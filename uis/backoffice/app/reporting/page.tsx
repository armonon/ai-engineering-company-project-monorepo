import { ReportingDashboard } from "@/components/ReportingDashboard";

export const metadata = { title: "Weekly performance reporting" };

export default function ReportingPage() {
  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm font-medium text-sky-700">Business performance</p>
        <h2 className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">
          Weekly Warehouse &amp; Client Performance Report
        </h2>
        <p className="mt-2 max-w-3xl text-sm text-slate-600">
          A decision-ready view of TrackFlow&apos;s completed-week inbound,
          outbound, stockout, and discrepancy activity.
        </p>
      </div>
      <ReportingDashboard />
    </div>
  );
}
