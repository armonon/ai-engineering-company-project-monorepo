import { InventoryOrders } from "@/components/InventoryOrders";

export const metadata = { title: "Inventory movements" };

export default function InventoryOrdersPage() {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">
          Inventory movements
        </h2>
        <p className="mt-1 max-w-3xl text-sm text-slate-600">
          Read-only audit history of every goods receipt, customer dispatch,
          and warehouse loss, including the confirming TrackFlow user.
        </p>
      </div>
      <InventoryOrders />
    </div>
  );
}
