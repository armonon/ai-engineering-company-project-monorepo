"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import { CandidateNotes } from "@/components/talent/CandidateNotes";
import { StageBadge, StatusBadge } from "@/components/talent/CandidateBadges";
import { CandidateStatusControls } from "@/components/talent/CandidateStatusControls";
import {
  TalentToast,
  type ToastMessage,
} from "@/components/talent/TalentToast";
import { toUserMessage } from "@/lib/errors";
import { safeExternalUrl, type Candidate } from "@/lib/talent";
import { candidatesService } from "@/lib/talent-api";

interface CandidateDetailPageProps {
  params: Promise<{ id: string }>;
}

export default function CandidateDetailPage({
  params,
}: CandidateDetailPageProps) {
  const { id } = use(params);
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastMessage | null>(null);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (!cancelled) {
        setLoading(true);
        setError(null);
      }
    });
    candidatesService
      .get(id)
      .then((response) => {
        if (!cancelled) setCandidate(response);
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(toUserMessage(reason, "Failed to load candidate"));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  const onSuccess = useCallback(
    (text: string) => setToast({ kind: "success", text }),
    [],
  );
  const onError = useCallback(
    (text: string) => setToast({ kind: "error", text }),
    [],
  );

  if (loading) {
    return <CandidateState>Loading candidate…</CandidateState>;
  }

  if (error || !candidate) {
    return (
      <div className="space-y-4">
        <BackToCandidates />
        <div
          role="alert"
          className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700"
        >
          {error ?? "Candidate not found"}
        </div>
      </div>
    );
  }

  const linkedInUrl = safeExternalUrl(candidate.linkedin_url);
  const cvUrl = safeExternalUrl(candidate.cv_url);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <BackToCandidates />
        <Link
          href={`/talent/${candidate.id}/edit`}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Edit candidate
        </Link>
      </div>

      <section className="rounded-md border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          People &amp; Talent
        </p>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">
              {candidate.full_name}
            </h1>
            <p className="mt-1 text-sm text-slate-600">
              Applied for{" "}
              <span className="font-medium text-slate-800">
                {candidate.position}
              </span>{" "}
              on {formatDate(candidate.applied_at)}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusBadge value={candidate.status} />
            <StageBadge value={candidate.stage} />
          </div>
        </div>

        <dl className="mt-6 grid gap-4 text-sm sm:grid-cols-2">
          <Info label="Email" value={candidate.email} />
          <Info label="Phone" value={candidate.phone} />
          <Info
            label="Years of experience"
            value={String(candidate.experience_years)}
          />
          <Info label="Last updated" value={formatDate(candidate.updated_at)} />
          <Info
            label="LinkedIn"
            value={
              linkedInUrl ? (
                <a
                  href={linkedInUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-slate-900 underline hover:no-underline"
                >
                  {linkedInUrl}
                </a>
              ) : (
                <span className="text-slate-400">—</span>
              )
            }
          />
          <Info
            label="CV"
            value={
              cvUrl ? (
                <a
                  href={cvUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-slate-900 underline hover:no-underline"
                >
                  Open CV
                </a>
              ) : (
                <span className="text-slate-400">—</span>
              )
            }
          />
        </dl>
      </section>

      <section className="rounded-md border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Update pipeline
        </h2>
        <CandidateStatusControls
          candidateId={candidate.id}
          status={candidate.status}
          stage={candidate.stage}
          onUpdated={(patch) =>
            setCandidate((current) =>
              current ? { ...current, ...patch } : current,
            )
          }
          onError={onError}
          onSuccess={onSuccess}
        />
      </section>

      <section className="rounded-md border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Internal notes
        </h2>
        <CandidateNotes
          candidateId={candidate.id}
          onError={onError}
          onSuccess={onSuccess}
        />
      </section>

      <TalentToast message={toast} onDismiss={() => setToast(null)} />
    </div>
  );
}

function BackToCandidates() {
  return (
    <Link href="/talent" className="text-sm text-slate-600 hover:underline">
      ← Back to candidates
    </Link>
  );
}

function CandidateState({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-8 text-sm text-slate-500">
      {children}
    </div>
  );
}

function Info({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-0.5 text-slate-800">{value}</dd>
    </div>
  );
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
