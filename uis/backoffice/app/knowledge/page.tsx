import { KnowledgeAssistant } from "@/components/KnowledgeAssistant";

export default function KnowledgePage() {
  return (
    <div className="space-y-5">
      <header>
        <p className="text-xs font-semibold uppercase tracking-wider text-blue-700 dark:text-blue-300">Sales enablement</p>
        <h1 className="mt-1 text-2xl font-bold text-slate-950 dark:text-white">TrackFlow knowledge assistant</h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-600 dark:text-slate-300">
          Policy-grounded answers for client conversations. When the approved documents do not contain an answer, the assistant says so instead of guessing.
        </p>
      </header>
      <KnowledgeAssistant />
    </div>
  );
}
