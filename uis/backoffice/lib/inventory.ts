import { authJson } from "@/lib/auth";

export type Warehouse = "LA" | "ZGZ";
export type ExitType = "dispatch" | "loss";

export interface InventoryProduct {
  id: number;
  name: string;
  sku: string;
  client_name: string;
  category: string;
  warehouse: Warehouse;
  current_stock: number;
  stock_by_warehouse: Record<string, number>;
}

export interface InventoryMovement {
  movement_type: "entry" | "exit";
  id: number;
  quantity: number;
  warehouse: Warehouse;
  created_at: string;
  user_uuid: string;
  sku: Pick<InventoryProduct, "id" | "name" | "sku" | "client_name">;
  reference: string | null;
  exit_type: ExitType | null;
  tracking_number: string | null;
}

export interface StockEntry {
  id: number;
  sku_id: number;
  quantity: number;
  reference: string;
  warehouse: Warehouse;
  created_at: string;
  user_uuid: string;
}

export interface StockExit {
  id: number;
  sku_id: number;
  quantity: number;
  exit_type: ExitType;
  tracking_number: string | null;
  warehouse: Warehouse;
  created_at: string;
  user_uuid: string;
}

export interface InboundInput {
  sku_id: number;
  quantity: number;
  reference: string;
  warehouse: Warehouse;
}

export interface OutboundInput {
  sku_id: number;
  quantity: number;
  exit_type: ExitType;
  tracking_number: string | null;
  warehouse: Warehouse;
}

export type StockStatus = "out" | "low" | "available";

// Operations threshold: 0 is out, 1–10 units is low, and 11+ is
// available. Keeping this in the integration layer makes the product
// table and any future scanner view use the same visual classification.
export function stockStatus(currentStock: number): StockStatus {
  if (currentStock <= 0) return "out";
  if (currentStock <= 10) return "low";
  return "available";
}

export function outboundStockWarning(
  currentStock: number,
  requestedQuantity: number,
  warehouse: Warehouse,
): string | null {
  if (!Number.isFinite(requestedQuantity) || requestedQuantity <= currentStock) {
    return null;
  }
  return `Insufficient stock. ${currentStock} units are available in ${warehouse}.`;
}

export function userUuidLabel(userUuid: string): string {
  return `user_uuid: ${userUuid}`;
}

export function fetchInventoryProducts(): Promise<InventoryProduct[]> {
  return authJson<InventoryProduct[]>("/inventory/products");
}

export function createInboundMovement(
  input: InboundInput,
): Promise<StockEntry> {
  return authJson<StockEntry>("/inventory/orders/inbound", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function createOutboundMovement(
  input: OutboundInput,
): Promise<StockExit> {
  return authJson<StockExit>("/inventory/orders/outbound", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function fetchInventoryOrders(): Promise<InventoryMovement[]> {
  return authJson<InventoryMovement[]>("/inventory/orders");
}
