"use client";

import { useEffect, useMemo, useState } from "react";
import { toUserMessage } from "@/lib/errors";
import {
  checkInventoryAudit,
  fetchInventoryProducts,
  type InventoryAuditResult,
  type InventoryProduct,
} from "@/lib/inventory";
import { track } from "@/lib/telemetry";

export function InventoryAuditForm() {
  const [products, setProducts] = useState<InventoryProduct[]>([]);
  const [skuId, setSkuId] = useState("");
  const [physicalQuantity, setPhysicalQuantity] = useState("");
  const [method, setMethod] = useState<"cycle_count" | "full_audit">("cycle_count");
  const [result, setResult] = useState<InventoryAuditResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchInventoryProducts()
      .then(setProducts)
      .catch((caught) => setError(toUserMessage(caught, "We couldn't load the audit catalogue.")))
      .finally(() => setLoading(false));
  }, []);

  const product = useMemo(
    () => products.find((candidate) => String(candidate.id) === skuId),
    [products, skuId],
  );

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setResult(null);
    const count = Number(physicalQuantity);
    if (!product || !Number.isInteger(count) || count < 0) {
      setError("Choose a SKU and enter a non-negative whole-number physical count.");
      return;
    }

    setSubmitting(true);
    try {
      const comparison = await checkInventoryAudit({
        sku_id: product.id,
        warehouse: product.warehouse,
        physical_quantity: count,
        detection_method: method,
      });
      setResult(comparison);
      if (comparison.discrepancy_detected) {
        track("inventory_discrepancy_detected", {
          warehouse: comparison.warehouse === "LA" ? "los_angeles" : "zaragoza",
          client_id: comparison.client_id,
          product_id: comparison.product_id,
          product_category: comparison.product_category,
          quantity: Math.abs(comparison.variance_quantity),
          audit_id: comparison.audit_id,
          system_quantity: comparison.system_quantity,
          physical_quantity: comparison.physical_quantity,
          variance_quantity: comparison.variance_quantity,
          detection_method: method,
        });
      }
    } catch (caught) {
      setError(toUserMessage(caught, "The physical count could not be compared."));
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <p className="text-sm text-slate-500">Loading SKUs…</p>;

  return (
    <form onSubmit={handleSubmit} className="max-w-2xl space-y-5 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      {error && <div role="alert" className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</div>}
      {result && (
        <div role="status" className={`rounded-md border p-4 text-sm ${result.discrepancy_detected ? "border-amber-300 bg-amber-50 text-amber-900" : "border-emerald-300 bg-emerald-50 text-emerald-900"}`}>
          <p className="font-semibold">{result.discrepancy_detected ? "Inventory discrepancy detected" : "Physical count matches"}</p>
          <p className="mt-1">System: {result.system_quantity} · Physical: {result.physical_quantity} · Variance: {result.variance_quantity > 0 ? "+" : ""}{result.variance_quantity}</p>
          <p className="mt-1 font-mono text-xs">Audit {result.audit_id}</p>
        </div>
      )}

      <label className="block text-sm font-medium text-slate-700">
        Product
        <select required value={skuId} onChange={(event) => setSkuId(event.target.value)} className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2">
          <option value="">Choose a product</option>
          {products.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.sku} · {item.warehouse}</option>)}
        </select>
      </label>

      {product && <p className="rounded-md bg-slate-50 p-3 text-sm">Computed stock: <strong>{product.current_stock}</strong> units in {product.warehouse}. The audit compares only; it never edits stock.</p>}

      <label className="block text-sm font-medium text-slate-700">
        Physical count
        <input required min="0" step="1" type="number" value={physicalQuantity} onChange={(event) => setPhysicalQuantity(event.target.value)} className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2" />
      </label>

      <label className="block text-sm font-medium text-slate-700">
        Audit method
        <select value={method} onChange={(event) => setMethod(event.target.value as "cycle_count" | "full_audit")} className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2">
          <option value="cycle_count">Cycle count</option>
          <option value="full_audit">Full audit</option>
        </select>
      </label>

      <button disabled={submitting} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:bg-slate-400">
        {submitting ? "Comparing…" : "Compare physical count"}
      </button>
    </form>
  );
}
