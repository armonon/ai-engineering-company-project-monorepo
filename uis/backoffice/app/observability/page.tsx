import { AgentObservability } from "@/components/AgentObservability";
import { PageHero } from "@/components/ui/Showcase";

export default function ObservabilityPage() {
  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <PageHero
        eyebrow="Operations"
        title="Agent observability"
        description="See what every TrackFlow agent is doing, reconstruct each run step by step, and pause, resume, or cancel live work."
      >
        <div className="flex flex-wrap gap-2 text-xs font-semibold">
          {["Live traces", "Human controls", "Full audit trail"].map((tag) => (
            <span key={tag} className="rounded-full bg-white/10 px-3 py-1.5 text-blue-100 ring-1 ring-inset ring-white/20 backdrop-blur">
              {tag}
            </span>
          ))}
        </div>
      </PageHero>
      <AgentObservability />
    </div>
  );
}
