import { authJson } from "@/lib/auth";
import {
  createInboundMovement,
  createOutboundMovement,
  outboundStockWarning,
  stockStatus,
} from "@/lib/inventory";

jest.mock("@/lib/auth", () => ({ authJson: jest.fn() }));

const mockedAuthJson = jest.mocked(authJson);

beforeEach(() => {
  mockedAuthJson.mockReset();
});

describe("outboundStockWarning", () => {
  it("warns before an outbound quantity exceeds warehouse stock", () => {
    expect(outboundStockWarning(10, 11, "LA")).toBe(
      "Insufficient stock. 10 units are available in LA.",
    );
  });

  it("allows an exit equal to the available stock", () => {
    expect(outboundStockWarning(10, 10, "ZGZ")).toBeNull();
  });
});

describe("stockStatus", () => {
  it("marks empty and negative computed stock as out", () => {
    expect(stockStatus(0)).toBe("out");
    expect(stockStatus(-1)).toBe("out");
  });

  it("marks one through ten units as low", () => {
    expect(stockStatus(1)).toBe("low");
    expect(stockStatus(10)).toBe("low");
  });

  it("marks stock over ten as available", () => {
    expect(stockStatus(11)).toBe("available");
  });
});

describe("inventory movement requests", () => {
  it("sends the inbound payload to the protected receipt endpoint", async () => {
    mockedAuthJson.mockResolvedValue({ id: 1 });
    const input = {
      sku_id: 7,
      quantity: 12,
      reference: "PO-2042",
      warehouse: "LA" as const,
    };

    await createInboundMovement(input);

    expect(mockedAuthJson).toHaveBeenCalledWith(
      "/inventory/orders/inbound",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(input),
      }),
    );
  });

  it("preserves the nullable tracking contract for a warehouse loss", async () => {
    mockedAuthJson.mockResolvedValue({ id: 2 });
    const input = {
      sku_id: 9,
      quantity: 1,
      exit_type: "loss" as const,
      tracking_number: null,
      warehouse: "ZGZ" as const,
    };

    await createOutboundMovement(input);

    expect(mockedAuthJson).toHaveBeenCalledWith(
      "/inventory/orders/outbound",
      expect.objectContaining({ body: JSON.stringify(input) }),
    );
  });
});
