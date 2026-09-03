const PAGE_VIEW = {
  route_template: "/backoffice/inventory/products",
  section: "inventory",
  previous_section: "direct",
  viewport_class: "desktop",
};

const INVENTORY = {
  warehouse: "los_angeles",
  client_id: "client_01JTF000000000000000000001",
  product_id: "CLT-SNK-W-42",
  product_category: "fashion",
};

const ALL_EVENT_PROPERTIES: Record<string, Record<string, unknown>> = {
  inbound_order_created: { ...INVENTORY, quantity: 10, order_id: "1", stock_after: 20, reference_present: true },
  outbound_order_created: { ...INVENTORY, quantity: 2, order_id: "2", exit_type: "dispatch", stock_after: 18, tracking_present: true },
  inventory_loss_recorded: { ...INVENTORY, quantity: 1, order_id: "3", exit_type: "loss", stock_after: 17 },
  stock_threshold_triggered: { ...INVENTORY, quantity: 9, threshold_quantity: 10, previous_quantity: 11, trigger_source: "outbound_order" },
  direct_stock_edit_rejected: { ...INVENTORY, quantity: 99, attempted_operation: "set", endpoint_template: "/inventory/products/{id}", reason_code: "stock_is_derived" },
  inventory_discrepancy_detected: { ...INVENTORY, quantity: 3, audit_id: "audit-1", system_quantity: 20, physical_quantity: 17, variance_quantity: -3, detection_method: "cycle_count" },
  product_created: { ...INVENTORY, quantity: 0 },
  inventory_validation_failed: { ...INVENTORY, quantity: 0, form_type: "inbound", field_name: "quantity", reason_code: "required", occurrence_count: 1 },
  outbound_order_rejected: { ...INVENTORY, quantity: 21, available_quantity: 20, exit_type: "dispatch", reason_code: "insufficient_stock" },
  audit_history_viewed: { warehouse_filter: "all", movement_filter: "all", result_count: 8, load_duration_ms: 50 },
  login_succeeded: { auth_method: "password", role: "user", session_age_seconds: 0 },
  login_failed: { auth_method: "password", reason_code: "network_error", attempt_number: 1 },
  session_expired: { session_age_seconds: 600, expiry_reason: "token_expired", route_template: "/inventory" },
  authorization_denied: { endpoint_template: "/users/{id}", method: "GET", required_role: "owner", actual_role: "user", reason_code: "ownership_mismatch" },
  password_reset_requested: { delivery_channel: "email", outcome: "accepted" },
  page_viewed: PAGE_VIEW,
  workflow_started: { workflow_name: "inventory_inbound", flow_instance_id: "4cb11120-71a6-4a8f-a2d5-0cb59287fe14", entry_point: "navigation" },
  workflow_completed: { workflow_name: "inventory_inbound", flow_instance_id: "4cb11120-71a6-4a8f-a2d5-0cb59287fe14", duration_ms: 200, step_count: 3, outcome: "success" },
  workflow_abandoned: { workflow_name: "inventory_inbound", flow_instance_id: "4cb11120-71a6-4a8f-a2d5-0cb59287fe14", duration_ms: 200, last_step: "details_entered", abandonment_reason: "navigation" },
  api_latency_recorded: { service: "trackflow_api", endpoint_template: "/inventory/products", method: "GET", status_class: "2xx", duration_ms: 30, slo_exceeded: false },
  page_load_recorded: { route_template: "/inventory", duration_ms: 900, navigation_type: "initial", viewport_class: "desktop", threshold_exceeded: false },
  frontend_error_captured: { error_code: "TYPE_ERROR", error_fingerprint: `err_${"a".repeat(64)}`, component: "app/error", route_template: "/inventory", release: "test", handled: true, occurrence_count: 1 },
  api_error_returned: { service: "trackflow_api", endpoint_template: "/inventory/products", method: "GET", status_code: 500, error_code: "HTTP_500", duration_ms: 30, retryable: true },
};

async function freshTelemetry() {
  jest.resetModules();
  return import("@/lib/telemetry");
}

async function settle(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
}

