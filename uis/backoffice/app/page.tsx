import { InventoryOperations } from "@/components/InventoryOperations";

export const metadata = { title: "Inventory operations" };

export default function BackofficeHome() {
  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight text-slate-900">
          Inventory operations
        </h2>
        <p className="mt-1 max-w-3xl text-sm text-slate-600">
          Stock levels, warehouse split, product validation, and carrier
          selection — every figure computed at render time by the Milestone 2
          module{" "}
          <code className="rounded bg-slate-100 px-1">
            @trackflow/programming-fundamentals
          </code>
          . The backoffice imports it; it does not re-implement or copy the
          rules (rule <strong>MONO-1</strong>).
        </p>
      </div>
      <InventoryOperations />
    </div>
  );
}
