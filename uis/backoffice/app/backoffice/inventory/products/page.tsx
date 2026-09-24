import Link from "next/link";
import { InventoryProductList } from "@/components/InventoryProductList";

export const metadata = { title: "Inventory products" };

export default function InventoryProductsPage() {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Inventory</h2>
          <p className="mt-1 max-w-3xl text-sm text-slate-600">
            Warehouse-scoped stock for TrackFlow SKUs. Stock is computed
            from confirmed receipts, dispatches, and losses—never edited
            directly.
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            href="/backoffice/inventory/products/new"
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium hover:bg-slate-50"
          >
            Register SKU
          </Link>
          <Link
            href="/backoffice/inventory/audit"
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium hover:bg-slate-50"
          >
            Audit stock
          </Link>
          <Link
            href="/backoffice/inventory/orders/inbound"
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium hover:bg-slate-50"
          >
            Receive stock
          </Link>
          <Link
            href="/backoffice/inventory/orders/outbound"
            className="rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            Dispatch or record loss
          </Link>
        </div>
      </div>
      <InventoryProductList />
    </div>
  );
}
