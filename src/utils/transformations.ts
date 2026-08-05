import type {
  Carrier,
  CarrierSelection,
  Product,
  ProductCategory,
  Shipment,
  ShipmentStatus,
} from "../types/models.js";

const PRODUCT_CATEGORIES: ProductCategory[] = [
  "Fashion",
  "Electronics",
  "Cosmetics",
  "Home",
  "Other",
];

function roundToTwoDecimals(value: number): number {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

export function calculateShippingCost(
  shipment: Shipment,
  product: Product,
  carrier: Carrier,
): number {
  const weightCost =
    product.weightKg * carrier.ratePerKgUSD * shipment.quantity;
  const distanceCost =
    shipment.destination.distanceKm * carrier.ratePerKmUSD;
  const subtotal = carrier.baseRateUSD + weightCost + distanceCost;
  const priorityMultiplier =
    shipment.priority === "Express"
      ? 1.3
      : shipment.priority === "Same-day"
        ? 1.6
        : 1;

  return roundToTwoDecimals(subtotal * priorityMultiplier);
}

export function scoreCarrierForShipment(
  carrier: Carrier,
  shipment: Shipment,
  product: Product,
): number {
  let score = carrier.onTimeRate * 0.3;

  if (carrier.operatesIn.includes(shipment.destination.country)) {
    score += 20;
  }

  if (product.weightKg * shipment.quantity <= carrier.maxWeightKg) {
    score += 20;
  }

  if (carrier.acceptsPriority.includes(shipment.priority)) {
    score += 15;
  }

  if (!product.isFragile || carrier.handlesFragile) {
    score += 15;
  }

  return roundToTwoDecimals(score);
}

export function selectBestCarrier(
  carriers: Carrier[],
  shipment: Shipment,
  product: Product,
): CarrierSelection | null {
  const suitableCarriers = carriers
    .map((carrier): CarrierSelection => ({
      carrier,
      score: scoreCarrierForShipment(carrier, shipment, product),
      cost: calculateShippingCost(shipment, product, carrier),
    }))
    .filter((selection) => selection.score >= 50);

  if (suitableCarriers.length === 0) {
    return null;
  }

  return suitableCarriers.reduce((best, current) =>
    current.cost < best.cost ? current : best,
  );
}

export function countProductsByCategory(
  products: Product[],
): Record<ProductCategory, number> {
  const counts = Object.fromEntries(
    PRODUCT_CATEGORIES.map((category) => [category, 0]),
  ) as Record<ProductCategory, number>;

  for (const product of products) {
    counts[product.category] += 1;
  }

  return counts;
}

export function calculateTotalInventoryValue(products: Product[]): number {
  const total = products.reduce(
    (sum, product) => sum + product.stockQuantity * product.unitCostUSD,
    0,
  );
  return roundToTwoDecimals(total);
}

export function calculateAverageShipmentDistance(
  shipments: Shipment[],
): number {
  if (shipments.length === 0) {
    return 0;
  }

  const totalDistance = shipments.reduce(
    (sum, shipment) => sum + shipment.destination.distanceKm,
    0,
  );
  return roundToTwoDecimals(totalDistance / shipments.length);
}

export function groupShipmentsByStatus(
  shipments: Shipment[],
): Record<ShipmentStatus, Shipment[]> {
  const groups: Record<ShipmentStatus, Shipment[]> = {
    Pending: [],
    Assigned: [],
    "In transit": [],
    Delivered: [],
    Failed: [],
  };

  for (const shipment of shipments) {
    groups[shipment.status].push(shipment);
  }

  return groups;
}

export function findTopCarriers(
  shipments: Shipment[],
  topN: number,
): Array<{ carrier: string; count: number }> {
  if (topN <= 0) {
    return [];
  }

  const counts = new Map<string, number>();
  for (const shipment of shipments) {
    if (shipment.carrier !== null) {
      counts.set(shipment.carrier, (counts.get(shipment.carrier) ?? 0) + 1);
    }
  }

  return [...counts.entries()]
    .map(([carrier, count]) => ({ carrier, count }))
    .sort(
      (first, second) =>
        second.count - first.count || first.carrier.localeCompare(second.carrier),
    )
    .slice(0, topN);
}
