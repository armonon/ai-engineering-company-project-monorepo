import { parseRfpNotificationBlock } from "@/lib/rfp-notifications";

describe("RFP SSE notification contract", () => {
  it("parses the named TrackFlow event and structured payload", () => {
    const parsed = parseRfpNotificationBlock(
      'id: 7\nevent: rfp_ticket_created\ndata: {"ticket_id":"tkt_0225","rfp_id":"rfp_0071","client_name":"Northline Apparel","client_country":"US","services_requested":["warehouse"],"status":"analyzing","created_at":"2026-07-24T14:32:00Z"}',
    );

    expect(parsed).toEqual({
      id: 7,
      event: "rfp_ticket_created",
      data: {
        ticket_id: "tkt_0225",
        rfp_id: "rfp_0071",
        client_name: "Northline Apparel",
        client_country: "US",
        services_requested: ["warehouse"],
        status: "analyzing",
        created_at: "2026-07-24T14:32:00Z",
      },
    });
  });

  it("ignores keep-alive frames and unrelated event types", () => {
    expect(parseRfpNotificationBlock(": keep-alive")).toBeNull();
    expect(parseRfpNotificationBlock('id: 8\nevent: message\ndata: {"message":"generic"}')).toBeNull();
  });
});
