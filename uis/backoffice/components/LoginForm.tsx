"use client";

import { toUserMessage } from "@/lib/errors";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useRef, useState } from "react";
import { LoginError, login } from "@/lib/auth";
import { beginTelemetrySession, track } from "@/lib/telemetry";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  // Set by /reset-password after a successful reset.
  const justReset = searchParams.get("reset") === "1";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const failedAttempts = useRef(0);

  function validate(): Record<string, string> {
    const errs: Record<string, string> = {};
    if (!email.trim()) errs.email = "Email is required.";
    if (!password) errs.password = "Password is required.";
    return errs;
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setApiError(null);

    const errs = validate();
    setFieldErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setSubmitting(true);
    try {
      const session = await login(email.trim(), password);
      beginTelemetrySession(session.telemetry_user_id);
      track("login_succeeded", {
        auth_method: "password",
        role: session.role,
        session_age_seconds: 0,
      });
      failedAttempts.current = 0;
      // Token is stored; go to the main authenticated view.
      router.replace("/");
    } catch (err) {
      failedAttempts.current += 1;
      track("login_failed", {
        auth_method: "password",
        reason_code:
          err instanceof LoginError ? err.reasonCode : "network_error",
        attempt_number: failedAttempts.current,
      });
      setApiError(
        toUserMessage(err, "Could not sign in. Try again."),
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Sign in"
      subtitle="TrackFlow Backoffice — People & Operations"
      footer={
        <>
          No account yet?{" "}
          <Link href="/register" className="font-medium text-slate-900 underline">
            Create one
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {justReset && !apiError && (
          <div
            role="status"
            className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800"
          >
            Your password has been updated. Sign in with your new password.
          </div>
        )}

        {apiError && (
          <div
            role="alert"
            className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800"
          >
            {apiError}
          </div>
        )}

        <Field label="Email" error={fieldErrors.email}>
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputCls(!!fieldErrors.email)}
            placeholder="you@trackflow.com"
          />
        </Field>

        <Field label="Password" error={fieldErrors.password}>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputCls(!!fieldErrors.password)}
            placeholder="••••••••"
          />
        </Field>

        <div className="flex justify-end">
          <Link
            href="/forgot-password"
            className="text-xs font-medium text-slate-600 underline hover:text-slate-900"
          >
            Forgot your password?
          </Link>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60"
        >
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </AuthShell>
  );
}

export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-md bg-slate-900 text-sm font-bold text-white">
            TF
          </span>
          <div>
            <p className="text-sm font-semibold text-slate-900">TrackFlow</p>
            <p className="text-xs text-slate-500">{subtitle}</p>
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <h1 className="mb-4 text-lg font-semibold text-slate-900">{title}</h1>
          {children}
        </div>

        {footer && (
          <p className="mt-4 text-center text-sm text-slate-600">{footer}</p>
        )}
      </div>
    </div>
  );
}

export function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium text-slate-700">{label}</span>
      {children}
      {error && <span className="mt-1 block text-xs text-red-600">{error}</span>}
    </label>
  );
}

export function inputCls(hasError: boolean): string {
  return `w-full rounded-md border px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 ${
    hasError
      ? "border-red-400 focus:ring-red-300"
      : "border-slate-300 focus:ring-slate-400"
  }`;
}
