import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { sampleCarriers, sampleProducts } from "../src/data/sampleData.js";
import {
  filterLowStockProducts,
  filterProductsByCategory,
  filterProductsByWarehouse,
  sortCarriersByReliability,
  sortProductsByStock,
} from "../src/utils/collections.js";

describe("collection utilities", () => {
  it("filters products by warehouse and category", () => {
    assert.deepEqual(
      filterProductsByWarehouse(sampleProducts, "Monterrey").map(
        ({ sku }) => sku,
      ),
      ["SHOE-BLK-42", "PERFUME-COCO-50"],
    );
    assert.deepEqual(
      filterProductsByCategory(sampleProducts, "Electronics").map(
        ({ sku }) => sku,
      ),
      ["LAPTOP-DELL-15"],
    );
  });

  it("includes products exactly at or below their stock threshold", () => {
    const atThreshold = {
      ...sampleProducts[0],
      stockQuantity: sampleProducts[0].minStockThreshold,
    };
    assert.deepEqual(
      filterLowStockProducts([...sampleProducts, atThreshold]).map(
        ({ sku }) => sku,
      ),
      ["LAPTOP-DELL-15", "SHOE-BLK-42"],
    );
  });

  it("sorts products without mutating the source array", () => {
    const originalOrder = sampleProducts.map(({ sku }) => sku);
    const ascending = sortProductsByStock(sampleProducts, "asc");
    const descending = sortProductsByStock(sampleProducts, "desc");

    assert.deepEqual(
      ascending.map(({ stockQuantity }) => stockQuantity),
      [8, 45, 120],
    );
    assert.deepEqual(
      descending.map(({ stockQuantity }) => stockQuantity),
      [120, 45, 8],
    );
    assert.deepEqual(
      sampleProducts.map(({ sku }) => sku),
      originalOrder,
    );
    assert.notEqual(ascending, sampleProducts);
  });

  it("sorts carriers by reliability without mutation", () => {
    const originalOrder = sampleCarriers.map(({ id }) => id);
    assert.deepEqual(
      sortCarriersByReliability(sampleCarriers, "desc").map(
        ({ onTimeRate }) => onTimeRate,
      ),
      [95, 92, 88],
    );
    assert.deepEqual(
      sampleCarriers.map(({ id }) => id),
      originalOrder,
    );
  });

  it("handles empty collections", () => {
    assert.deepEqual(filterLowStockProducts([]), []);
    assert.deepEqual(sortProductsByStock([], "asc"), []);
    assert.deepEqual(sortCarriersByReliability([], "desc"), []);
  });
});
