import { TelemetryReportView } from "@/components/TelemetryReportView";

export const metadata = { title: "Application telemetry" };

export default function TelemetryPage() {
  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm font-medium text-sky-700">Platform health</p>
        <h2 className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">
          Application telemetry
        </h2>
        <p className="mt-2 max-w-3xl text-sm text-slate-600">
          Event traffic, error-level share, API latency, and sign-in failures
          from TrackFlow&apos;s approved telemetry catalogue for the last seven
          days (UTC).
        </p>
      </div>
      <TelemetryReportView />
    </div>
  );
}
