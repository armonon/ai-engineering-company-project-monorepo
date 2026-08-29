"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CandidateForm } from "@/components/talent/CandidateForm";
import {
  TalentToast,
  type ToastMessage,
} from "@/components/talent/TalentToast";
import { toUserMessage } from "@/lib/errors";
import type { Candidate } from "@/lib/talent";
import { candidatesService } from "@/lib/talent-api";

interface EditCandidatePageProps {
  params: Promise<{ id: string }>;
}

export default function EditCandidatePage({ params }: EditCandidatePageProps) {
  const { id } = use(params);
  const router = useRouter();
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

  return (
    <div className="space-y-6">
      <Link
        href={`/talent/${id}`}
        className="text-sm text-slate-600 hover:underline"
      >
        ← Back to candidate
      </Link>

      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          People &amp; Talent
        </p>
        <h1 className="mt-1 text-2xl font-semibold text-slate-900">
          Edit candidate
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Correct or update this applicant&apos;s information.
        </p>
      </div>

      {loading && (
        <div className="rounded-md border border-slate-200 bg-white p-6 text-sm text-slate-500">
          Loading candidate…
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700"
        >
          {error}
        </div>
      )}

      {candidate && (
        <div className="rounded-md border border-slate-200 bg-white p-6 shadow-sm">
          <CandidateForm
            initial={candidate}
            submitLabel="Save changes"
            onCancel={() => router.push(`/talent/${id}`)}
            onSubmit={async (data) => {
              try {
                const updated = await candidatesService.replace(id, data);
                setCandidate(updated);
                setToast({ kind: "success", text: "Candidate updated" });
                router.push(`/talent/${id}`);
              } catch (reason) {
                setToast({
                  kind: "error",
                  text: toUserMessage(reason, "Failed to update candidate"),
                });
              }
            }}
          />
        </div>
      )}

      <TalentToast message={toast} onDismiss={() => setToast(null)} />
    </div>
  );
}
