"use client";

import { useRef, useState } from "react";
import { toUserMessage } from "@/lib/errors";
import {
  createInventoryProduct,
  inventoryTelemetryDimensions,
  type ProductCategory,
  type Warehouse,
} from "@/lib/inventory";
import { track } from "@/lib/telemetry";

const CLIENTS = [
  "PureStep Footwear",
  "SoundWave Electronics",
  "GlowLab Cosmetics",
  "UrbanThread",
] as const;

export function InventoryProductForm() {
  const [name, setName] = useState("");
  const [sku, setSku] = useState("");
  const [clientName, setClientName] = useState<(typeof CLIENTS)[number]>(CLIENTS[0]);
  const [category, setCategory] = useState<ProductCategory>("fashion");
  const [warehouse, setWarehouse] = useState<Warehouse>("LA");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const flow = useRef<{ id: string; startedAt: number; steps: number } | null>(null);

  function touchWorkflow() {
    if (flow.current) {
      flow.current.steps += 1;
      return;
    }
    const id = crypto.randomUUID();
    flow.current = { id, startedAt: Date.now(), steps: 1 };
    track("workflow_started", {
      workflow_name: "product_create",
      flow_instance_id: id,
      entry_point: "navigation",
    });
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    touchWorkflow();
    setSubmitting(true);
    try {
      const product = await createInventoryProduct({
        name: name.trim(),
        sku: sku.trim(),
        client_name: clientName,
        category,
        warehouse,
      });
      const dimensions = inventoryTelemetryDimensions(product);
      if (dimensions) track("product_created", { ...dimensions, quantity: 0 });
      if (flow.current) {
        track("workflow_completed", {
          workflow_name: "product_create",
          flow_instance_id: flow.current.id,
          duration_ms: Math.max(0, Date.now() - flow.current.startedAt),
          step_count: flow.current.steps,
          outcome: "success",
        });
      }
      flow.current = null;
      setName("");
      setSku("");
      setMessage(`${product.name} was registered at zero stock.`);
    } catch (caught) {
      setError(toUserMessage(caught, "The SKU could not be registered."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-2xl space-y-5 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      {error && <div role="alert" className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</div>}
      {message && <div role="status" className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</div>}

      <label className="block text-sm font-medium text-slate-700">Product name
        <input required maxLength={200} value={name} onChange={(event) => { setName(event.target.value); touchWorkflow(); }} className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2" />
      </label>
      <label className="block text-sm font-medium text-slate-700">SKU
        <input required maxLength={60} value={sku} onChange={(event) => { setSku(event.target.value); touchWorkflow(); }} className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 font-mono" />
      </label>
      <label className="block text-sm font-medium text-slate-700">Client
        <select value={clientName} onChange={(event) => { setClientName(event.target.value as (typeof CLIENTS)[number]); touchWorkflow(); }} className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2">
          {CLIENTS.map((client) => <option key={client}>{client}</option>)}
        </select>
      </label>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block text-sm font-medium text-slate-700">Category
          <select value={category} onChange={(event) => { setCategory(event.target.value as ProductCategory); touchWorkflow(); }} className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2">
            <option value="fashion">Fashion</option><option value="electronics">Electronics</option><option value="cosmetics">Cosmetics</option>
          </select>
        </label>
        <label className="block text-sm font-medium text-slate-700">Warehouse
          <select value={warehouse} onChange={(event) => { setWarehouse(event.target.value as Warehouse); touchWorkflow(); }} className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2">
            <option value="LA">Los Angeles</option><option value="ZGZ">Zaragoza</option>
          </select>
        </label>
      </div>
      <p className="rounded-md bg-slate-50 p-3 text-sm text-slate-600">New SKUs always start at zero stock. Register an inbound order to add units.</p>
      <button disabled={submitting} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:bg-slate-400">{submitting ? "Registering…" : "Register SKU"}</button>
    </form>
  );
}
