"use client";

import { toUserMessage } from "@/lib/errors";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { register } from "@/lib/auth";
import { beginTelemetrySession, track } from "@/lib/telemetry";
import { AuthShell, Field, inputCls } from "@/components/LoginForm";

export function RegisterForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function validate(): Record<string, string> {
    const errs: Record<string, string> = {};
    if (!email.trim()) {
      errs.email = "Email is required.";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      errs.email = "Enter a valid email address.";
    }
    // Mirrors the API's min_length=8 so the obvious case is caught
    // without a round-trip; the server still enforces it.
    if (!password) {
      errs.password = "Password is required.";
    } else if (password.length < 8) {
      errs.password = "Must be at least 8 characters.";
    }
    if (confirm !== password) errs.confirm = "Passwords do not match.";
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
      // Registers, then logs in with the same credentials so the user
      // lands authenticated rather than on a second form.
      const session = await register({
        email: email.trim(),
        password,
        name: name.trim() || undefined,
        phone: phone.trim() || undefined,
        address: address.trim() || undefined,
      });
      beginTelemetrySession(session.telemetry_user_id);
      track("login_succeeded", {
        auth_method: "password",
        role: session.role,
        session_age_seconds: 0,
      });
      router.replace("/");
    } catch (err) {
      setApiError(
        toUserMessage(err, "Could not create the account."),
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Create an account"
      subtitle="TrackFlow Backoffice — People & Operations"
      footer={
        <>
          Already registered?{" "}
          <Link href="/login" className="font-medium text-slate-900 underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {apiError && (
          <div
            role="alert"
            className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800"
          >
            {apiError}
          </div>
        )}

        <Field label="Email *" error={fieldErrors.email}>
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputCls(!!fieldErrors.email)}
            placeholder="you@trackflow.com"
          />
        </Field>

        <Field label="Password *" error={fieldErrors.password}>
          <input
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputCls(!!fieldErrors.password)}
            placeholder="At least 8 characters"
          />
        </Field>

        <Field label="Confirm password *" error={fieldErrors.confirm}>
          <input
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className={inputCls(!!fieldErrors.confirm)}
          />
        </Field>

        <fieldset className="space-y-3 border-t border-slate-200 pt-4">
          <legend className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Profile (optional)
          </legend>

          <Field label="Full name">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={inputCls(false)}
              placeholder="Carlos Vega"
            />
          </Field>

          <Field label="Phone">
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className={inputCls(false)}
              placeholder="+34 976 000 000"
            />
          </Field>

          <Field label="Address">
            <input
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              className={inputCls(false)}
              placeholder="Zaragoza, ES"
            />
          </Field>
        </fieldset>

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60"
        >
          {submitting ? "Creating account…" : "Create account"}
        </button>
      </form>
    </AuthShell>
  );
}
