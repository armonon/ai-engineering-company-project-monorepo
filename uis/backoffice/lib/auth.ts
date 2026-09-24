import { API_BASE_URL } from "@/lib/api";
import { readJson } from "@/lib/errors";
import {
  endpointTemplate,
  telemetryRequestHeaders,
  track,
  trackApiRequestCompleted,
} from "@/lib/telemetry";

/**
 * Token lifecycle for the backoffice.
 *
 * The token lives in localStorage (per AUTH-02) and is attached to every
 * protected call as `Authorization: Bearer <token>`. A 401 from any
 * protected call clears the session and sends the user to /login.
 *
 * Note the deliberate consequence of localStorage: the token is not
 * readable by Next.js middleware, which runs on the server. Route
 * protection is therefore a client-side guard (see AuthProvider), not
 * middleware — the brief calls this out explicitly.
 */

export const TOKEN_KEY = "trackflow.backoffice.token";

/** Routes reachable without a session. Everything else is guarded. */
/**
 * Routes reachable without a session. The password-recovery pages
 * must be public by definition — a user who cannot sign in has to be
 * able to reach them.
 */
export const PUBLIC_ROUTES = [
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
] as const;

export interface Profile {
  id: number;
  user_id: number;
  name: string | null;
  phone: string | null;
  address: string | null;
}

export type Role = "admin" | "manager" | "user";

export interface CurrentUser {
  id: number;
  email: string;
  role: Role;
  is_active: boolean;
  telemetry_user_id: string;
  profile: Profile | null;
}

// ---------------------------------------------------------------------------
// Storage
// ---------------------------------------------------------------------------

export function getToken(): string | null {
  // Guard for SSR: this module is imported by client components that
  // Next.js still renders once on the server.
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    // Private-browsing modes can throw on localStorage access.
    return null;
  }
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* storage unavailable — the session simply will not persist */
  }
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* nothing to do */
  }
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

export class UnauthorizedError extends Error {
  constructor(message = "Session expired") {
    super(message);
    this.name = "UnauthorizedError";
  }
}

/**
 * Used whenever the response carries nothing a person can act on. It
 * deliberately omits the status code: "Request failed (500)" tells the
 * reader nothing they can do, and the ticket asks for an exit, not a
 * number.
 */
const GENERIC_REQUEST_FAILURE =
  "That request didn't go through. Please try again — if it keeps " +
  "happening, contact support.";

/** Turn a FastAPI error body into one readable line. */
export async function readApiError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      // Pydantic 422: [{loc: [...], msg: "..."}]
      return detail
        .map((d: { loc?: unknown[]; msg?: string }) => {
          const field = Array.isArray(d.loc)
            ? d.loc.filter((p) => p !== "body").join(".")
            : "";
          return field ? `${field}: ${d.msg}` : String(d.msg ?? "");
        })
        .join(" · ");
    }
    // An object detail — the incident manager returns
    // {field, message}. Read the message out of it; stringifying the
    // body used to put raw JSON on the screen.
    if (detail && typeof detail === "object") {
      const message = (detail as { message?: unknown }).message;
      if (typeof message === "string" && message.trim()) return message;
    }
    return GENERIC_REQUEST_FAILURE;
  } catch {
    // The body was not JSON at all — an error page or a truncated
    // response. Its content is no use to the reader.
    return GENERIC_REQUEST_FAILURE;
  }
}

// ---------------------------------------------------------------------------
// Fetch wrapper
// ---------------------------------------------------------------------------

/** Called when any protected request comes back 401. Set by AuthProvider. */
export type SessionExpiryReason = "token_expired" | "token_revoked";

let onUnauthorized: ((reason: SessionExpiryReason) => void) | null = null;

export function setUnauthorizedHandler(
  handler: ((reason: SessionExpiryReason) => void) | null,
): void {
  onUnauthorized = handler;
}

function sessionExpiryReason(token: string | null): SessionExpiryReason {
  if (!token) return "token_revoked";
  try {
    const encoded = token.split(".")[1];
    if (!encoded) return "token_revoked";
    const base64 = encoded.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, "=");
    const payload = JSON.parse(window.atob(padded)) as { exp?: unknown };
    return typeof payload.exp === "number" && payload.exp * 1000 <= Date.now()
      ? "token_expired"
      : "token_revoked";
  } catch {
    return "token_revoked";
  }
}

function roleFromToken(token: string | null): Role | null {
  if (!token) return null;
  try {
    const encoded = token.split(".")[1];
    if (!encoded) return null;
    const base64 = encoded.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, "=");
    const payload = JSON.parse(window.atob(padded)) as { role?: unknown };
    return ["admin", "manager", "user"].includes(String(payload.role))
      ? payload.role as Role
      : null;
  } catch {
    return null;
  }
}

/**
 * fetch() with the bearer token attached and centralised 401 handling.
 *
 * Every protected call in the backoffice goes through here, so the
 * "401 → clear session → redirect to /login" rule lives in exactly one
 * place rather than being re-implemented per call site.
 */
