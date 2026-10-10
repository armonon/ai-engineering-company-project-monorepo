"use client";

import { useState, type FormEvent } from "react";
import type { Candidate, CandidateInput } from "@/lib/talent";

interface CandidateFormProps {
  initial?: Candidate;
  submitLabel: string;
  onSubmit: (data: CandidateInput) => Promise<void>;
  onCancel?: () => void;
}

type FieldErrors = Partial<Record<keyof CandidateInput, string>>;

export function CandidateForm({
  initial,
  submitLabel,
  onSubmit,
  onCancel,
}: CandidateFormProps) {
  const [fullName, setFullName] = useState(initial?.full_name ?? "");
  const [email, setEmail] = useState(initial?.email ?? "");
  const [phone, setPhone] = useState(initial?.phone ?? "");
  const [position, setPosition] = useState(initial?.position ?? "");
  const [linkedInUrl, setLinkedInUrl] = useState(
    initial?.linkedin_url ?? "",
  );
  const [cvUrl, setCvUrl] = useState(initial?.cv_url ?? "");
  const [experienceYears, setExperienceYears] = useState(
    initial ? String(initial.experience_years) : "",
  );
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitting, setSubmitting] = useState(false);

  function validate(): FieldErrors {
    const nextErrors: FieldErrors = {};
    if (!fullName.trim()) nextErrors.full_name = "Full name is required";
    if (!email.trim()) nextErrors.email = "Email is required";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      nextErrors.email = "Invalid email format";
    }
    if (!phone.trim()) nextErrors.phone = "Phone is required";
    if (!position.trim()) nextErrors.position = "Position is required";
    const years = Number(experienceYears);
    if (experienceYears === "" || Number.isNaN(years) || years < 0) {
      nextErrors.experience_years =
        "Years of experience must be a non-negative number";
    }
    return nextErrors;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors = validate();
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setSubmitting(true);
    try {
      await onSubmit({
        full_name: fullName.trim(),
        email: email.trim(),
        phone: phone.trim(),
        position: position.trim(),
        linkedin_url: linkedInUrl.trim() || null,
        cv_url: cvUrl.trim() || null,
        experience_years: Number(experienceYears),
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Full name *" error={errors.full_name}>
          <input
            className={inputClass(Boolean(errors.full_name))}
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
          />
        </Field>
        <Field label="Email *" error={errors.email}>
          <input
            type="email"
            className={inputClass(Boolean(errors.email))}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </Field>
        <Field label="Phone *" error={errors.phone}>
          <input
            className={inputClass(Boolean(errors.phone))}
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
          />
        </Field>
        <Field label="Position applied for *" error={errors.position}>
          <input
            className={inputClass(Boolean(errors.position))}
            value={position}
            onChange={(event) => setPosition(event.target.value)}
          />
        </Field>
        <Field label="Years of experience *" error={errors.experience_years}>
          <input
            type="number"
            min={0}
            step="0.5"
            className={inputClass(Boolean(errors.experience_years))}
            value={experienceYears}
            onChange={(event) => setExperienceYears(event.target.value)}
          />
        </Field>
        <Field label="LinkedIn URL">
          <input
            type="url"
            className={inputClass(false)}
            value={linkedInUrl}
            onChange={(event) => setLinkedInUrl(event.target.value)}
          />
        </Field>
        <Field label="CV URL">
          <input
            type="url"
            className={inputClass(false)}
            value={cvUrl}
            onChange={(event) => setCvUrl(event.target.value)}
          />
        </Field>
      </div>

      <div className="flex gap-3 pt-2">
        <button
          type="submit"
          disabled={submitting}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60"
        >
          {submitting ? "Saving…" : submitLabel}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700">
        {label}
      </span>
      {children}
      {error && (
        <span className="mt-1 block text-xs text-red-600">{error}</span>
      )}
    </label>
  );
}

function inputClass(hasError: boolean): string {
  return `w-full rounded-md border px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 ${
    hasError
      ? "border-red-400 focus:ring-red-300"
      : "border-slate-300 focus:ring-slate-400"
  }`;
}
