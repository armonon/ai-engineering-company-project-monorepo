import { SupportChat } from "@/components/SupportChat";
import { PageHero } from "@/components/ui/Showcase";

export default function SupportPage() {
  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <PageHero
        eyebrow="Live customer support"
        title="First-line CX agent"
        description="Customers ask where their parcel is and get a live answer from TrackFlow's systems, streamed word by word. Send a correction mid-answer to interrupt it and redirect the next turn."
      >
        <div className="flex flex-wrap gap-2 text-xs font-semibold">
          {["Live ticket lookups", "Guardrails", "Interrupt anytime"].map((tag) => (
            <span key={tag} className="rounded-full bg-white/10 px-3 py-1.5 text-blue-100 ring-1 ring-inset ring-white/20 backdrop-blur">
              {tag}
            </span>
          ))}
        </div>
      </PageHero>
      <SupportChat />
    </div>
  );
}