export async function authFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const correlation = telemetryRequestHeaders();
  for (const [name, value] of Object.entries(correlation.headers)) {
    headers.set(name, value);
  }

  const startedAt = typeof performance === "undefined" ? Date.now() : performance.now();
  const res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  const finishedAt = typeof performance === "undefined" ? Date.now() : performance.now();
  trackApiRequestCompleted({
    path,
    method: init.method ?? "GET",
    status: res.status,
    durationMs: finishedAt - startedAt,
    requestId: correlation.requestId,
  });

  if (res.status === 403) {
    const actualRole = roleFromToken(token);
    if (actualRole) {
      track("authorization_denied", {
        endpoint_template: endpointTemplate(path),
        method: (init.method ?? "GET").toUpperCase(),
        required_role: path.startsWith("/users/") ? "owner" : "admin",
        actual_role: actualRole,
        reason_code: path.startsWith("/users/")
          ? "ownership_mismatch"
          : "role_insufficient",
      });
    }
  }

  if (res.status === 401) {
    const reason = sessionExpiryReason(token);
    clearToken();
    onUnauthorized?.(reason);
    throw new UnauthorizedError(
      "Your session has expired. Please sign in again.",
    );
  }
  return res;
}

/** authFetch + JSON parsing + error-to-Error conversion. */
export async function authJson<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await authFetch(path, init);
  if (!res.ok) throw new Error(await readApiError(res));
  return readJson<T>(res);
}

// ---------------------------------------------------------------------------
// Auth API
// ---------------------------------------------------------------------------

export interface AuthenticatedSession {
  access_token: string;
  token_type: string;
  expires_in: number;
  telemetry_user_id: string;
  role: Role;
}

export type LoginFailureReason =
  | "invalid_credentials"
  | "inactive_account"
  | "rate_limited"
  | "network_error";

export class LoginError extends Error {
  constructor(
    message: string,
    readonly reasonCode: LoginFailureReason,
  ) {
    super(message);
    this.name = "LoginError";
  }
}

export async function login(
  email: string,
  password: string,
): Promise<AuthenticatedSession> {
  // Not authFetch: there is no token yet, and a 401 here means "bad
  // credentials", which the form shows inline rather than redirecting.
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  } catch {
    throw new LoginError("Could not reach the sign-in service.", "network_error");
  }
  if (!res.ok) {
    const responseText = await res.clone().text();
    const reason: LoginFailureReason =
      res.status === 429
        ? "rate_limited"
        : res.status === 401 && responseText.toLowerCase().includes("deactivated")
          ? "inactive_account"
          : "invalid_credentials";
    throw new LoginError(await readApiError(res), reason);
  }

  const data = await readJson<AuthenticatedSession>(res);
  setToken(data.access_token);
  return data;
}

export interface RegisterInput {
  email: string;
  password: string;
  name?: string;
  phone?: string;
  address?: string;
}

/**
 * Register, then immediately log in with the same credentials so the
 * user lands authenticated instead of on a second form.
 */
export async function register(
  input: RegisterInput,
): Promise<AuthenticatedSession> {
  const res = await fetch(`${API_BASE_URL}/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: input.email,
      password: input.password,
      name: input.name || null,
      phone: input.phone || null,
      address: input.address || null,
    }),
  });
  if (!res.ok) throw new Error(await readApiError(res));

  return login(input.email, input.password);
}

export function fetchCurrentUser(): Promise<CurrentUser> {
  return authJson<CurrentUser>("/auth/me");
}

export function updateMyProfile(patch: {
  name?: string | null;
  phone?: string | null;
  address?: string | null;
}): Promise<Profile> {
  return authJson<Profile>("/profiles/me", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}


// ---------------------------------------------------------------------------
// Password recovery / change (AUTH-03)
// ---------------------------------------------------------------------------

interface MessageResponse {
  message: string;
}

/**
 * Ask for a reset link.
 *
 * The API answers 200 with the same body whether or not the address is
 * registered, so this never reveals which emails exist — the caller
 * shows one confirmation message regardless.
 */
export async function forgotPassword(email: string): Promise<{
  message: string;
  outcome: "accepted" | "rate_limited";
}> {
  const res = await fetch(`${API_BASE_URL}/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (res.status === 429) {
    return { message: await readApiError(res), outcome: "rate_limited" };
  }
  if (!res.ok) throw new Error(await readApiError(res));
  const data = await readJson<MessageResponse>(res);
  return { message: data.message, outcome: "accepted" };
}

/** Set a new password using the token from the reset link. */
export async function resetPassword(
  token: string,
  newPassword: string,
): Promise<string> {
  const res = await fetch(`${API_BASE_URL}/auth/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password: newPassword }),
  });
  if (!res.ok) throw new Error(await readApiError(res));
  const data = await readJson<MessageResponse>(res);
  return data.message;
}

/** Change the password of the signed-in user. Requires a session. */
export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<string> {
  const data = await authJson<MessageResponse>("/auth/change-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
  return data.message;
}
