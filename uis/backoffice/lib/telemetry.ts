import eventCatalogueJson from "../../../docs/telemetry/event-schemas.json";

type JsonValue = string | number | boolean | null;
type TelemetryProperties = Record<string, JsonValue>;

interface FieldSpec {
  type: "string" | "integer" | "number" | "boolean" | "object";
  required: boolean;
  enum?: JsonValue[];
  const?: JsonValue;
  pattern?: string;
  minLength?: number;
  minimum?: number;
  maximum?: number;
  format?: "uuid" | "date-time";
}

interface EventSpec {
  schemaVersion: string;
  properties: {
    additionalProperties: boolean;
    fields: Record<string, FieldSpec>;
  };
}

interface EventCatalogue {
  events: Record<string, EventSpec>;
}

export interface TelemetryEvent {
  eventId: string;
  timestamp: string;
  sessionId: string;
  userId: string;
  event_type: string;
  schemaVersion: string;
  requestId: string;
  properties: TelemetryProperties;
}

const eventCatalogue = eventCatalogueJson as EventCatalogue;
const SESSION_ID_KEY = "trackflow.telemetry.session_id";
const SESSION_STARTED_KEY = "trackflow.telemetry.session_started";
const BATCH_SIZE = 20;
const FLUSH_INTERVAL_MS = 10_000;
const MAX_RETRIES = 3;
const INITIAL_BACKOFF_MS = 250;
const API_SLO_MS = 750;
const USER_ID_PATTERN = /^(anonymous|system|usr_[a-f0-9]{64})$/;

let sessionId: string | null = null;
let sessionStartedAt: number | null = null;
let userId = "anonymous";

function randomUuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  const bytes = new Uint8Array(16);
  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    crypto.getRandomValues(bytes);
  } else {
    for (let index = 0; index < bytes.length; index += 1) {
      bytes[index] = Math.floor(Math.random() * 256);
    }
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0"));
  return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10).join("")}`;
}

function safeSessionGet(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSessionSet(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(key, value);
  } catch {
    // The in-memory values still keep this tab internally consistent.
  }
}

function safeSessionRemove(key: string): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(key);
  } catch {
    // The in-memory values are cleared below regardless.
  }
}

function ensureSession(): string {
  if (sessionId) return sessionId;

  sessionId = safeSessionGet(SESSION_ID_KEY) || `sess_${randomUuid()}`;
  const storedStartedAt = Number(safeSessionGet(SESSION_STARTED_KEY));
  sessionStartedAt = Number.isFinite(storedStartedAt) && storedStartedAt > 0
    ? storedStartedAt
    : Date.now();
  safeSessionSet(SESSION_ID_KEY, sessionId);
  safeSessionSet(SESSION_STARTED_KEY, String(sessionStartedAt));
  return sessionId;
}

/** Start a fresh authenticated browser session immediately after login. */
export function beginTelemetrySession(pseudonymousUserId: string): void {
  sessionId = `sess_${randomUuid()}`;
  sessionStartedAt = Date.now();
  safeSessionSet(SESSION_ID_KEY, sessionId);
  safeSessionSet(SESSION_STARTED_KEY, String(sessionStartedAt));
  identifyTelemetryUser(pseudonymousUserId);
}

/** Attach the authenticated pseudonym when an existing session is restored. */
export function identifyTelemetryUser(pseudonymousUserId: string): void {
  userId = USER_ID_PATTERN.test(pseudonymousUserId)
    ? pseudonymousUserId
    : "anonymous";
  ensureSession();
}

/** Flush pending events and forget the tab session after an explicit logout. */
export function endTelemetrySession(): void {
  telemetryService.flushWithBeacon();
  safeSessionRemove(SESSION_ID_KEY);
  safeSessionRemove(SESSION_STARTED_KEY);
  sessionId = null;
  sessionStartedAt = null;
  userId = "anonymous";
}

export function telemetrySessionAgeSeconds(): number {
  ensureSession();
  return Math.max(0, Math.floor((Date.now() - (sessionStartedAt ?? Date.now())) / 1000));
}

export function resolveTelemetryEndpoint(
  configured = process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT,
  apiBase = process.env.NEXT_PUBLIC_API_BASE_URL,
): string {
  const explicit = configured?.trim();
  if (explicit) return explicit.replace(/\/+$/, "");

  const base = apiBase?.trim().replace(/\/+$/, "");
  return base ? `${base}/telemetry/events` : "";
}

function valueMatches(value: JsonValue, spec: FieldSpec): boolean {
  if (spec.type === "string") {
    if (typeof value !== "string") return false;
    if (spec.enum && !spec.enum.includes(value)) return false;
    if (spec.const !== undefined && value !== spec.const) return false;
    if (spec.pattern && !new RegExp(spec.pattern).test(value)) return false;
    if (spec.minLength !== undefined && value.length < spec.minLength) return false;
    if (spec.format === "uuid" && !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)) return false;
    if (spec.format === "date-time" && Number.isNaN(Date.parse(value))) return false;
    return true;
  }
  if (spec.type === "integer") {
    if (!Number.isInteger(value)) return false;
    const numeric = value as number;
    if (spec.minimum !== undefined && numeric < spec.minimum) return false;
    if (spec.maximum !== undefined && numeric > spec.maximum) return false;
    if (spec.const !== undefined && numeric !== spec.const) return false;
    if (spec.enum && !spec.enum.includes(numeric)) return false;
    return true;
  }
  if (spec.type === "number") {
    if (typeof value !== "number" || !Number.isFinite(value)) return false;
    if (spec.minimum !== undefined && value < spec.minimum) return false;
    if (spec.maximum !== undefined && value > spec.maximum) return false;
    return true;
  }
  if (spec.type === "boolean") return typeof value === "boolean";
  return value !== null && typeof value === "object";
}

function propertiesMatch(
  eventType: string,
  properties: TelemetryProperties,
): properties is TelemetryProperties {
  const spec = eventCatalogue.events[eventType];
  if (!spec) return false;

  const allowed = spec.properties.fields;
  if (Object.keys(properties).some((key) => !(key in allowed))) return false;
  return Object.entries(allowed).every(([key, field]) => {
    if (field.required && !(key in properties)) return false;
    return !(key in properties) || valueMatches(properties[key], field);
  });
}

function telemetryWarning(eventType: string, reason: string): void {
  if (process.env.NODE_ENV !== "production") {
    // Never print values: rejected properties may contain exactly the PII the
    // allowlist is designed to stop.
    console.warn(`Telemetry event '${eventType}' discarded: ${reason}.`);
  }
}

class TelemetryService {
  private queue: TelemetryEvent[] = [];
  private intervalId: number | null = null;
  private started = false;
  private activeFlush: Promise<void> | null = null;

  track(eventType: string, properties: TelemetryProperties): void {
    const spec = eventCatalogue.events[eventType];
    if (!spec) {
      telemetryWarning(eventType, "event_type is not registered");
      return;
    }
    if (!propertiesMatch(eventType, properties)) {
      telemetryWarning(eventType, "properties do not match the approved allowlist");
      return;
    }

    this.ensureStarted();
    this.enqueue({
      eventId: randomUuid(),
      timestamp: new Date().toISOString(),
      sessionId: ensureSession(),
      userId,
      event_type: eventType,
      schemaVersion: spec.schemaVersion,
      requestId: `req_${randomUuid()}`,
      properties: { ...properties },
    });
  }

  trackForRequest(
    eventType: string,
    properties: TelemetryProperties,
    requestId: string,
  ): void {
    const spec = eventCatalogue.events[eventType];
    if (!spec || !propertiesMatch(eventType, properties)) {
      telemetryWarning(eventType, "request event does not match the approved schema");
      return;
    }
    this.ensureStarted();
    this.enqueue({
      eventId: randomUuid(),
      timestamp: new Date().toISOString(),
      sessionId: ensureSession(),
      userId,
      event_type: eventType,
      schemaVersion: spec.schemaVersion,
      requestId,
      properties: { ...properties },
    });
  }

  private enqueue(event: TelemetryEvent): void {
    this.queue.push(event);
    if (this.queue.length >= BATCH_SIZE) void this.flush();
  }

  private ensureStarted(): void {
    if (this.started || typeof window === "undefined") return;
    this.started = true;
    this.intervalId = window.setInterval(() => void this.flush(), FLUSH_INTERVAL_MS);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "hidden") this.flushWithBeacon();
    });
  }

  flush(): Promise<void> {
    if (this.activeFlush) return this.activeFlush;
    if (this.queue.length === 0) return Promise.resolve();

    const batch = this.queue.splice(0, this.queue.length);
    this.activeFlush = this.sendWithRetry(batch).finally(() => {
      this.activeFlush = null;
      if (this.queue.length >= BATCH_SIZE) void this.flush();
    });
    return this.activeFlush;
  }

  flushWithBeacon(): void {
    if (this.queue.length === 0 || typeof navigator === "undefined") return;
    const endpoint = resolveTelemetryEndpoint();
    if (!endpoint || typeof navigator.sendBeacon !== "function") return;

    const batch = this.queue.slice();
    const accepted = navigator.sendBeacon(
      endpoint,
      new Blob([JSON.stringify({ events: batch })], {
        type: "application/json",
      }),
    );
    if (accepted) this.queue.splice(0, batch.length);
  }

  private async sendWithRetry(batch: TelemetryEvent[]): Promise<void> {
    const endpoint = resolveTelemetryEndpoint();
    if (!endpoint) {
      telemetryWarning("batch", "NEXT_PUBLIC_TELEMETRY_ENDPOINT is not configured");
      return;
    }

    for (let attempt = 0; attempt <= MAX_RETRIES; attempt += 1) {
      try {
        const response = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ events: batch }),
          keepalive: true,
        });
        if (!response.ok) throw new Error("telemetry receiver rejected the batch");
        return;
      } catch {
        if (attempt === MAX_RETRIES) {
          telemetryWarning("batch", "delivery failed after three retries");
          return;
        }
        await new Promise<void>((resolve) => {
          setTimeout(resolve, INITIAL_BACKOFF_MS * 2 ** attempt);
        });
      }
    }
  }
}

const telemetryService = new TelemetryService();

/** The only public event-capture function used by backoffice components. */
export function track(
  eventType: string,
  properties: Record<string, unknown>,
): void {
  telemetryService.track(eventType, properties as TelemetryProperties);
}

export function telemetryRequestHeaders(): {
  requestId: string;
  headers: Record<string, string>;
} {
  const requestId = `req_${randomUuid()}`;
  return {
    requestId,
    headers: {
      "X-Request-ID": requestId,
      "X-Telemetry-Session-ID": ensureSession(),
    },
  };
}

export function endpointTemplate(path: string): string {
  const pathname = path.split(/[?#]/, 1)[0] || "/";
  return pathname
    .replace(/\/[0-9]+(?=\/|$)/g, "/{id}")
    .replace(/\/[0-9a-f]{8}-[0-9a-f-]{27,}(?=\/|$)/gi, "/{id}");
}

export function trackApiRequestCompleted(input: {
  path: string;
  method: string;
  status: number;
  durationMs: number;
  requestId: string;
}): void {
  const method = input.method.toUpperCase();
  if (!["GET", "POST", "PUT", "PATCH", "DELETE"].includes(method)) return;
  const duration = Math.max(0, Math.round(input.durationMs));
  const statusClass = `${Math.floor(input.status / 100)}xx`;
  const slow = duration > API_SLO_MS;

  if (input.status >= 400) {
    telemetryService.trackForRequest(
      "api_error_returned",
      {
        service: "trackflow_api",
        endpoint_template: endpointTemplate(input.path),
        method,
        status_code: input.status,
        error_code: `HTTP_${input.status}`,
        duration_ms: duration,
        retryable: input.status >= 500 || input.status === 429,
      },
      input.requestId,
    );
  }

  if (input.status >= 400 || slow || Math.random() < 0.1) {
    telemetryService.trackForRequest(
      "api_latency_recorded",
      {
        service: "trackflow_api",
        endpoint_template: endpointTemplate(input.path),
        method,
        status_class: statusClass,
        duration_ms: duration,
        slo_exceeded: slow,
      },
      input.requestId,
    );
  }
}

function safeErrorCode(error: unknown): string {
  const name = error instanceof Error ? error.name : "UnknownError";
  const normalised = name.replace(/[^A-Za-z0-9]+/g, "_").toUpperCase();
  return normalised.length > 1 ? normalised : "UNKNOWN_ERROR";
}

async function errorFingerprint(error: unknown): Promise<string> {
  const source = error instanceof Error
    ? `${error.name}\n${error.stack ?? "no-stack"}`
    : "UnknownError";
  if (typeof crypto !== "undefined" && crypto.subtle) {
    const bytes = await crypto.subtle.digest(
      "SHA-256",
      new TextEncoder().encode(source),
    );
    const hex = Array.from(new Uint8Array(bytes), (byte) =>
      byte.toString(16).padStart(2, "0"),
    ).join("");
    return `err_${hex}`;
  }

  let hash = 2166136261;
  for (const character of source) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return `err_${Math.abs(hash).toString(16).padStart(8, "0").repeat(4)}`;
}

export async function captureFrontendError(
  error: unknown,
  component: string,
  handled: boolean,
): Promise<void> {
  track("frontend_error_captured", {
    error_code: safeErrorCode(error),
    error_fingerprint: await errorFingerprint(error),
    component,
    route_template: endpointTemplate(
      typeof window === "undefined" ? "/unknown" : window.location.pathname,
    ),
    release: process.env.NEXT_PUBLIC_APP_RELEASE || "development",
    handled,
    occurrence_count: 1,
  });
}

export function viewportClass(): "mobile" | "tablet" | "desktop" {
  if (typeof window === "undefined") return "desktop";
  if (window.innerWidth < 640) return "mobile";
  if (window.innerWidth < 1024) return "tablet";
  return "desktop";
}
