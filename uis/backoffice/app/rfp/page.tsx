import { RfpIntake } from "@/components/RfpIntake";

export default function RfpPage() {
  return (
    <div className="space-y-5">
      <header>
        <p className="text-xs font-semibold uppercase tracking-wider text-blue-700">Commercial workflow</p>
        <h1 className="mt-1 text-2xl font-bold text-slate-950">RFP intake and routing</h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-600">
          Upload client proposals, monitor ticket status, and see the exact TrackFlow departments and owners needed for the response.
        </p>
      </header>
      <RfpIntake />
    </div>
  );
}
