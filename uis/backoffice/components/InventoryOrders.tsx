"use client";

import { useEffect, useState } from "react";
import { toUserMessage } from "@/lib/errors";
import {
  fetchInventoryOrders,
  userUuidLabel,
  type InventoryMovement,
} from "@/lib/inventory";
import { track } from "@/lib/telemetry";

export function InventoryOrders() {
  const [orders, setOrders] = useState<InventoryMovement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const startedAt = performance.now();
    fetchInventoryOrders()
      .then((loaded) => {
        setOrders(loaded);
        track("audit_history_viewed", {
          warehouse_filter: "all",
          movement_filter: "all",
          result_count: loaded.length,
          load_duration_ms: Math.max(0, Math.round(performance.now() - startedAt)),
        });
      })
      .catch((caught) => setError(toUserMessage(caught, "We couldn't load stock movements.")))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-sm text-slate-500">Loading movements…</p>;
  if (error) return <div role="alert" className="rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-800">{error}</div>;
  if (orders.length === 0) return <p className="rounded-lg border bg-white p-8 text-center text-sm text-slate-500">No stock movements have been recorded.</p>;

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr><th className="px-4 py-3">Date</th><th className="px-4 py-3">Product</th><th className="px-4 py-3">Movement</th><th className="px-4 py-3">Reference</th><th className="px-4 py-3">Created by</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {orders.map((order) => (
              <tr key={`${order.movement_type}-${order.id}`}>
                <td className="whitespace-nowrap px-4 py-3">{new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(order.created_at))}</td>
                <td className="px-4 py-3"><p className="font-medium">{order.sku.name}</p><p className="font-mono text-xs text-slate-500">{order.sku.sku} · {order.warehouse}</p></td>
                <td className="px-4 py-3"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${order.movement_type === "entry" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>{order.movement_type === "entry" ? "+" : "−"}{order.quantity} {order.exit_type ?? "receipt"}</span></td>
                <td className="px-4 py-3">{order.reference ?? order.tracking_number ?? "—"}</td>
                <td className="px-4 py-3 font-mono text-xs">{userUuidLabel(order.user_uuid)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
