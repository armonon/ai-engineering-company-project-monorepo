import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  sampleCarriers,
  sampleProducts,
  sampleShipment,
} from "../src/data/sampleData.js";
import {
  validateCarrier,
  validateProduct,
  validateShipment,
} from "../src/utils/validations.js";

describe("business-rule validations", () => {
  it("accepts valid product, shipment, and carrier records", () => {
    assert.deepEqual(validateProduct(sampleProducts[0]), {
      valid: true,
      errors: [],
    });
    assert.deepEqual(validateShipment(sampleShipment), {
      valid: true,
      errors: [],
    });
    assert.deepEqual(validateCarrier(sampleCarriers[0]), {
      valid: true,
      errors: [],
    });
  });

  it("reports every invalid product field instead of stopping early", () => {
    const result = validateProduct({
      ...sampleProducts[0],
      sku: " ",
      weightKg: 101,
      dimensions: { lengthCm: 0, widthCm: 201, heightCm: -1 },
      stockQuantity: -1,
      minStockThreshold: -1,
      unitCostUSD: 0,
    });
    assert.equal(result.valid, false);
    assert.equal(result.errors.length, 8);
  });

  it("rejects non-positive shipment values and negative distance", () => {
    const result = validateShipment({
      ...sampleShipment,
      quantity: 0,
      declaredValueUSD: -1,
      destination: { ...sampleShipment.destination, distanceKm: -1 },
    });
    assert.equal(result.valid, false);
    assert.equal(result.errors.length, 3);
  });

  it("checks every carrier constraint", () => {
    const result = validateCarrier({
      ...sampleCarriers[0],
      operatesIn: [],
      baseRateUSD: -1,
      ratePerKgUSD: -1,
      ratePerKmUSD: -1,
      avgDeliveryDays: 0,
      onTimeRate: 101,
      maxWeightKg: 0,
    });
    assert.equal(result.valid, false);
    assert.equal(result.errors.length, 7);
  });

  it("accepts validation boundary values", () => {
    assert.equal(
      validateProduct({
        ...sampleProducts[0],
        weightKg: 100,
        dimensions: { lengthCm: 200, widthCm: 200, heightCm: 200 },
        stockQuantity: 0,
        minStockThreshold: 0,
      }).valid,
      true,
    );
    assert.equal(
      validateCarrier({
        ...sampleCarriers[0],
        baseRateUSD: 0,
        ratePerKgUSD: 0,
        ratePerKmUSD: 0,
        onTimeRate: 100,
      }).valid,
      true,
    );
  });
});
