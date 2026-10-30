import { authJson } from "@/lib/auth";
import {
  fetchTelemetryReport,
  summarizeTelemetry,
  type TelemetryReport,
} from "@/lib/telemetry-report";

jest.mock("@/lib/auth", () => ({ authJson: jest.fn() }));

const mockedAuthJson = jest.mocked(authJson);

beforeEach(() => mockedAuthJson.mockReset());

// Mirrors the hand-checked rows asserted by services/api/tests/test_telemetry_report.py.
const REPORT: TelemetryReport = {
  period: { from: "2026-10-01T00:00:00+00:00", to: "2026-10-03T00:00:00+00:00" },
  metrics: {
    events_per_day: [
      { date: "2026-10-01", event_type: "login_failed", count: 1 },
      { date: "2026-10-01", event_type: "login_succeeded", count: 2 },
      { date: "2026-10-01", event_type: "api_error_returned", count: 1 },
      { date: "2026-10-01", event_type: "api_latency_recorded", count: 3 },
      { date: "2026-10-02", event_type: "page_viewed", count: 1 },
    ],
    error_rate_by_day: [
      { date: "2026-10-01", service: "api", total_events: 7, error_events: 1, error_rate: 1 / 7 },
      { date: "2026-10-02", service: "api", total_events: 1, error_events: 0, error_rate: 0 },
    ],
    latency_by_endpoint: [
      { date: "2026-10-01", endpoint_template: "/a", samples: 2, mean_duration_ms: 200 },
      { date: "2026-10-01", endpoint_template: "/b", samples: 1, mean_duration_ms: 900 },
    ],
    auth_failure_rate: [
      { date: "2026-10-01", attempts: 3, failures: 1, failure_rate: 1 / 3 },
    ],
  },
};

describe("telemetry report client", () => {
  it("loads the authenticated rolling-window report by default", async () => {
    mockedAuthJson.mockResolvedValue(REPORT);
    await fetchTelemetryReport();
    expect(mockedAuthJson).toHaveBeenCalledWith("/telemetry/report");
  });

  it("encodes an explicit ISO 8601 window", async () => {
    mockedAuthJson.mockResolvedValue(REPORT);
    await fetchTelemetryReport({ start_date: "2026-10-01", end_date: "2026-10-03" });
    expect(mockedAuthJson).toHaveBeenCalledWith(
      "/telemetry/report?start_date=2026-10-01&end_date=2026-10-03",
    );
  });

  it("weights period totals by population instead of averaging daily rates", () => {
    expect(summarizeTelemetry(REPORT)).toEqual({
      total_events: 8,
      error_rate: 1 / 8,
      auth_failure_rate: 1 / 3,
      slowest_endpoint: { endpoint_template: "/b", mean_duration_ms: 900 },
    });
  });

  it("returns honest zeros and no endpoint for an empty period", () => {
    expect(
      summarizeTelemetry({
        period: REPORT.period,
        metrics: {
          events_per_day: [],
          error_rate_by_day: [],
          latency_by_endpoint: [],
          auth_failure_rate: [],
        },
      }),
    ).toEqual({ total_events: 0, error_rate: 0, auth_failure_rate: 0, slowest_endpoint: null });
  });
});
