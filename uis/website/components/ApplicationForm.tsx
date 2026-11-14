"use client";

import { useState } from "react";
import {
  COMMENTS_LIMIT,
  FIELDS,
  OPTIONS,
  commentsRemaining,
  emptyApplication,
  lowVolumeWarning,
  validateField,
  validateForm,
  type ApplicationValues,
  type FieldName,
} from "@/lib/applicationValidation";

const FIELD_CLASS =
  "mt-1 w-full rounded-md border border-slate-400 px-3 py-2 text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-blue-700";

function FieldError({ name, message }: { name: string; message?: string }) {
  return (
    <p id={`${name}-error`} className="mt-1 text-sm text-red-700" role="alert">
      {message ?? ""}
    </p>
  );
}

export function ApplicationForm() {
  const [values, setValues] = useState<ApplicationValues>(emptyApplication);
  const [errors, setErrors] = useState<Partial<Record<FieldName, string>>>({});
  const [submitted, setSubmitted] = useState(false);

  function set<K extends FieldName>(name: K, value: ApplicationValues[K]) {
    setValues((current) => ({ ...current, [name]: value }));
    // Clear an error as soon as the field becomes valid, like the static
    // site did on input.
    setErrors((current) => {
      if (!current[name]) return current;
      const message = validateField(name, value);
      if (message) return current;
      const next = { ...current };
      delete next[name];
      return next;
    });
  }

  function blur(name: FieldName) {
    const message = validateField(name, values[name]);
    setErrors((current) => {
      const next = { ...current };
      if (message) next[name] = message;
      else delete next[name];
      return next;
    });
  }

  function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const outcome = validateForm(values);
    setErrors(outcome.errors);
    if (!outcome.valid) {
      const firstInvalid = FIELDS.find((name) => outcome.errors[name]);
      if (firstInvalid) {
        document
          .querySelector<HTMLElement>(`[name="${firstInvalid}"]`)
          ?.focus();
      }
      return;
    }
    setSubmitted(true);
  }

  const warning = lowVolumeWarning(values);
  const remaining = commentsRemaining(values.comments);
  const invalid = (name: FieldName) => (errors[name] ? "true" : "false");

  if (submitted) {
    return (
      <section
        id="form-success"
        tabIndex={-1}
        role="status"
        aria-live="polite"
        className="mt-8 rounded-lg border border-emerald-300 bg-emerald-50 p-6 text-emerald-950"
      >
        <h2 className="text-xl font-semibold">
          Thank you for your interest in TrackFlow!
        </h2>
        <p className="mt-3">
          We have received your request. Our commercial team will review your
          information and contact you within the next 24-48 hours to schedule a
          call and learn about your logistics needs in detail.
        </p>
        <p className="mt-3">
          If you have any urgent inquiry, write to us directly at{" "}
          <a
            href="mailto:comercial@trackflow.com"
            className="font-semibold underline underline-offset-4"
          >
            comercial@trackflow.com
          </a>
          .
        </p>
      </section>
    );
  }

  return (
    <form onSubmit={onSubmit} noValidate className="mt-8 space-y-8">
      <fieldset className="rounded-lg border border-slate-200 p-6">
        <legend className="px-2 text-lg font-semibold">
          Company and contact
        </legend>

        <label className="block">
          <span className="font-medium">Company name *</span>
          <input
            name="companyName"
            type="text"
            value={values.companyName}
            onChange={(e) => set("companyName", e.target.value)}
            onBlur={() => blur("companyName")}
            aria-invalid={invalid("companyName")}
            aria-describedby="companyName-error"
            className={FIELD_CLASS}
          />
          <FieldError name="companyName" message={errors.companyName} />
        </label>

        <label className="mt-4 block">
          <span className="font-medium">Contact person *</span>
          <input
            name="contactPerson"
            type="text"
            value={values.contactPerson}
            onChange={(e) => set("contactPerson", e.target.value)}
            onBlur={() => blur("contactPerson")}
            aria-invalid={invalid("contactPerson")}
            aria-describedby="contactPerson-error"
            className={FIELD_CLASS}
          />
          <FieldError name="contactPerson" message={errors.contactPerson} />
        </label>

        <label className="mt-4 block">
          <span className="font-medium">Corporate email *</span>
          <input
            name="corporateEmail"
            type="email"
            value={values.corporateEmail}
            onChange={(e) => set("corporateEmail", e.target.value)}
            onBlur={() => blur("corporateEmail")}
            aria-invalid={invalid("corporateEmail")}
            aria-describedby="corporateEmail-error"
            className={FIELD_CLASS}
          />
          <FieldError name="corporateEmail" message={errors.corporateEmail} />
        </label>

        <label className="mt-4 block">
          <span className="font-medium">Phone *</span>
          <input
            name="phone"
            type="tel"
            placeholder="+1 213 555 0147"
            value={values.phone}
            onChange={(e) => set("phone", e.target.value)}
            onBlur={() => blur("phone")}
            aria-invalid={invalid("phone")}
            aria-describedby="phone-error"
            className={FIELD_CLASS}
          />
          <FieldError name="phone" message={errors.phone} />
        </label>

        <label className="mt-4 block">
          <span className="font-medium">Company website</span>
          <input
            name="companyWebsite"
            type="url"
            placeholder="https://example.com"
            value={values.companyWebsite}
            onChange={(e) => set("companyWebsite", e.target.value)}
            onBlur={() => blur("companyWebsite")}
            aria-invalid={invalid("companyWebsite")}
            aria-describedby="companyWebsite-error"
            className={FIELD_CLASS}
          />
          <FieldError name="companyWebsite" message={errors.companyWebsite} />
        </label>
      </fieldset>

      <fieldset className="rounded-lg border border-slate-200 p-6">
        <legend className="px-2 text-lg font-semibold">Your operation</legend>

        {(
          [
            ["mainOperatingCountry", "Main operating country *"],
            ["productType", "Product type *"],
            ["monthlyShippingVolume", "Estimated monthly shipping volume *"],
          ] as const
        ).map(([name, label]) => (
          <label key={name} className="mt-4 block first:mt-0">
            <span className="font-medium">{label}</span>
            <select
              name={name}
              value={values[name]}
              onChange={(e) => set(name, e.target.value)}
              onBlur={() => blur(name)}
              aria-invalid={invalid(name)}
              aria-describedby={`${name}-error`}
              className={`${FIELD_CLASS} bg-white`}
            >
              <option value="">Select…</option>
              {OPTIONS[name].map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
            <FieldError name={name} message={errors[name]} />
          </label>
        ))}

        {warning && (
          <p
            role="status"
            className="mt-4 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900"
          >
            {warning}
          </p>
        )}

        <fieldset className="mt-6">
          <legend className="font-medium">Services of interest *</legend>
          <div className="mt-2 space-y-2">
            {OPTIONS.servicesOfInterest.map((service) => (
              <label key={service} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  name="servicesOfInterest"
                  value={service}
                  checked={values.servicesOfInterest.includes(service)}
                  onChange={(e) =>
                    set(
                      "servicesOfInterest",
                      e.target.checked
                        ? [...values.servicesOfInterest, service]
                        : values.servicesOfInterest.filter(
                            (item) => item !== service,
                          ),
                    )
                  }
                  aria-invalid={invalid("servicesOfInterest")}
                  aria-describedby="servicesOfInterest-error"
                  className="h-4 w-4"
                />
                <span>{service}</span>
              </label>
            ))}
          </div>
          <FieldError
            name="servicesOfInterest"
            message={errors.servicesOfInterest}
          />
        </fieldset>

        <fieldset className="mt-6">
          <legend className="font-medium">
            Do you currently work with another 3PL? *
          </legend>
          <div
            role="radiogroup"
            aria-invalid={invalid("currentThreePL")}
            aria-describedby="currentThreePL-error"
            className="mt-2 space-y-2"
          >
            {OPTIONS.currentThreePL.map((option) => (
              <label key={option} className="flex items-center gap-2">
                <input
                  type="radio"
                  name="currentThreePL"
                  value={option}
                  checked={values.currentThreePL === option}
                  onChange={() => set("currentThreePL", option)}
                  className="h-4 w-4"
                />
                <span>{option}</span>
              </label>
            ))}
          </div>
          <FieldError name="currentThreePL" message={errors.currentThreePL} />
        </fieldset>

        <label className="mt-6 block">
          <span className="font-medium">Comments or specific needs</span>
          <textarea
            name="comments"
            rows={4}
            value={values.comments}
            onChange={(e) => set("comments", e.target.value)}
            onBlur={() => blur("comments")}
            aria-invalid={invalid("comments")}
            aria-describedby="comments-error comments-remaining"
            className={FIELD_CLASS}
          />
          <p
            id="comments-remaining"
            className={`mt-1 text-sm ${remaining < 0 ? "text-red-700" : "text-slate-600"}`}
          >
            {remaining} of {COMMENTS_LIMIT} characters remaining
          </p>
          <FieldError name="comments" message={errors.comments} />
        </label>
      </fieldset>

      <div className="rounded-lg border border-slate-200 p-6">
        <label className="flex items-start gap-3">
          <input
            type="checkbox"
            name="privacyPolicy"
            value="accepted"
            checked={values.privacyPolicy}
            onChange={(e) => set("privacyPolicy", e.target.checked)}
            aria-invalid={invalid("privacyPolicy")}
            aria-describedby="privacyPolicy-error"
            className="mt-1 h-4 w-4"
          />
          <span>
            I accept the privacy policy and consent to TrackFlow contacting me
            about this request. *
          </span>
        </label>
        <FieldError name="privacyPolicy" message={errors.privacyPolicy} />

        <button
          type="submit"
          className="mt-6 rounded-md bg-blue-800 px-6 py-3 text-base font-semibold text-white shadow-sm hover:bg-blue-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-800"
        >
          Send request
        </button>
      </div>
    </form>
  );
}
