"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { toUserMessage } from "@/lib/errors";
import {
  fetchInventoryProducts,
  stockStatus,
  type InventoryProduct,
  type StockStatus,
} from "@/lib/inventory";

const STATUS_STYLE: Record<StockStatus, string> = {
  out: "border-red-200 bg-red-50 text-red-800",
  low: "border-amber-200 bg-amber-50 text-amber-800",
  available: "border-emerald-200 bg-emerald-50 text-emerald-800",
};

const STATUS_LABEL: Record<StockStatus, string> = {
  out: "Out of stock",
  low: "Low stock",
  available: "Available",
};

export function InventoryProductList() {
  const [products, setProducts] = useState<InventoryProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setProducts(await fetchInventoryProducts());
    } catch (caught) {
      setError(toUserMessage(caught, "We couldn't load inventory products."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  if (loading) {
    return <p className="rounded-lg border bg-white p-8 text-center text-sm text-slate-500">Loading inventory…</p>;
  }

  if (error) {
    return (
      <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-800">
        <p className="font-semibold">Inventory is unavailable</p>
        <p className="mt-1">{error}</p>
        <button type="button" onClick={() => void load()} className="mt-3 rounded-md border border-red-300 bg-white px-3 py-1.5 font-medium hover:bg-red-100">
          Try again
        </button>
      </div>
    );
  }

  if (products.length === 0) {
    return <p className="rounded-lg border bg-white p-8 text-center text-sm text-slate-500">No SKUs have been registered yet.</p>;
  }

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3 font-medium">Product</th>
              <th className="px-4 py-3 font-medium">Client / category</th>
              <th className="px-4 py-3 font-medium">Warehouse</th>
              <th className="px-4 py-3 text-right font-medium">Current stock</th>
              <th className="px-4 py-3 text-right font-medium">Movement</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {products.map((product) => {
              const status = stockStatus(product.current_stock);
              return (
                <tr key={product.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-900">{product.name}</p>
                    <p className="font-mono text-xs text-slate-500">{product.sku}</p>
                  </td>
                  <td className="px-4 py-3">
                    <p>{product.client_name}</p>
                    <p className="text-xs capitalize text-slate-500">{product.category.replaceAll("_", " ")}</p>
                  </td>
                  <td className="px-4 py-3 font-medium">{product.warehouse}</td>
                  <td className="px-4 py-3 text-right">
                    <span className={`inline-flex rounded-full border px-2.5 py-1 font-semibold ${STATUS_STYLE[status]}`}>
                      {product.current_stock} · {STATUS_LABEL[status]}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      <Link href={`/backoffice/inventory/orders/inbound?sku=${product.id}`} className="rounded-md border border-slate-300 px-2.5 py-1.5 font-medium text-slate-700 hover:bg-slate-100">
                        Inbound
                      </Link>
                      <Link href={`/backoffice/inventory/orders/outbound?sku=${product.id}`} className="rounded-md bg-slate-900 px-2.5 py-1.5 font-medium text-white hover:bg-slate-700">
                        Outbound
                      </Link>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
