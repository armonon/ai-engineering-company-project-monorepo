"use client";

import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  PUBLIC_ROUTES,
  UnauthorizedError,
  clearToken,
  fetchCurrentUser,
  getToken,
  setUnauthorizedHandler,
  type CurrentUser,
} from "@/lib/auth";
import { toUserMessage } from "@/lib/errors";
import {
  endTelemetrySession,
  endpointTemplate,
  identifyTelemetryUser,
  telemetrySessionAgeSeconds,
  track,
} from "@/lib/telemetry";

interface AuthContextValue {
  user: CurrentUser | null;
  /** True until the initial token check has finished. */
  loading: boolean;
  refresh: () => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

function isPublicRoute(pathname: string): boolean {
  return PUBLIC_ROUTES.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`),
  );
}

/**
 * Client-side session guard.
 *
 * Deliberately not Next.js middleware: middleware runs on the server
 * and cannot read localStorage, where AUTH-02 requires the token to
 * live. This provider reads the token in the browser, verifies it
 * against GET /auth/me, and redirects to /login when it is absent or
 * rejected.
 *
 * It wraps only the backoffice. The public website (uis/website) has no
 * provider, no token check, and no redirect.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  // The third state. The session check used to be binary — signed in or
  // signed out — which forced "we could not ask" into "signed out".
  const [sessionError, setSessionError] = useState<string | null>(null);

  const publicRoute = isPublicRoute(pathname);

  const logout = useCallback(() => {
    endTelemetrySession();
    clearToken();
    setUser(null);
    router.replace("/login");
  }, [router]);

  const refresh = useCallback(async () => {
    const token = getToken();
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const currentUser = await fetchCurrentUser();
      identifyTelemetryUser(currentUser.telemetry_user_id);
      setUser(currentUser);
      setSessionError(null);
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        // The server actually rejected the token — expired, tampered
        // with, or the account is gone. Signing out is correct.
        clearToken();
        setUser(null);
        setSessionError(null);
      } else {
        // We could not reach the server, or could not read its reply.
        // That says nothing about whether the session is valid, so the
        // token is KEPT. Clearing it here logged people out of a working
        // session every time the API blinked, and they had to sign in
        // again even once it came back.
        setSessionError(
          toUserMessage(
            err,
            "We couldn't reach the server to confirm your session.",
          ),
        );
      }
    } finally {
      setLoading(false);
    }
  }, []);

  // Any 401 from a protected call anywhere in the app lands here.
  useEffect(() => {
    setUnauthorizedHandler((reason) => {
      track("session_expired", {
        session_age_seconds: telemetrySessionAgeSeconds(),
        expiry_reason: reason,
        route_template: endpointTemplate(pathname),
      });
      endTelemetrySession();
      setUser(null);
      router.replace("/login");
    });
    return () => setUnauthorizedHandler(null);
  }, [pathname, router]);

  // Verify the session on mount and whenever the route changes.
  useEffect(() => {
    queueMicrotask(() => {
      setLoading(true);
      void refresh();
    });
  }, [refresh, pathname]);

  // Redirect unauthenticated users away from guarded routes.
  useEffect(() => {
    if (loading || publicRoute || sessionError) return;
    if (!getToken()) router.replace("/login");
  }, [loading, publicRoute, router, sessionError, user]);

  const value = useMemo(
    () => ({ user, loading, refresh, logout }),
    [user, loading, refresh, logout],
  );

  // Public routes render immediately — no session needed.
  if (publicRoute) {
    return (
      <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
    );
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <p className="text-sm text-slate-500">Checking your session…</p>
      </div>
    );
  }

  // Rejected: we could not confirm the session. The token is still
  // here, so this is recoverable — say so and offer the retry, rather
  // than dumping the user on the sign-in page with no explanation.
  if (sessionError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
        <div
          role="alert"
          className="w-full max-w-md rounded-lg border border-amber-300 bg-amber-50 p-6 text-sm text-amber-900"
        >
          <p className="font-medium">We can&apos;t reach TrackFlow right now</p>
          <p className="mt-1">{sessionError}</p>
          <p className="mt-1">
            You are still signed in — this is a connection problem, not a
            session problem.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => {
                setLoading(true);
                void refresh();
              }}
              className="rounded-md border border-amber-400 bg-white px-3 py-1.5 font-medium hover:bg-amber-100"
            >
              Try again
            </button>
            <button
              type="button"
              onClick={logout}
              className="rounded-md border border-amber-300 bg-white px-3 py-1.5 font-medium hover:bg-amber-100"
            >
              Sign out
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Not signed in: render nothing while the redirect above runs, so a
  // protected view never flashes on screen.
  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <p className="text-sm text-slate-500">Redirecting to sign in…</p>
      </div>
    );
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
