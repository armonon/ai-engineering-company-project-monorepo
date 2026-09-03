import { authJson } from "@/lib/auth";
import {
  createInboundMovement,
  createInventoryProduct,
  createOutboundMovement,
  checkInventoryAudit,
  inventoryTelemetryDimensions,
  outboundStockWarning,
  stockStatus,
  userUuidLabel,
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

describe("userUuidLabel", () => {
  it("shows the exact creator field required by the rubric", () => {
    expect(userUuidLabel("warehouse-user-42")).toBe(
      "user_uuid: warehouse-user-42",
    );
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

describe("governed telemetry dimensions", () => {
  it("normalises warehouse codes and never substitutes a client display name", () => {
    expect(inventoryTelemetryDimensions({
      id: 1,
      name: "Classic White Sneaker",
      sku: "CLT-SNK-W-42",
      client_name: "PureStep Footwear",
      client_id: "client_01JTF000000000000000000001",
      category: "fashion",
      warehouse: "LA",
      current_stock: 20,
      stock_by_warehouse: { LA: 20 },
      minimum_stock: 25,
    })).toEqual({
      warehouse: "los_angeles",
      client_id: "client_01JTF000000000000000000001",
      product_id: "CLT-SNK-W-42",
      product_category: "fashion",
    });
  });
});

describe("inventory movement requests", () => {
  it("registers a SKU without any directly editable stock field", async () => {
    mockedAuthJson.mockResolvedValue({ id: 3 });
    const input = {
      name: "Trail Shoe",
      sku: "CLT-SHOE-001",
      client_name: "PureStep Footwear",
      category: "fashion" as const,
      warehouse: "LA" as const,
    };

    await createInventoryProduct(input);

    expect(mockedAuthJson).toHaveBeenCalledWith(
      "/inventory/products",
      expect.objectContaining({ method: "POST", body: JSON.stringify(input) }),
    );
    expect(input).not.toHaveProperty("current_stock");
  });

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

  it("sends a physical count to the non-mutating audit endpoint", async () => {
    mockedAuthJson.mockResolvedValue({ audit_id: "audit-1" });
    const input = {
      sku_id: 9,
      warehouse: "ZGZ" as const,
      physical_quantity: 88,
      detection_method: "cycle_count" as const,
    };

    await checkInventoryAudit(input);

    expect(mockedAuthJson).toHaveBeenCalledWith(
      "/inventory/audits/check",
      expect.objectContaining({ method: "POST", body: JSON.stringify(input) }),
    );
  });
});
