import { Suspense } from "react";
import { CandidateList } from "@/components/CandidateList";
import { Filters } from "@/components/Filters";

export default function HomePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">
          Candidate pipeline
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          All applicants across TrackFlow&apos;s open roles. Filter, search, and
          open a candidate to update their status or add notes.
        </p>
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
        <Filters />
      </Suspense>

      <Suspense
        fallback={
          <div className="rounded-md border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
            Loading candidates…
          </div>
        }
      >
        <CandidateList />
      </Suspense>
    </div>
  );
}
