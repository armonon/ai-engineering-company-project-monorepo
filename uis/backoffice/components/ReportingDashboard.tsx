"use client";

import { useCallback, useEffect, useState } from "react";
import { toUserMessage } from "@/lib/errors";
import {
  aggregateWeeklyPerformance,
  fetchWeeklyPerformance,
  reportingPeriod,
  warehouseLabel,
  type WeeklyPerformanceResponse,
  type WeeklyPerformanceTotals,
} from "@/lib/reporting";

export const KPI_CARDS: {
  field: keyof WeeklyPerformanceTotals;
  label: string;
  description: string;
}[] = [
  {
    field: "inbound_units_count",
    label: "Inbound Volume",
    description: "Units received across TrackFlow warehouses",
  },
  {
    field: "outbound_orders_count",
    label: "Outbound Throughput",
    description: "Distinct outbound orders dispatched",
  },
  {
    field: "stockout_events_count",
    label: "Stockout Frequency",
    description: "Minimum-stock threshold events",
  },
  {
    field: "discrepancy_rate",
    label: "Discrepancy Rate",
    description: "Discrepancies divided by outbound orders",
  },
];

function displayKpi(
  field: keyof WeeklyPerformanceTotals,
  value: number,
): string {
  return field === "discrepancy_rate"
    ? new Intl.NumberFormat("en-US", {
        style: "percent",
        maximumFractionDigits: 1,
      }).format(value)
    : new Intl.NumberFormat("en-US").format(value);
}

export function ReportingDashboard() {
  const [report, setReport] = useState<WeeklyPerformanceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadReport = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setReport(await fetchWeeklyPerformance());
    } catch (caught) {
      setError(
        toUserMessage(
          caught,
          "We couldn't load the weekly warehouse and client report.",
        ),
      );
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
        Loading weekly warehouse and client performance…
      </p>
    );
  }

  if (error) {
    return (
      <div
        role="alert"
        className="rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-900"
      >
        <p className="font-medium">The report is unavailable</p>
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

  if (!report?.week_start || report.entries.length === 0) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-8 text-center">
        <h3 className="font-semibold text-slate-900">No completed weekly report yet</h3>
        <p className="mx-auto mt-2 max-w-xl text-sm text-slate-600">
          Run the weekly warehouse and client performance pipeline after the
          first completed UTC week. This view will then show the published KPIs.
        </p>
      </div>
    );
  }

  const period = reportingPeriod(report.week_start);
  const totals = aggregateWeeklyPerformance(report.entries);

  return (
    <div className="space-y-6">
      <section
        aria-labelledby="report-period"
        className="rounded-lg border border-slate-200 bg-white p-5"
      >
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Reporting period
        </p>
        <h3 id="report-period" className="mt-1 text-xl font-semibold text-slate-900">
          {period.start} through {period.end} (UTC)
        </h3>
        <p className="mt-1 text-sm text-slate-600">
          Completed-week warehouse and client activity, grouped by the approved
          TrackFlow business dimensions.
        </p>
      </section>

      <section
        aria-label="Weekly KPI totals"
        className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5"
      >
        {KPI_CARDS.map((kpi) => (
          <article key={kpi.field} className="rounded-lg border border-slate-200 bg-white p-4">
            <p className="text-xs font-medium text-slate-600">{kpi.label}</p>
            <p className="mt-2 text-2xl font-semibold text-slate-950">
              {displayKpi(kpi.field, totals[kpi.field])}
            </p>
            <p className="mt-2 text-xs text-slate-500">{kpi.description}</p>
          </article>
        ))}
      </section>

      <section className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-5 py-4">
          <h3 className="font-semibold text-slate-900">Warehouse and client detail</h3>
          <p className="mt-1 text-sm text-slate-600">
            Each row is one warehouse, client, and UTC ISO week.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
              <tr>
                <th scope="col" className="px-4 py-3">Warehouse</th>
                <th scope="col" className="px-4 py-3">Client ID</th>
                <th scope="col" className="px-4 py-3">Inbound units</th>
                <th scope="col" className="px-4 py-3">Outbound orders</th>
                <th scope="col" className="px-4 py-3">Stockout events</th>
                <th scope="col" className="px-4 py-3">Discrepancy events</th>
                <th scope="col" className="px-4 py-3">Discrepancy rate</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {report.entries.map((entry) => (
                <tr key={`${entry.warehouse}:${entry.client_id}`}>
                  <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-900">
                    {warehouseLabel(entry.warehouse)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-slate-600">
                    {entry.client_id}
                  </td>
                  <td className="px-4 py-3">{entry.inbound_units_count}</td>
                  <td className="px-4 py-3">{entry.outbound_orders_count}</td>
                  <td className="px-4 py-3">{entry.stockout_events_count}</td>
                  <td className="px-4 py-3">{entry.discrepancy_events_count}</td>
                  <td className="px-4 py-3">
                    {displayKpi("discrepancy_rate", entry.discrepancy_rate)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
