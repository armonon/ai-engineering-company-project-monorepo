import { InventoryAuditForm } from "@/components/InventoryAuditForm";

export const metadata = { title: "Inventory audit" };

export default function InventoryAuditPage() {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Inventory audit</h2>
        <p className="mt-1 max-w-3xl text-sm text-slate-600">
          Compare a warehouse physical count with computed TrackFlow stock.
          A variance emits the mandatory discrepancy event but never changes stock.
        </p>
      </div>
      <InventoryAuditForm />
    </div>
  );
}
