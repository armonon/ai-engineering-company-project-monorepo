import { InventoryMovementForm } from "@/components/InventoryMovementForm";

export const metadata = { title: "Receive inventory" };

export default function InboundInventoryPage() {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">
          Receive inventory
        </h2>
        <p className="mt-1 max-w-2xl text-sm text-slate-600">
          Confirm a goods receipt from a client brand. The receipt adds stock
          only to the SKU&apos;s own warehouse.
        </p>
      </div>
      <InventoryMovementForm direction="inbound" />
    </div>
  );
}
