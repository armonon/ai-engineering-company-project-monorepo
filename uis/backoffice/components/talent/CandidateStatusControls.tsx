"use client";

import { useState } from "react";
import { toUserMessage } from "@/lib/errors";
import {
  STAGE_LABELS,
  STAGE_OPTIONS,
  STATUS_LABELS,
  STATUS_OPTIONS,
  type CandidateStage,
  type CandidateStatus,
} from "@/lib/talent";
import { candidatesService } from "@/lib/talent-api";

interface CandidateStatusControlsProps {
  candidateId: string;
  status: CandidateStatus;
  stage: CandidateStage;
  onUpdated: (patch: {
    status?: CandidateStatus;
    stage?: CandidateStage;
  }) => void;
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
}

export function CandidateStatusControls({
  candidateId,
  status,
  stage,
  onUpdated,
  onError,
  onSuccess,
}: CandidateStatusControlsProps) {
  const [savingField, setSavingField] = useState<"status" | "stage" | null>(
    null,
  );

  async function updateStatus(next: CandidateStatus) {
    if (next === status) return;
    setSavingField("status");
    try {
      const updated = await candidatesService.patch(candidateId, {
        status: next,
      });
      onUpdated({ status: updated.status });
      onSuccess("Status updated");
    } catch (error) {
      onError(toUserMessage(error, "Failed to update status"));
    } finally {
      setSavingField(null);
    }
  }

  async function updateStage(next: CandidateStage) {
    if (next === stage) return;
    setSavingField("stage");
    try {
      const updated = await candidatesService.patch(candidateId, {
        stage: next,
      });
      onUpdated({ stage: updated.stage });
      onSuccess("Stage updated");
    } catch (error) {
      onError(toUserMessage(error, "Failed to update stage"));
    } finally {
      setSavingField(null);
    }
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <label className="block">
        <span className="mb-1 block text-xs font-medium text-slate-600">
          Status {savingField === "status" && <em>(saving…)</em>}
        </span>
        <select
          value={status}
          disabled={savingField !== null}
          onChange={(event) =>
            void updateStatus(event.target.value as CandidateStatus)
          }
          className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-400 disabled:opacity-60"
        >
          {STATUS_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {STATUS_LABELS[option]}
            </option>
          ))}
        </select>
      </label>

      <label className="block">
        <span className="mb-1 block text-xs font-medium text-slate-600">
          Pipeline stage {savingField === "stage" && <em>(saving…)</em>}
        </span>
        <select
          value={stage}
          disabled={savingField !== null}
          onChange={(event) =>
            void updateStage(event.target.value as CandidateStage)
          }
          className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-400 disabled:opacity-60"
        >
          {STAGE_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {STAGE_LABELS[option]}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
