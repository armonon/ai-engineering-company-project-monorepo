import { authJson } from "@/lib/auth";

export type Warehouse = "LA" | "ZGZ";
export type ExitType = "dispatch" | "loss";
export type ProductCategory = "fashion" | "electronics" | "cosmetics";
export type TelemetryWarehouse = "los_angeles" | "zaragoza";

export interface InventoryProduct {
  id: number;
  name: string;
  sku: string;
  client_name: string;
  client_id: string | null;
  category: ProductCategory;
  warehouse: Warehouse;
  current_stock: number;
  stock_by_warehouse: Record<string, number>;
  minimum_stock: number | null;
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

export interface InventoryProductInput {
  name: string;
  sku: string;
  client_name: string;
  category: ProductCategory;
  warehouse: Warehouse;
}

export interface OutboundInput {
  sku_id: number;
  quantity: number;
  exit_type: ExitType;
  tracking_number: string | null;
  warehouse: Warehouse;
}

export interface InventoryAuditInput {
  sku_id: number;
  warehouse: Warehouse;
  physical_quantity: number;
  detection_method: "cycle_count" | "full_audit";
}

export interface InventoryAuditResult {
  audit_id: string;
  sku_id: number;
  warehouse: Warehouse;
  client_id: string;
  product_id: string;
  product_category: ProductCategory;
  system_quantity: number;
  physical_quantity: number;
  variance_quantity: number;
  discrepancy_detected: boolean;
}

export interface InventoryTelemetryDimensions {
  warehouse: TelemetryWarehouse;
  client_id: string;
  product_id: string;
  product_category: ProductCategory;
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

export function telemetryWarehouse(warehouse: Warehouse): TelemetryWarehouse {
  return warehouse === "LA" ? "los_angeles" : "zaragoza";
}

/** Return only governed, non-PII dimensions; never substitute display names. */
export function inventoryTelemetryDimensions(
  product: InventoryProduct,
): InventoryTelemetryDimensions | null {
  if (!product.client_id) return null;
  return {
    warehouse: telemetryWarehouse(product.warehouse),
    client_id: product.client_id,
    product_id: product.sku,
    product_category: product.category,
  };
}

export function fetchInventoryProducts(): Promise<InventoryProduct[]> {
  return authJson<InventoryProduct[]>("/inventory/products");
}

export function createInventoryProduct(
  input: InventoryProductInput,
): Promise<InventoryProduct> {
  return authJson<InventoryProduct>("/inventory/products", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
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

export function checkInventoryAudit(
  input: InventoryAuditInput,
): Promise<InventoryAuditResult> {
  return authJson<InventoryAuditResult>("/inventory/audits/check", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}
