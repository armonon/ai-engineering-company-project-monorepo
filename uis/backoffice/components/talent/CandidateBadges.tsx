import {
  STAGE_LABELS,
  STATUS_LABELS,
  type CandidateStage,
  type CandidateStatus,
} from "@/lib/talent";

const STATUS_STYLES: Record<CandidateStatus, string> = {
  received: "border-slate-300 bg-slate-100 text-slate-700",
  in_progress: "border-blue-300 bg-blue-100 text-blue-800",
  selected: "border-emerald-300 bg-emerald-100 text-emerald-800",
  discarded: "border-red-300 bg-red-100 text-red-800",
};

const STAGE_STYLES: Record<CandidateStage, string> = {
  pending: "border-slate-300 bg-slate-100 text-slate-700",
  review: "border-amber-300 bg-amber-100 text-amber-800",
  personal_interview: "border-indigo-300 bg-indigo-100 text-indigo-800",
  technical_interview: "border-purple-300 bg-purple-100 text-purple-800",
  offer_presented: "border-emerald-300 bg-emerald-100 text-emerald-800",
};

export function StatusBadge({ value }: { value: CandidateStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[value]}`}
    >
      {STATUS_LABELS[value]}
    </span>
  );
}

export function StageBadge({ value }: { value: CandidateStage }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${STAGE_STYLES[value]}`}
    >
      {STAGE_LABELS[value]}
    </span>
  );
}
