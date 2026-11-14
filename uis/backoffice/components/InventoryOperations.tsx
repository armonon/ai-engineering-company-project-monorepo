import {
  calculateShippingCost,
  calculateTotalInventoryValue,
  countProductsByCategory,
  filterLowStockProducts,
  filterProductsByWarehouse,
  findProductBySKU,
  sampleCarriers,
  sampleProducts,
  sampleShipment,
  selectBestCarrier,
  sortCarriersByReliability,
  sortProductsByStock,
  validateProduct,
  validateShipment,
  type Product,
  type WarehouseLocation,
} from "@trackflow/programming-fundamentals";

/**
 * Everything on this screen is computed by @trackflow/programming-fundamentals
 * — the Milestone 2 module — at render time. Nothing here re-implements a
 * rule or hardcodes a number: MONO-1 says the module is the single source of
 * truth, so the backoffice imports it rather than copying it.
 */

const WAREHOUSES: WarehouseLocation[] = ["Los Angeles", "Zaragoza"];
const currency = (value: number) =>
  value.toLocaleString("en-US", { style: "currency", currency: "USD" });

function Card({
  title,
  source,
  children,
}: {
  title: string;
  source: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-slate-900">{title}</h3>
      <p className="mt-0.5 text-xs text-slate-500">
        <code className="rounded bg-slate-100 px-1 py-0.5">{source}</code>
      </p>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function StockRow({ product }: { product: Product }) {
  const low = product.stockQuantity <= product.minStockThreshold;
  return (
    <tr className="border-t border-slate-100">
      <td className="py-2 pr-3">
        <span className="font-medium text-slate-900">{product.name}</span>
        <span className="block font-mono text-xs text-slate-500">
          {product.sku}
        </span>
      </td>
      <td className="py-2 pr-3 text-slate-700">{product.category}</td>
      <td className="py-2 pr-3 text-right tabular-nums text-slate-900">
        {product.stockQuantity}
      </td>
      <td className="py-2 pr-3 text-right tabular-nums text-slate-500">
        {product.minStockThreshold}
      </td>
      <td className="py-2 text-right">
        <span
          className={
            low
              ? "rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900"
              : "rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-900"
          }
        >
          {low ? "At or below minimum" : "Healthy"}
        </span>
      </td>
    </tr>
  );
}

export function InventoryOperations() {
  const byStock = sortProductsByStock(sampleProducts, "asc");
  const lowStock = filterLowStockProducts(sampleProducts);
  const categoryCounts = countProductsByCategory(sampleProducts);
  const totalValue = calculateTotalInventoryValue(sampleProducts);

  // The sample shipment moves a SKU, so the product comes from the module's
  // own search rather than from an index into the array.
  const shipmentProduct = findProductBySKU(sampleProducts, sampleShipment.sku);
  const bestCarrier = shipmentProduct
    ? selectBestCarrier(sampleCarriers, sampleShipment, shipmentProduct)
    : null;
  const carriersByReliability = sortCarriersByReliability(
    sampleCarriers,
    "desc",
  );
  const shipmentValidation = validateShipment(sampleShipment);

  // scoreCarrierForShipment() awards +20 for covering the destination
  // country but selectBestCarrier() does not require it — it keeps every
  // carrier scoring >= 50 and then takes the cheapest. So the module can
  // return a carrier that does not operate in the destination. That is the
  // module's behaviour, not this screen's, and the screen says so rather
  // than presenting the result as if it were deliverable.
  const covers = (carrier: { operatesIn: readonly string[] }) =>
    carrier.operatesIn.includes(sampleShipment.destination.country);
  const selectedLacksCoverage = bestCarrier
    ? !covers(bestCarrier.carrier)
    : false;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs uppercase tracking-wide text-slate-500">
            Inventory value
          </p>
          <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">
            {currency(totalValue)}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            calculateTotalInventoryValue()
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs uppercase tracking-wide text-slate-500">
            SKUs at or below minimum
          </p>
          <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">
            {lowStock.length}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            filterLowStockProducts()
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs uppercase tracking-wide text-slate-500">
            Catalogue
          </p>
          <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">
            {sampleProducts.length}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {Object.entries(categoryCounts)
              .filter(([, count]) => count > 0)
              .map(([category, count]) => `${category} ${count}`)
              .join(" · ")}
          </p>
        </div>
      </div>

      <Card
        title="Stock by SKU, lowest first"
        source="sortProductsByStock(products, 'asc') · filterLowStockProducts(products)"
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="pb-2 pr-3 font-medium">Product</th>
                <th className="pb-2 pr-3 font-medium">Category</th>
                <th className="pb-2 pr-3 text-right font-medium">On hand</th>
                <th className="pb-2 pr-3 text-right font-medium">Minimum</th>
                <th className="pb-2 text-right font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {byStock.map((product) => (
                <StockRow key={product.sku} product={product} />
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card
          title="Stock by warehouse"
          source="filterProductsByWarehouse(products, warehouse)"
        >
          <dl className="space-y-3">
            {WAREHOUSES.map((warehouse) => {
              const held = filterProductsByWarehouse(
                sampleProducts,
                warehouse,
              );
              return (
                <div key={warehouse}>
                  <dt className="text-sm font-medium text-slate-900">
                    {warehouse}
                    <span className="ml-2 text-xs font-normal text-slate-500">
                      {held.length} SKU{held.length === 1 ? "" : "s"} ·{" "}
                      {currency(calculateTotalInventoryValue(held))}
                    </span>
                  </dt>
                  <dd className="mt-1 text-sm text-slate-600">
                    {held.length > 0
                      ? held.map((product) => product.sku).join(", ")
                      : "No SKUs held here."}
                  </dd>
                </div>
              );
            })}
          </dl>
        </Card>

        <Card
          title="Product validation"
          source="validateProduct(product)"
        >
          <ul className="space-y-2 text-sm">
            {sampleProducts.map((product) => {
              const result = validateProduct(product);
              return (
                <li
                  key={product.sku}
                  className="flex items-start justify-between gap-3"
                >
                  <span className="font-mono text-xs text-slate-600">
                    {product.sku}
                  </span>
                  {result.valid ? (
                    <span className="text-xs font-medium text-emerald-700">
                      valid
                    </span>
                  ) : (
                    <span className="text-right text-xs text-red-700">
                      {result.errors.join("; ")}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </Card>
      </div>

      <Card
        title={`Carrier selection — shipment ${sampleShipment.id}`}
        source="selectBestCarrier(carriers, shipment, product) · calculateShippingCost() · scoreCarrierForShipment()"
      >
        <p className="text-sm text-slate-700">
          {sampleShipment.quantity} ×{" "}
          <span className="font-mono text-xs">{sampleShipment.sku}</span> from{" "}
          {sampleShipment.origin} to {sampleShipment.destination.city},{" "}
          {sampleShipment.destination.country} —{" "}
          {sampleShipment.destination.distanceKm} km,{" "}
          {sampleShipment.priority.toLowerCase()} priority.
          {shipmentValidation.valid ? null : (
            <span className="ml-1 text-red-700">
              Shipment rejected: {shipmentValidation.errors.join("; ")}
            </span>
          )}
        </p>

        {bestCarrier ? (
          <>
            <p className="mt-3 rounded-md bg-slate-900 px-4 py-3 text-sm text-white">
              Selected <strong>{bestCarrier.carrier.name}</strong> —{" "}
              {currency(bestCarrier.cost)}, score {bestCarrier.score},{" "}
              {bestCarrier.carrier.avgDeliveryDays} day
              {bestCarrier.carrier.avgDeliveryDays === 1 ? "" : "s"}.
            </p>
            {selectedLacksCoverage && (
              <p className="mt-2 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                <strong>{bestCarrier.carrier.name}</strong> does not list{" "}
                {sampleShipment.destination.country} in its coverage.{" "}
                <code className="rounded bg-amber-100 px-1">
                  selectBestCarrier()
                </code>{" "}
                scores destination coverage but does not require it, then
                takes the cheapest carrier above the score threshold — so this
                is the module&apos;s output, shown unmodified. Dispatch would
                need a coverage filter before acting on it.
              </p>
            )}
          </>
        ) : (
          <p className="mt-3 rounded-md bg-amber-50 px-4 py-3 text-sm text-amber-900">
            No carrier scored high enough for this shipment.
          </p>
        )}

        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="pb-2 pr-3 font-medium">Carrier</th>
                <th className="pb-2 pr-3 font-medium">Operates in</th>
                <th className="pb-2 pr-3 text-right font-medium">On time</th>
                <th className="pb-2 text-right font-medium">
                  Cost for this shipment
                </th>
              </tr>
            </thead>
            <tbody>
              {carriersByReliability.map((carrier) => (
                <tr key={carrier.id} className="border-t border-slate-100">
                  <td className="py-2 pr-3 font-medium text-slate-900">
                    {carrier.name}
                    {bestCarrier?.carrier.id === carrier.id && (
                      <span className="ml-2 rounded-full bg-slate-900 px-2 py-0.5 text-xs font-medium text-white">
                        selected
                      </span>
                    )}
                  </td>
                  <td className="py-2 pr-3 text-slate-700">
                    {carrier.operatesIn.join(", ")}
                    {!covers(carrier) && (
                      <span className="ml-2 text-xs text-amber-800">
                        no {sampleShipment.destination.country} coverage
                      </span>
                    )}
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums text-slate-700">
                    {carrier.onTimeRate}%
                  </td>
                  <td className="py-2 text-right tabular-nums text-slate-900">
                    {shipmentProduct
                      ? currency(
                          calculateShippingCost(
                            sampleShipment,
                            shipmentProduct,
                            carrier,
                          ),
                        )
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
