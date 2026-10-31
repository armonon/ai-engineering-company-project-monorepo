/**
 * Pure presentation helpers for the RFP and observability screens: stage
 * mapping, human-readable labels, tones, and relative times. Kept free of
 * React so the rules shown on screen are unit-tested.
 */

export type Tone = "slate" | "amber" | "blue" | "violet" | "cyan" | "emerald" | "orange" | "red";

export const RFP_STAGES = ["Intake", "Drafts", "Evaluation", "Approvals", "Done"] as const;

export interface StageProgress {
  /** Index of the stage currently in progress, or RFP_STAGES.length when finished. */
  current: number;
  /** True while background work is running for the current stage. */
  working: boolean;
  discarded: boolean;
}

export function rfpProgress(status: string): StageProgress {
  switch (status) {
    case "analyzing":
      return { current: 0, working: true, discarded: false };
    case "intake_complete":
      return { current: 1, working: false, discarded: false };
    case "drafting":
      return { current: 1, working: true, discarded: false };
    case "under_evaluation":
    case "needs_human_review":
      return { current: 2, working: false, discarded: false };
    case "waiting_for_approval":
      return { current: 3, working: false, discarded: false };
    case "done":
      return { current: RFP_STAGES.length, working: false, discarded: false };
    case "discarded":
      return { current: 0, working: false, discarded: true };
    default:
      return { current: 0, working: false, discarded: false };
  }
}

/** Fraction of the stage track that is filled, 0..1. */
export function progressFraction(progress: StageProgress): number {
  if (progress.discarded) return 0;
  return Math.min(progress.current / (RFP_STAGES.length - 1), 1);
}

const STATUS_TONE: Record<string, Tone> = {
  analyzing: "amber",
  intake_complete: "blue",
  drafting: "blue",
  under_evaluation: "violet",
  needs_human_review: "orange",
  waiting_for_approval: "cyan",
  done: "emerald",
  discarded: "slate",
  running: "blue",
  idle: "slate",
  paused: "amber",
  completed: "emerald",
  cancelled: "red",
  failed: "red",
  waiting_for_human: "violet",
  approved: "emerald",
  rejected: "red",
  changes_requested: "amber",
};

const LIVE_STATUSES = new Set(["analyzing", "drafting", "running", "waiting_for_human"]);

export function statusTone(status: string): Tone {
  return STATUS_TONE[status] ?? "slate";
}

export function isLiveStatus(status: string): boolean {
  return LIVE_STATUSES.has(status);
}

const ACRONYMS: Record<string, string> = { rfp: "RFP", cx: "CX", api: "API", sse: "SSE", mcp: "MCP" };

export function humanize(value: string): string {
  const text = value
    .replaceAll("_", " ")
    .trim()
    .split(/\s+/)
    .map((word) => ACRONYMS[word.toLowerCase()] ?? word)
    .join(" ");
  return text ? text[0].toUpperCase() + text.slice(1) : text;
}

/** "rfp_ticket:6213ee4b-…" → "RFP ticket #6213ee4b". */
export function describeTrigger(trigger: string): string {
  const [kind, ref] = trigger.split(":", 2);
  return ref ? `${humanize(kind)} #${shortId(ref)}` : humanize(kind);
}

const DEPARTMENT_NAMES: Record<string, string> = {
  warehouse: "Warehouse Operations",
  reverse: "Reverse Logistics",
  lastmile: "Last Mile & Carriers",
  last_mile: "Last Mile & Carriers",
  cx: "Customer Experience",
  commercial: "Commercial",
};

export function departmentName(departmentId: string): string {
  return DEPARTMENT_NAMES[departmentId] ?? humanize(departmentId);
}

export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  const letters = words.length === 1 ? words[0].slice(0, 2) : words[0][0] + words[words.length - 1][0];
  return letters.toUpperCase();
}

const ACTION_LABELS: Record<string, string> = {
  query: "Request analyzed",
  draft_start: "Drafting started",
  intake: "Document received",
  classify: "Classified",
  route: "Routed to departments",
  retrieve: "Knowledge retrieved",
  write: "Draft written",
  evaluate: "Draft evaluated",
  approve: "Human approval",
  deliver: "Delivered",
  respond: "Reply sent",
  tool_call: "Company data looked up",
};

export function actionLabel(actionType: string): string {
  return ACTION_LABELS[actionType] ?? humanize(actionType);
}

const ACTION_TONES: Record<string, Tone> = {
  query: "amber",
  tool_call: "cyan",
  draft_start: "slate",
  intake: "amber",
  classify: "amber",
  route: "cyan",
  retrieve: "cyan",
  write: "blue",
  evaluate: "violet",
  approve: "orange",
  deliver: "emerald",
  respond: "emerald",
};

export function actionTone(actionType: string): Tone {
  return ACTION_TONES[actionType] ?? "slate";
}

export function shortId(id: string): string {
  const core = id.replace(/^[a-z]+[-_]/, "");
  return core.length > 8 ? core.slice(0, 8) : core;
}

export function relativeTime(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return "";
  const seconds = Math.round((now.getTime() - then.getTime()) / 1000);
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  return `${days} d ago`;
}
