"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { toUserMessage } from "@/lib/errors";
import { candidatesService } from "@/lib/talent-api";
import type {
  Candidate,
  CandidateStage,
  CandidateStatus,
} from "@/lib/talent";
import { StageBadge, StatusBadge } from "./CandidateBadges";

export function CandidateList() {
  const searchParams = useSearchParams();
  const status = searchParams.get("status") ?? "";
  const stage = searchParams.get("stage") ?? "";
  const search = searchParams.get("search") ?? "";
  const [data, setData] = useState<Candidate[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (!cancelled) {
        setLoading(true);
        setError(null);
      }
    });

    candidatesService
      .list({
        status: (status as CandidateStatus) || "",
        stage: (stage as CandidateStage) || "",
        search,
        limit: 100,
      })
      .then((response) => {
        if (!cancelled) {
          setData(response.data);
          setTotal(response.total);
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(toUserMessage(reason, "Failed to load candidates"));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [status, stage, search]);

  if (loading) {
    return <TalentState>Loading candidates…</TalentState>;
  }

  if (error) {
    return (
      <div
        role="alert"
        className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700"
      >
        <strong>Couldn&apos;t load candidates.</strong> {error}
      </div>
    );
  }

  if (data.length === 0) {
    return <TalentState>No candidates match the current filters.</TalentState>;
  }

  return (
    <div className="overflow-hidden rounded-md border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 bg-slate-50 px-4 py-2 text-xs text-slate-600">
        Showing {data.length} of {total} candidates
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">Name</th>
              <th className="px-4 py-2 font-medium">Position</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Pipeline stage</th>
              <th className="px-4 py-2 font-medium">Applied</th>
              <th className="px-4 py-2">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.map((candidate) => (
              <tr key={candidate.id} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <div className="font-medium text-slate-900">
                    {candidate.full_name}
                  </div>
                  <div className="text-xs text-slate-500">
                    {candidate.email}
                  </div>
                </td>
                <td className="px-4 py-3 text-slate-700">
                  {candidate.position}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge value={candidate.status} />
                </td>
                <td className="px-4 py-3">
                  <StageBadge value={candidate.stage} />
                </td>
                <td className="px-4 py-3 text-slate-500">
                  {formatDate(candidate.applied_at)}
                </td>
                <td className="px-4 py-3 text-right">
                  <Link
                    href={`/talent/${candidate.id}`}
                    className="font-medium text-slate-900 hover:underline"
                  >
                    View →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TalentState({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
      {children}
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
