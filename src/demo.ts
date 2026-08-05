import {
  sampleCarriers,
  sampleProducts,
  sampleShipment,
} from "./data/sampleData.js";
import { filterLowStockProducts } from "./utils/collections.js";
import {
  calculateTotalInventoryValue,
  selectBestCarrier,
} from "./utils/transformations.js";

const lowStockProducts = filterLowStockProducts(sampleProducts);
const bestCarrier = selectBestCarrier(
  sampleCarriers,
  sampleShipment,
  sampleProducts[1],
);

console.log("TrackFlow Milestone 2 demo");
console.log("Low-stock SKUs:", lowStockProducts.map(({ sku }) => sku));
console.log(
  "Inventory value (USD):",
  calculateTotalInventoryValue(sampleProducts),
);
console.log(
  "Best carrier:",
  bestCarrier === null
    ? "No suitable carrier"
    : `${bestCarrier.carrier.name} ($${bestCarrier.cost}, score ${bestCarrier.score})`,
);
