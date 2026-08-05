import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  sampleCarriers,
  sampleProducts,
  sampleShipment,
} from "../src/data/sampleData.js";
import type { Carrier, Shipment } from "../src/types/models.js";
import {
  calculateAverageShipmentDistance,
  calculateShippingCost,
  calculateTotalInventoryValue,
  countProductsByCategory,
  findTopCarriers,
  groupShipmentsByStatus,
  scoreCarrierForShipment,
  selectBestCarrier,
} from "../src/utils/transformations.js";

const laptop = sampleProducts[1];
const seur = sampleCarriers[1];

describe("carrier scoring and cost calculations", () => {
  it("calculates shipping cost and applies the Express surcharge", () => {
    // (6.50 + 2.3 * 1.5 + 320 * 0.08) * 1.30 = 46.215
    assert.equal(calculateShippingCost(sampleShipment, laptop, seur), 46.22);
  });

  it("applies Standard and Same-day surcharge rules", () => {
    assert.equal(
      calculateShippingCost(
        { ...sampleShipment, priority: "Standard" },
        laptop,
        seur,
      ),
      35.55,
    );
    assert.equal(
      calculateShippingCost(
        { ...sampleShipment, priority: "Same-day" },
        laptop,
        seur,
      ),
      56.88,
    );
  });

  it("scores all five suitability factors", () => {
    // country 20 + weight 20 + priority 15 + fragile 15 + reliability 27.6
    assert.equal(scoreCarrierForShipment(seur, sampleShipment, laptop), 97.6);
  });

  it("selects the lowest-cost suitable carrier", () => {
    const selection = selectBestCarrier(
      sampleCarriers,
      sampleShipment,
      laptop,
    );
    // Per the context contract, any score >= 50 is suitable; Estafeta scores
    // 76.4 and has the lowest calculated cost for this example.
    assert.equal(selection?.carrier.name, "Estafeta");
    assert.equal(selection?.cost, 30.89);
  });

  it("returns null when every carrier scores below 50", () => {
    const unsuitable: Carrier[] = sampleCarriers.map((carrier) => ({
      ...carrier,
      operatesIn: ["Mexico"],
      maxWeightKg: 1,
      handlesFragile: false,
      acceptsPriority: ["Standard"],
      onTimeRate: 0,
    }));
    assert.equal(selectBestCarrier(unsuitable, sampleShipment, laptop), null);
  });
});

describe("report aggregations", () => {
  const shipments: Shipment[] = [
    { ...sampleShipment, id: "SH-1", carrier: "SEUR", status: "Delivered" },
    {
      ...sampleShipment,
      id: "SH-2",
      carrier: "DHL Express",
      status: "In transit",
      destination: { ...sampleShipment.destination, distanceKm: 100 },
    },
    {
      ...sampleShipment,
      id: "SH-3",
      carrier: "SEUR",
      status: "Delivered",
      destination: { ...sampleShipment.destination, distanceKm: 180 },
    },
    { ...sampleShipment, id: "SH-4", carrier: null, status: "Pending" },
  ];

  it("counts every product category, including categories with zero products", () => {
    assert.deepEqual(countProductsByCategory(sampleProducts), {
      Fashion: 1,
      Electronics: 1,
      Cosmetics: 1,
      Home: 0,
      Other: 0,
    });
  });

  it("calculates total inventory value", () => {
    assert.equal(calculateTotalInventoryValue(sampleProducts), 16975);
    assert.equal(calculateTotalInventoryValue([]), 0);
  });

  it("calculates average distance and handles an empty collection", () => {
    assert.equal(calculateAverageShipmentDistance(shipments), 230);
    assert.equal(calculateAverageShipmentDistance([]), 0);
  });

  it("creates all status groups, including empty groups", () => {
    const groups = groupShipmentsByStatus(shipments);
    assert.equal(groups.Delivered.length, 2);
    assert.equal(groups["In transit"].length, 1);
    assert.deepEqual(groups.Assigned, []);
    assert.deepEqual(groups.Failed, []);
  });

  it("ranks assigned carriers and ignores null assignments", () => {
    assert.deepEqual(findTopCarriers(shipments, 2), [
      { carrier: "SEUR", count: 2 },
      { carrier: "DHL Express", count: 1 },
    ]);
    assert.deepEqual(findTopCarriers(shipments, 0), []);
    assert.deepEqual(findTopCarriers([], 3), []);
  });
});
