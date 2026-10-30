import { authJson } from "@/lib/auth";

export interface EventsPerDayRow {
  date: string;
  event_type: string;
  count: number;
}

export interface ErrorRateRow {
  date: string;
  service: string;
  total_events: number;
  error_events: number;
  error_rate: number;
}

export interface LatencyRow {
  date: string;
  endpoint_template: string;
  samples: number;
  mean_duration_ms: number;
}

export interface AuthFailureRow {
  date: string;
  attempts: number;
  failures: number;
  failure_rate: number;
}

export interface TelemetryReport {
  period: { from: string; to: string };
  metrics: {
    events_per_day: EventsPerDayRow[];
    error_rate_by_day: ErrorRateRow[];
    latency_by_endpoint: LatencyRow[];
    auth_failure_rate: AuthFailureRow[];
  };
}

export interface TelemetrySummary {
  total_events: number;
  error_rate: number;
  auth_failure_rate: number;
  slowest_endpoint: { endpoint_template: string; mean_duration_ms: number } | null;
}

/** Defaults to the API's rolling seven-day window when no bounds are given. */
export function fetchTelemetryReport(range?: {
  start_date: string;
  end_date: string;
}): Promise<TelemetryReport> {
  const query = range ? `?${new URLSearchParams(range).toString()}` : "";
  return authJson<TelemetryReport>(`/telemetry/report${query}`);
}

/**
 * Period-level totals are weighted by their populations (events, attempts,
 * samples) rather than averaging the daily rates.
 */
export function summarizeTelemetry(report: TelemetryReport): TelemetrySummary {
  const { metrics } = report;
  const sum = <T,>(rows: T[], pick: (row: T) => number) =>
    rows.reduce((total, row) => total + pick(row), 0);

  const totalLogged = sum(metrics.error_rate_by_day, (row) => row.total_events);
  const errors = sum(metrics.error_rate_by_day, (row) => row.error_events);
  const attempts = sum(metrics.auth_failure_rate, (row) => row.attempts);
  const failures = sum(metrics.auth_failure_rate, (row) => row.failures);

  const byEndpoint = new Map<string, { samples: number; total: number }>();
  for (const row of metrics.latency_by_endpoint) {
    const current = byEndpoint.get(row.endpoint_template) ?? { samples: 0, total: 0 };
    current.samples += row.samples;
    current.total += row.mean_duration_ms * row.samples;
    byEndpoint.set(row.endpoint_template, current);
  }
  let slowest: TelemetrySummary["slowest_endpoint"] = null;
  for (const [endpoint_template, { samples, total }] of byEndpoint) {
    const mean = total / samples;
    if (!slowest || mean > slowest.mean_duration_ms) {
      slowest = { endpoint_template, mean_duration_ms: mean };
    }
  }

  return {
    total_events: sum(metrics.events_per_day, (row) => row.count),
    error_rate: totalLogged ? errors / totalLogged : 0,
    auth_failure_rate: attempts ? failures / attempts : 0,
    slowest_endpoint: slowest,
  };
}
