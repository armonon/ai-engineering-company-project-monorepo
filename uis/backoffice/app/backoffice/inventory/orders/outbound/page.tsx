import { InventoryMovementForm } from "@/components/InventoryMovementForm";

export const metadata = { title: "Dispatch inventory" };

export default function OutboundInventoryPage() {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">
          Dispatch or record a loss
        </h2>
        <p className="mt-1 max-w-2xl text-sm text-slate-600">
          Remove stock from the selected warehouse. Dispatches require
          tracking; losses must not carry a tracking number. Overselling is
          blocked here and by the API.
        </p>
      </div>
      <InventoryMovementForm direction="outbound" />
    </div>
  );
}
