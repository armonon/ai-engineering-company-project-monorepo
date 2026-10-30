"use client";

import { useCallback, useEffect, useState } from "react";
import { toUserMessage } from "@/lib/errors";
import {
  fetchTelemetryReport,
  summarizeTelemetry,
  type TelemetryReport,
} from "@/lib/telemetry-report";

const percent = new Intl.NumberFormat("en-US", {
  style: "percent",
  maximumFractionDigits: 1,
});
const count = new Intl.NumberFormat("en-US");

export function TelemetryReportView() {
  const [report, setReport] = useState<TelemetryReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadReport = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setReport(await fetchTelemetryReport());
    } catch (caught) {
      setError(toUserMessage(caught, "We couldn't load the telemetry report."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void loadReport());
  }, [loadReport]);

  if (loading) {
    return (
      <p className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-600">
        Loading application telemetry…
      </p>
    );
  }

  if (error || !report) {
    return (
      <div
        role="alert"
        className="rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-900"
      >
        <p className="font-medium">The telemetry report is unavailable</p>
        <p className="mt-1">{error}</p>
        <button
          type="button"
          onClick={() => void loadReport()}
          className="mt-4 rounded-md border border-red-300 bg-white px-3 py-2 font-medium hover:bg-red-100"
        >
          Try again
        </button>
      </div>
    );
  }

  const summary = summarizeTelemetry(report);
  const cards = [
    { label: "Events recorded", value: count.format(summary.total_events) },
    { label: "Error-level share", value: percent.format(summary.error_rate) },
    { label: "Sign-in failure rate", value: percent.format(summary.auth_failure_rate) },
    {
      label: "Slowest endpoint (mean)",
      value: summary.slowest_endpoint
        ? `${Math.round(summary.slowest_endpoint.mean_duration_ms)} ms`
        : "—",
      detail: summary.slowest_endpoint?.endpoint_template,
    },
  ];

  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-600">
        {report.period.from.slice(0, 10)} through {report.period.to.slice(0, 10)} (UTC)
      </p>

      <section aria-label="Telemetry totals" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <article key={card.label} className="rounded-lg border border-slate-200 bg-white p-4">
            <p className="text-xs font-medium text-slate-600">{card.label}</p>
            <p className="mt-2 text-2xl font-semibold text-slate-950">{card.value}</p>
            {card.detail && (
              <p className="mt-2 font-mono text-xs text-slate-500">{card.detail}</p>
            )}
          </article>
        ))}
      </section>

      <section className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <h3 className="border-b border-slate-200 px-5 py-4 font-semibold text-slate-900">
          API latency by endpoint
        </h3>
        {report.metrics.latency_by_endpoint.length === 0 ? (
          <p className="px-5 py-4 text-sm text-slate-600">No latency samples in this period.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
                <tr>
                  <th scope="col" className="px-4 py-3">Date</th>
                  <th scope="col" className="px-4 py-3">Endpoint</th>
                  <th scope="col" className="px-4 py-3">Samples</th>
                  <th scope="col" className="px-4 py-3">Mean duration</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {report.metrics.latency_by_endpoint.map((row) => (
                  <tr key={`${row.date}:${row.endpoint_template}`}>
                    <td className="whitespace-nowrap px-4 py-3">{row.date}</td>
                    <td className="px-4 py-3 font-mono text-xs">{row.endpoint_template}</td>
                    <td className="px-4 py-3">{row.samples}</td>
                    <td className="px-4 py-3">{Math.round(row.mean_duration_ms)} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
