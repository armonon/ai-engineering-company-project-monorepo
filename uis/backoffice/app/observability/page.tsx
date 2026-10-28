import { AgentObservability } from "@/components/AgentObservability";

export default function ObservabilityPage() {
  return (
    <main className="mx-auto max-w-7xl p-6 lg:p-10">
      <p className="text-sm font-semibold uppercase tracking-widest text-blue-700">Operations</p>
      <h1 className="mt-2 text-3xl font-bold text-slate-950">Agent observability</h1>
      <p className="mt-2 max-w-3xl text-slate-600">
        Reconstruct live and historical work across the First-line CX agent and Commercial proposal pipeline.
      </p>
      <div className="mt-8"><AgentObservability /></div>
    </main>
  );
}
