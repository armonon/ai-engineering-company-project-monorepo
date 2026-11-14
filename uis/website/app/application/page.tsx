import type { Metadata } from "next";
import { ApplicationForm } from "@/components/ApplicationForm";

export const metadata: Metadata = {
  title: "Request information",
  description:
    "Tell TrackFlow about your company, your operation, and the logistics services you need. Our commercial team replies within 24-48 hours.",
  robots: { index: true, follow: true },
};

export default function ApplicationPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-16 sm:py-20">
      <h1 className="text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">
        Request information
      </h1>
      <p className="mt-4 text-lg leading-relaxed text-slate-700">
        Tell us about your operation and our commercial team will get back to
        you within 24-48 hours. Fields marked * are required.
      </p>
      <ApplicationForm />
    </div>
  );
}
