"use client";

import Link from "next/link";
import { useState } from "react";
import { forgotPassword } from "@/lib/auth";
import { AuthShell, Field, inputCls } from "@/components/LoginForm";
import { track } from "@/lib/telemetry";

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!email.trim()) {
      setFieldError("Email is required.");
      return;
    }
    setFieldError(null);
    setSubmitting(true);

    try {
      const response = await forgotPassword(email.trim().toLowerCase());
      track("password_reset_requested", {
        delivery_channel: "email",
        outcome: response.outcome,
      });
    } catch {
      // Swallowed on purpose. The confirmation must look identical
      // whether or not the address is registered, and a transport
      // hiccup must not become a signal either.
    } finally {
      setSubmitting(false);
      // Disables the form, so a second click cannot fire a duplicate
      // request.
      setSubmitted(true);
    }
  }

  return (
    <AuthShell
      title="Forgot your password?"
      subtitle="TrackFlow Backoffice — People & Operations"
      footer={
        <Link href="/login" className="font-medium text-slate-900 underline">
          Back to sign in
        </Link>
      }
    >
      {submitted ? (
        <div
          role="status"
          className="rounded-md border border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-900"
        >
          <p className="font-medium">Check your inbox</p>
          <p className="mt-1">
            If that address is registered, you&apos;ll receive a link
            shortly. The link expires and can only be used once.
          </p>
        </div>
      ) : (
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          <p className="text-sm text-slate-600">
            Enter the email address on your account and we&apos;ll send you
            a link to choose a new password.
          </p>

          <Field label="Email" error={fieldError ?? undefined}>
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputCls(!!fieldError)}
              placeholder="you@trackflow.com"
            />
          </Field>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60"
          >
            {submitting ? "Sending…" : "Send reset link"}
          </button>
        </form>
      )}
    </AuthShell>
  );
}
