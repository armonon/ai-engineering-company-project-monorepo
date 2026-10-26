import { authJson } from "@/lib/auth";

export interface WeeklyPerformanceEntry {
  warehouse: string;
  client_id: string;
  inbound_units_count: number;
  outbound_orders_count: number;
  stockout_events_count: number;
  discrepancy_events_count: number;
  discrepancy_rate: number;
}

export interface WeeklyPerformanceResponse {
  week_start: string | null;
  entries: WeeklyPerformanceEntry[];
}

export interface WeeklyPerformanceTotals {
  inbound_units_count: number;
  outbound_orders_count: number;
  stockout_events_count: number;
  discrepancy_events_count: number;
  discrepancy_rate: number;
}

export function fetchWeeklyPerformance(
  weekStart?: string,
): Promise<WeeklyPerformanceResponse> {
  const query = weekStart
    ? `?week_start=${encodeURIComponent(weekStart)}`
    : "";
  return authJson<WeeklyPerformanceResponse>(
    `/reporting/weekly-warehouse-client-performance${query}`,
  );
}

function isoDateAtUtc(value: string): Date {
  const parts = value.split("-").map(Number);
  if (
    parts.length !== 3 ||
    parts.some((part) => !Number.isInteger(part))
  ) {
    throw new Error("Invalid reporting week date");
  }
  return new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
}

function toIsoDate(value: Date): string {
  return value.toISOString().slice(0, 10);
}

export function reportingPeriod(weekStart: string): {
  start: string;
  end: string;
} {
  const start = isoDateAtUtc(weekStart);
  const end = new Date(start);
  end.setUTCDate(end.getUTCDate() + 6);
  return { start: toIsoDate(start), end: toIsoDate(end) };
}

export function warehouseLabel(value: string): string {
  if (value === "los_angeles") return "Los Angeles";
  if (value === "zaragoza") return "Zaragoza";
  return value.replaceAll("_", " ");
}

export function aggregateWeeklyPerformance(
  entries: WeeklyPerformanceEntry[],
): WeeklyPerformanceTotals {
  const totals = entries.reduce(
    (current, entry) => ({
      inbound_units_count:
        current.inbound_units_count + entry.inbound_units_count,
      outbound_orders_count:
        current.outbound_orders_count + entry.outbound_orders_count,
      stockout_events_count:
        current.stockout_events_count + entry.stockout_events_count,
      discrepancy_events_count:
        current.discrepancy_events_count + entry.discrepancy_events_count,
      discrepancy_rate: 0,
    }),
    {
      inbound_units_count: 0,
      outbound_orders_count: 0,
      stockout_events_count: 0,
      discrepancy_events_count: 0,
      discrepancy_rate: 0,
    },
  );
  totals.discrepancy_rate = totals.outbound_orders_count
    ? totals.discrepancy_events_count / totals.outbound_orders_count
    : 0;
  return totals;
}
