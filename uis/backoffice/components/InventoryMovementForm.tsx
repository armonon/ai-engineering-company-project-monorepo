"use client";

import { useEffect, useMemo, useState } from "react";
import { toUserMessage } from "@/lib/errors";
import {
  createInboundMovement,
  createOutboundMovement,
  fetchInventoryProducts,
  outboundStockWarning,
  type ExitType,
  type InventoryProduct,
} from "@/lib/inventory";

export function InventoryMovementForm({ direction }: { direction: "inbound" | "outbound" }) {
  const [products, setProducts] = useState<InventoryProduct[]>([]);
  const [skuId, setSkuId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [reference, setReference] = useState("");
  const [exitType, setExitType] = useState<ExitType>("dispatch");
  const [trackingNumber, setTrackingNumber] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [quantityError, setQuantityError] = useState<string | null>(null);

  useEffect(() => {
    fetchInventoryProducts()
      .then((loaded) => {
        setProducts(loaded);
        const requested = new URLSearchParams(window.location.search).get("sku");
        const validRequested = loaded.some((product) => String(product.id) === requested);
        if (validRequested) setSkuId(requested ?? "");
      })
      .catch((caught) => setError(toUserMessage(caught, "We couldn't load the SKU selector.")))
      .finally(() => setLoading(false));
  }, []);

  const product = useMemo(
    () => products.find((candidate) => String(candidate.id) === skuId),
    [products, skuId],
  );
  const numericQuantity = Number(quantity);
  const stockWarning =
    direction === "outbound" && product && quantity
      ? outboundStockWarning(
          product.current_stock,
          numericQuantity,
          product.warehouse,
        )
      : null;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    setError(null);
    setQuantityError(null);

    if (!product) {
      setError("Choose a product.");
      return;
    }
    if (!Number.isInteger(numericQuantity) || numericQuantity <= 0) {
      setError("Quantity must be a positive whole number.");
      return;
    }
    if (stockWarning) {
      setQuantityError(stockWarning);
      return;
    }
    if (direction === "outbound" && exitType === "dispatch" && !trackingNumber.trim()) {
      setError("A tracking number is required for a dispatch.");
      return;
    }

    setSubmitting(true);
    try {
      if (direction === "inbound") {
        await createInboundMovement({
          sku_id: product.id,
          quantity: numericQuantity,
          reference: reference.trim(),
          warehouse: product.warehouse,
        });
      } else {
        await createOutboundMovement({
          sku_id: product.id,
          quantity: numericQuantity,
          exit_type: exitType,
          tracking_number: exitType === "dispatch" ? trackingNumber.trim() : null,
          warehouse: product.warehouse,
        });
      }
      const refreshed = await fetchInventoryProducts();
      setProducts(refreshed);
      setSkuId("");
      setQuantity("");
      setReference("");
      setTrackingNumber("");
      setExitType("dispatch");
      setQuantityError(null);
      setMessage(`${direction === "inbound" ? "Goods receipt" : "Stock exit"} recorded for ${product.name}.`);
    } catch (caught) {
      const readable = toUserMessage(
        caught,
        `The ${direction} movement could not be recorded.`,
      );
      if (direction === "outbound" && /insufficient stock/i.test(readable)) {
        setQuantityError(readable);
      } else {
        setError(readable);
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <p className="text-sm text-slate-500">Loading SKUs…</p>;

  return (
    <form onSubmit={handleSubmit} className="max-w-2xl space-y-5 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      {error && <div role="alert" className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</div>}
      {message && <div role="status" className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</div>}

      <label className="block text-sm font-medium text-slate-700">
        Product
        <select required value={skuId} onChange={(event) => { setSkuId(event.target.value); setQuantityError(null); }} className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2">
          <option value="">Choose a product</option>
          {products.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.sku} · {item.warehouse}</option>)}
        </select>
      </label>

      {product && (
        <div className="grid gap-3 rounded-md bg-slate-50 p-4 text-sm sm:grid-cols-3">
          <p><span className="block text-xs uppercase text-slate-500">Client</span>{product.client_name}</p>
          <p><span className="block text-xs uppercase text-slate-500">Warehouse</span>{product.warehouse}</p>
          <p><span className="block text-xs uppercase text-slate-500">Current stock</span><strong>{product.current_stock}</strong> units</p>
        </div>
      )}

      <label className="block text-sm font-medium text-slate-700">
        Quantity
        <input required min="1" step="1" type="number" value={quantity} onChange={(event) => { setQuantity(event.target.value); setQuantityError(null); }} aria-describedby={direction === "outbound" && (stockWarning || quantityError) ? "quantity-stock-error" : undefined} className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2" />
        {direction === "outbound" && (quantityError || stockWarning) && (
          <span id="quantity-stock-error" role="alert" className="mt-1 block text-sm text-red-700">
            {quantityError ?? stockWarning}
          </span>
        )}
      </label>

      {direction === "inbound" ? (
        <label className="block text-sm font-medium text-slate-700">
          Receipt reference
          <input required maxLength={60} value={reference} onChange={(event) => setReference(event.target.value)} placeholder="PO-2026-0142" className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2" />
        </label>
      ) : (
        <>
          <label className="block text-sm font-medium text-slate-700">
            Exit type
            <select value={exitType} onChange={(event) => setExitType(event.target.value as ExitType)} className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2">
              <option value="dispatch">Customer dispatch</option>
              <option value="loss">Warehouse loss</option>
            </select>
          </label>
          {exitType === "dispatch" && (
            <label className="block text-sm font-medium text-slate-700">
              Tracking number
              <input required maxLength={60} value={trackingNumber} onChange={(event) => setTrackingNumber(event.target.value)} className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
          )}
        </>
      )}

      <button disabled={submitting || Boolean(stockWarning)} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400">
        {submitting ? "Saving…" : direction === "inbound" ? "Confirm goods receipt" : "Confirm stock exit"}
      </button>
    </form>
  );
}
