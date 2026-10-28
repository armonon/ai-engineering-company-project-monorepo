import { authFetch, authJson, readApiError } from "@/lib/auth";
import { fetchRfpTicket, fetchRfpTickets, uploadRfp } from "@/lib/rfp";

jest.mock("@/lib/auth", () => ({
  authFetch: jest.fn(),
  authJson: jest.fn(),
  readApiError: jest.fn(),
}));

const mockedFetch = jest.mocked(authFetch);
const mockedJson = jest.mocked(authJson);

describe("RFP ticket integration", () => {
  beforeEach(() => {
    mockedFetch.mockReset();
    mockedJson.mockReset();
  });

  it("uploads one PDF through the authenticated existing API", async () => {
    mockedFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ ticket_id: "ticket-1", status: "analyzing" }),
    } as Response);
    const file = new File(["%PDF fixture"], "client-rfp.pdf", {
      type: "application/pdf",
    });

    await expect(uploadRfp(file)).resolves.toEqual({
      ticket_id: "ticket-1",
      status: "analyzing",
    });
    expect(mockedFetch).toHaveBeenCalledWith("/rfp/tickets", {
      method: "POST",
      body: expect.any(FormData),
    });
  });

  it("uses the centralized authenticated layer for polling", async () => {
    mockedJson.mockResolvedValueOnce([]).mockResolvedValueOnce({ ticket_id: "ticket-1" });
    await fetchRfpTickets();
    await fetchRfpTicket("ticket-1");
    expect(mockedJson).toHaveBeenNthCalledWith(1, "/rfp/tickets");
    expect(mockedJson).toHaveBeenNthCalledWith(2, "/rfp/tickets/ticket-1");
  });

  it("surfaces the API error instead of swallowing it", async () => {
    mockedFetch.mockResolvedValue({ ok: false } as Response);
    jest.mocked(readApiError).mockResolvedValue("Upload a PDF RFP document.");
    const file = new File(["bad"], "bad.txt", { type: "text/plain" });
    await expect(uploadRfp(file)).rejects.toThrow("Upload a PDF RFP document.");
  });
});
