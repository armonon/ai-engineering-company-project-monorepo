import { InventoryProductForm } from "@/components/InventoryProductForm";

export const metadata = { title: "Register inventory SKU" };

export default function NewInventoryProductPage() {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Register SKU</h2>
        <p className="mt-1 max-w-3xl text-sm text-slate-600">
          Create a governed TrackFlow product record. Stock starts at zero and can
          move only through inbound or outbound orders.
        </p>
      </div>
      <InventoryProductForm />
    </div>
  );
}
