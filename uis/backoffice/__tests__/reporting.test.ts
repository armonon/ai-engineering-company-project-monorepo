import { authJson } from "@/lib/auth";
import {
  aggregateWeeklyPerformance,
  fetchWeeklyPerformance,
  reportingPeriod,
  warehouseLabel,
} from "@/lib/reporting";
import { KPI_CARDS } from "@/components/ReportingDashboard";

jest.mock("@/lib/auth", () => ({ authJson: jest.fn() }));

const mockedAuthJson = jest.mocked(authJson);

beforeEach(() => {
  mockedAuthJson.mockReset();
});

describe("TrackFlow reporting API", () => {
  it("loads the authenticated weekly warehouse/client endpoint", async () => {
    mockedAuthJson.mockResolvedValue({ week_start: null, entries: [] });

    await fetchWeeklyPerformance();

    expect(mockedAuthJson).toHaveBeenCalledWith(
      "/reporting/weekly-warehouse-client-performance",
    );
  });

  it("encodes an explicitly selected week", async () => {
    mockedAuthJson.mockResolvedValue({ week_start: null, entries: [] });

    await fetchWeeklyPerformance("2026-07-13");

    expect(mockedAuthJson).toHaveBeenCalledWith(
      "/reporting/weekly-warehouse-client-performance?week_start=2026-07-13",
    );
  });
});

describe("reporting presentation", () => {
  it("uses the four exact business KPI names from the TrackFlow briefing", () => {
    expect(KPI_CARDS.map(({ label }) => label)).toEqual([
      "Inbound Volume",
      "Outbound Throughput",
      "Stockout Frequency",
      "Discrepancy Rate",
    ]);
  });

  it("shows the complete Monday-through-Sunday UTC period", () => {
    expect(reportingPeriod("2026-07-13")).toEqual({
      start: "2026-07-13",
      end: "2026-07-19",
    });
  });

  it("uses TrackFlow's warehouse vocabulary", () => {
    expect(warehouseLabel("los_angeles")).toBe("Los Angeles");
    expect(warehouseLabel("zaragoza")).toBe("Zaragoza");
  });

  it("calculates the hand-checked aggregate discrepancy rate", () => {
    const totals = aggregateWeeklyPerformance([
      {
        warehouse: "los_angeles",
        client_id: "client-a",
        inbound_units_count: 12,
        outbound_orders_count: 3,
        stockout_events_count: 1,
        discrepancy_events_count: 2,
        discrepancy_rate: 2 / 3,
      },
      {
        warehouse: "zaragoza",
        client_id: "client-b",
        inbound_units_count: 8,
        outbound_orders_count: 1,
        stockout_events_count: 0,
        discrepancy_events_count: 0,
        discrepancy_rate: 0,
      },
    ]);

    expect(totals).toEqual({
      inbound_units_count: 20,
      outbound_orders_count: 4,
      stockout_events_count: 1,
      discrepancy_events_count: 2,
      discrepancy_rate: 0.5,
    });
  });
});