describe("TelemetryService", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    window.sessionStorage.clear();
    process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT =
      "http://localhost:8000/telemetry/events";
    global.fetch = jest.fn().mockResolvedValue({ ok: true }) as jest.Mock;
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  it("builds the standard envelope automatically and flushes at 20 events", async () => {
    const { track } = await freshTelemetry();

    for (let index = 0; index < 20; index += 1) {
      track("page_viewed", PAGE_VIEW);
    }
    await settle();

    expect(fetch).toHaveBeenCalledTimes(1);
    const [endpoint, init] = jest.mocked(fetch).mock.calls[0];
    expect(endpoint).toBe("http://localhost:8000/telemetry/events");
    const batch = JSON.parse(String(init?.body));
    expect(batch.events).toHaveLength(20);
    expect(batch.events[0]).toEqual(expect.objectContaining({
      event_type: "page_viewed",
      schemaVersion: "1.0.0",
      userId: "anonymous",
      properties: PAGE_VIEW,
    }));
    expect(batch.events[0].eventId).toMatch(/^[0-9a-f-]{36}$/);
    expect(batch.events[0].timestamp).toMatch(/Z$/);
    expect(batch.events[0].sessionId).toMatch(/^sess_/);
    expect(batch.events[0].requestId).toMatch(/^req_/);
  });

  it("accepts every event contract in the approved 23-event catalogue", async () => {
    const { track } = await freshTelemetry();
    for (const [eventType, properties] of Object.entries(ALL_EVENT_PROPERTIES)) {
      track(eventType, properties);
    }
    await settle();
    await jest.advanceTimersByTimeAsync(10_000);
    await settle();

    const emitted = jest.mocked(fetch).mock.calls.flatMap(([, init]) =>
      JSON.parse(String(init?.body)).events.map((event: { event_type: string }) => event.event_type),
    );
    expect(new Set(emitted)).toEqual(new Set(Object.keys(ALL_EVENT_PROPERTIES)));
    expect(emitted).toHaveLength(23);
  });

  it("flushes a smaller queue after ten seconds", async () => {
    const { track } = await freshTelemetry();
    track("page_viewed", PAGE_VIEW);

    await jest.advanceTimersByTimeAsync(9_999);
    expect(fetch).not.toHaveBeenCalled();
    await jest.advanceTimersByTimeAsync(1);
    await settle();

    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("accepts the approved UUID workflow correlation contract", async () => {
    const { track } = await freshTelemetry();
    for (let index = 0; index < 20; index += 1) {
      track("workflow_started", {
        workflow_name: "inventory_inbound",
        flow_instance_id: "4cb11120-71a6-4a8f-a2d5-0cb59287fe14",
        entry_point: "navigation",
      });
    }
    await settle();

    expect(fetch).toHaveBeenCalledTimes(1);
    const batch = JSON.parse(String(jest.mocked(fetch).mock.calls[0][1]?.body));
    expect(batch.events[0].event_type).toBe("workflow_started");
  });

  it("rejects properties outside the approved allowlist without logging values", async () => {
    const warning = jest.spyOn(console, "warn").mockImplementation(() => undefined);
    const { track } = await freshTelemetry();

    for (let index = 0; index < 19; index += 1) track("page_viewed", PAGE_VIEW);
    track("page_viewed", { ...PAGE_VIEW, email: "private@example.com" });
    await settle();
    expect(fetch).not.toHaveBeenCalled();
    expect(warning).toHaveBeenCalledWith(expect.not.stringContaining("private@example.com"));

    track("page_viewed", PAGE_VIEW);
    await settle();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("retries a failed batch three times with exponential backoff", async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error("offline")) as jest.Mock;
    const warning = jest.spyOn(console, "warn").mockImplementation(() => undefined);
    const { track } = await freshTelemetry();

    for (let index = 0; index < 20; index += 1) track("page_viewed", PAGE_VIEW);
    await settle();
    await jest.advanceTimersByTimeAsync(1_750);
    await settle();

    expect(fetch).toHaveBeenCalledTimes(4);
    expect(warning).toHaveBeenCalledWith(
      "Telemetry event 'batch' discarded: delivery failed after three retries.",
    );
  });

  it("uses sendBeacon when the document becomes hidden", async () => {
    const sendBeacon = jest.fn().mockReturnValue(true);
    Object.defineProperty(navigator, "sendBeacon", { configurable: true, value: sendBeacon });
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" });
    const { track } = await freshTelemetry();
    track("page_viewed", PAGE_VIEW);

    document.dispatchEvent(new Event("visibilitychange"));

    expect(sendBeacon).toHaveBeenCalledWith(
      "http://localhost:8000/telemetry/events",
      expect.any(Blob),
    );
  });
});

describe("telemetry helpers", () => {
  it("derives the endpoint from the general API URL when no override exists", async () => {
    const { resolveTelemetryEndpoint } = await freshTelemetry();
    expect(resolveTelemetryEndpoint("", "/trackflow-api/")).toBe(
      "/trackflow-api/telemetry/events",
    );
  });

  it("normalises record ids out of endpoint templates", async () => {
    const { endpointTemplate } = await freshTelemetry();
    expect(endpointTemplate("/inventory/products/42?include=stock")).toBe(
      "/inventory/products/{id}",
    );
  });
});
