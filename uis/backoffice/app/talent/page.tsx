import Link from "next/link";
import { Suspense } from "react";
import { CandidateFilters } from "@/components/talent/CandidateFilters";
import { CandidateList } from "@/components/talent/CandidateList";

export default function TalentPipelinePage() {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            People &amp; Talent
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-slate-900">
            Candidate pipeline
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-600">
            Review TrackFlow applicants, update their hiring stage, and keep
            internal recruiting notes in the same protected backoffice.
          </p>
        </div>
        <Link
          href="/talent/new"
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          Register candidate
        </Link>
      </div>

      <section
        aria-label="Active search"
        className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700"
      >
        <p>
          <span className="font-semibold text-slate-900">Active search:</span>{" "}
          Executive Assistant · Zaragoza headquarters
        </p>
        <p className="mt-1 text-slate-600">
          Profile: executive support experience, calendar and travel
          management, professional English, proficiency with office tools.
        </p>
      </section>

      <Suspense fallback={<div className="h-16 rounded-md bg-white" />}>
        <CandidateFilters />
      </Suspense>

      <Suspense fallback={<CandidateLoadingState />}>
        <CandidateList />
      </Suspense>
    </div>
  );
}

function CandidateLoadingState() {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
      Loading candidates…
    </div>
  );
}
