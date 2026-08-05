import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { sampleProducts, sampleShipment } from "../src/data/sampleData.js";
import {
  binarySearchProductByWeight,
  findProductBySKU,
  findShipmentById,
} from "../src/utils/search.js";

describe("search utilities", () => {
  it("finds a SKU without case sensitivity and ignores outer whitespace", () => {
    assert.equal(
      findProductBySKU(sampleProducts, "  laptop-dell-15 ")?.name,
      "Dell Laptop 15 inch",
    );
  });

  it("returns null when a product or shipment is not found", () => {
    assert.equal(findProductBySKU(sampleProducts, "UNKNOWN"), null);
    assert.equal(findShipmentById([sampleShipment], "UNKNOWN"), null);
  });

  it("finds a shipment by its exact ID", () => {
    assert.equal(
      findShipmentById([sampleShipment], "SH-2024-8821"),
      sampleShipment,
    );
  });

  it("uses binary search on weight-sorted products", () => {
    const sorted = [...sampleProducts].sort(
      (first, second) => first.weightKg - second.weightKg,
    );
    const index = binarySearchProductByWeight(sorted, 0.8);

    assert.equal(sorted[index]?.sku, "SHOE-BLK-42");
    assert.equal(binarySearchProductByWeight(sorted, 99), -1);
    assert.equal(binarySearchProductByWeight([], 1), -1);
  });
});
