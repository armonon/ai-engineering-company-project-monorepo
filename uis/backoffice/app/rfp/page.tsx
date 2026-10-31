import { RfpIntake } from "@/components/RfpIntake";
import { PageHero } from "@/components/ui/Showcase";

export default function RfpPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHero
        eyebrow="Commercial workflow"
        title="RFP intake and routing"
        description="Client proposals arrive, are read and routed to the right TrackFlow owners, drafted from approved knowledge, evaluated, and signed off department by department."
      >
        <div className="flex flex-wrap gap-2 text-xs font-semibold">
          {["Grounded drafts", "Independent approvals", "Live updates"].map((tag) => (
            <span key={tag} className="rounded-full bg-white/10 px-3 py-1.5 text-blue-100 ring-1 ring-inset ring-white/20 backdrop-blur">
              {tag}
            </span>
          ))}
        </div>
      </PageHero>
      <RfpIntake />
    </div>
  );
}
