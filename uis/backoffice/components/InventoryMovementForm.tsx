"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toUserMessage } from "@/lib/errors";
import {
  createInboundMovement,
  createOutboundMovement,
  fetchInventoryProducts,
  inventoryTelemetryDimensions,
  outboundStockWarning,
  type ExitType,
  type InventoryProduct,
} from "@/lib/inventory";
import { track } from "@/lib/telemetry";

type WorkflowStep =
  | "opened"
  | "product_selected"
  | "details_entered"
  | "validation_failed"
  | "reviewed"
  | "submitted";

interface WorkflowState {
  id: string;
  startedAt: number;
  steps: number;
  lastStep: WorkflowStep;
  completed: boolean;
}

function newFlowId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (value) => {
    const random = Math.floor(Math.random() * 16);
    return (value === "x" ? random : (random & 0x3) | 0x8).toString(16);
  });
}

export function InventoryMovementForm({ direction }: { direction: "inbound" | "outbound" }) {
  const [products, setProducts] = useState<InventoryProduct[]>([]);
  const [skuId, setSkuId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [reference, setReference] = useState("");
  const [exitType, setExitType] = useState<ExitType>("dispatch");
  const [trackingNumber, setTrackingNumber] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [quantityError, setQuantityError] = useState<string | null>(null);
  const workflow = useRef<WorkflowState | null>(null);
  const entryPoint = useRef<"navigation" | "product_row" | "deep_link">("navigation");

  const workflowName = direction === "inbound"
    ? "inventory_inbound"
    : "inventory_outbound";

  const touchWorkflow = useCallback((step: WorkflowStep) => {
    if (!workflow.current) {
      workflow.current = {
        id: newFlowId(),
        startedAt: Date.now(),
        steps: 1,
        lastStep: step,
        completed: false,
      };
      track("workflow_started", {
        workflow_name: workflowName,
        flow_instance_id: workflow.current.id,
        entry_point: entryPoint.current,
      });
      return;
    }
    if (workflow.current.lastStep !== step) workflow.current.steps += 1;
    workflow.current.lastStep = step;
  }, [workflowName]);

  useEffect(() => {
    fetchInventoryProducts()
      .then((loaded) => {
        setProducts(loaded);
        const requested = new URLSearchParams(window.location.search).get("sku");
        const validRequested = loaded.some((product) => String(product.id) === requested);
        if (validRequested) {
          entryPoint.current = "product_row";
          setSkuId(requested ?? "");
          touchWorkflow("product_selected");
        }
      })
      .catch((caught) => setError(toUserMessage(caught, "We couldn't load the SKU selector.")))
      .finally(() => setLoading(false));
  }, [touchWorkflow]);

  useEffect(() => () => {
    const state = workflow.current;
    if (!state || state.completed) return;
    track("workflow_abandoned", {
      workflow_name: workflowName,
      flow_instance_id: state.id,
      duration_ms: Math.max(0, Date.now() - state.startedAt),
      last_step: state.lastStep,
      abandonment_reason: "navigation",
    });
  }, [workflowName]);

  const product = useMemo(
    () => products.find((candidate) => String(candidate.id) === skuId),
    [products, skuId],
  );
  const numericQuantity = Number(quantity);
  const stockWarning =
    direction === "outbound" && product && quantity
      ? outboundStockWarning(
          product.current_stock,
          numericQuantity,
          product.warehouse,
        )
      : null;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    setError(null);
    setQuantityError(null);

    if (!product) {
      setError("Choose a product.");
      return;
    }
    const telemetryDimensions = inventoryTelemetryDimensions(product);
    const telemetryQuantity = Number.isInteger(numericQuantity) ? numericQuantity : 0;
    const validationFailed = (
      fieldName: "quantity" | "reference" | "tracking_number",
      reasonCode: "required" | "not_positive_integer" | "tracking_required",
    ) => {
      touchWorkflow("validation_failed");
      if (!telemetryDimensions) return;
      track("inventory_validation_failed", {
        ...telemetryDimensions,
        quantity: telemetryQuantity,
        form_type: direction,
        field_name: fieldName,
        reason_code: reasonCode,
        occurrence_count: 1,
      });
    };
    if (!Number.isInteger(numericQuantity) || numericQuantity <= 0) {
      setError("Quantity must be a positive whole number.");
      validationFailed("quantity", "not_positive_integer");
      return;
    }
    if (stockWarning) {
      setQuantityError(stockWarning);
      touchWorkflow("validation_failed");
      if (telemetryDimensions) {
        track("outbound_order_rejected", {
          ...telemetryDimensions,
          quantity: numericQuantity,
          available_quantity: product.current_stock,
          exit_type: exitType,
          reason_code: "insufficient_stock",
        });
      }
      return;
    }
    if (direction === "inbound" && !reference.trim()) {
      setError("A receipt reference is required.");
      validationFailed("reference", "required");
      return;
    }
    if (direction === "outbound" && exitType === "dispatch" && !trackingNumber.trim()) {
      setError("A tracking number is required for a dispatch.");
      validationFailed("tracking_number", "tracking_required");
      return;
    }

    touchWorkflow("submitted");
    setSubmitting(true);
    try {
      const stockBefore = product.current_stock;
      let orderId: number;
      if (direction === "inbound") {
        const movement = await createInboundMovement({
          sku_id: product.id,
          quantity: numericQuantity,
          reference: reference.trim(),
          warehouse: product.warehouse,
        });
        orderId = movement.id;
      } else {
        const movement = await createOutboundMovement({
          sku_id: product.id,
          quantity: numericQuantity,
          exit_type: exitType,
          tracking_number: exitType === "dispatch" ? trackingNumber.trim() : null,
          warehouse: product.warehouse,
        });
        orderId = movement.id;
      }
      const refreshed = await fetchInventoryProducts();
      const stockAfter = refreshed.find((candidate) => candidate.id === product.id)?.current_stock
        ?? (direction === "inbound"
          ? stockBefore + numericQuantity
          : stockBefore - numericQuantity);
      if (telemetryDimensions) {
        if (direction === "inbound") {
          track("inbound_order_created", {
            ...telemetryDimensions,
            quantity: numericQuantity,
            order_id: String(orderId),
            stock_after: stockAfter,
            reference_present: Boolean(reference.trim()),
          });
        } else if (exitType === "dispatch") {
          track("outbound_order_created", {
            ...telemetryDimensions,
            quantity: numericQuantity,
            order_id: String(orderId),
            exit_type: "dispatch",
            stock_after: stockAfter,
            tracking_present: Boolean(trackingNumber.trim()),
          });
        } else {
          track("inventory_loss_recorded", {
            ...telemetryDimensions,
            quantity: numericQuantity,
            order_id: String(orderId),
            exit_type: "loss",
            stock_after: stockAfter,
          });
        }

        const minimumStock = product.minimum_stock;
        if (
          direction === "outbound"
          && minimumStock !== null
          && stockBefore >= minimumStock
          && stockAfter < minimumStock
        ) {
          track("stock_threshold_triggered", {
            ...telemetryDimensions,
            quantity: stockAfter,
            threshold_quantity: minimumStock,
            previous_quantity: stockBefore,
            trigger_source: exitType === "loss" ? "inventory_loss" : "outbound_order",
          });
        }
      }

      const flow = workflow.current;
      if (flow) {
        flow.completed = true;
        track("workflow_completed", {
          workflow_name: workflowName,
          flow_instance_id: flow.id,
          duration_ms: Math.max(0, Date.now() - flow.startedAt),
          step_count: flow.steps,
          outcome: "success",
        });
        workflow.current = null;
      }
      setProducts(refreshed);
      setSkuId("");
      setQuantity("");
      setReference("");
      setTrackingNumber("");
      setExitType("dispatch");
      setQuantityError(null);
      setMessage(`${direction === "inbound" ? "Goods receipt" : "Stock exit"} recorded for ${product.name}.`);
    } catch (caught) {
      const readable = toUserMessage(
        caught,
        `The ${direction} movement could not be recorded.`,
      );
      if (direction === "outbound" && /insufficient stock/i.test(readable)) {
        setQuantityError(readable);
        if (telemetryDimensions) {
          track("outbound_order_rejected", {
            ...telemetryDimensions,
            quantity: numericQuantity,
            available_quantity: product.current_stock,
            exit_type: exitType,
            reason_code: "insufficient_stock",
          });
        }
      } else {
        setError(readable);
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <p className="text-sm text-slate-500">Loading SKUs…</p>;

  return (
    <form onSubmit={handleSubmit} noValidate className="max-w-2xl space-y-5 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      {error && <div role="alert" className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</div>}
      {message && <div role="status" className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</div>}

      <label className="block text-sm font-medium text-slate-700">
        Product
        <select required value={skuId} onChange={(event) => { setSkuId(event.target.value); setQuantityError(null); if (event.target.value) touchWorkflow("product_selected"); }} className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2">
          <option value="">Choose a product</option>
          {products.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.sku} · {item.warehouse}</option>)}
        </select>
      </label>

      {product && (
        <div className="grid gap-3 rounded-md bg-slate-50 p-4 text-sm sm:grid-cols-3">
          <p><span className="block text-xs uppercase text-slate-500">Client</span>{product.client_name}</p>
          <p><span className="block text-xs uppercase text-slate-500">Warehouse</span>{product.warehouse}</p>
          <p><span className="block text-xs uppercase text-slate-500">Current stock</span><strong>{product.current_stock}</strong> units</p>
        </div>
      )}

      <label className="block text-sm font-medium text-slate-700">
        Quantity
        <input required min="1" step="1" type="number" value={quantity} onChange={(event) => { setQuantity(event.target.value); setQuantityError(null); if (event.target.value) touchWorkflow("details_entered"); }} aria-describedby={direction === "outbound" && (stockWarning || quantityError) ? "quantity-stock-error" : undefined} className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2" />
        {direction === "outbound" && (quantityError || stockWarning) && (
          <span id="quantity-stock-error" role="alert" className="mt-1 block text-sm text-red-700">
            {quantityError ?? stockWarning}
          </span>
        )}
      </label>

      {direction === "inbound" ? (
        <label className="block text-sm font-medium text-slate-700">
          Receipt reference
          <input required maxLength={60} value={reference} onChange={(event) => { setReference(event.target.value); if (event.target.value) touchWorkflow("details_entered"); }} placeholder="PO-2026-0142" className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2" />
        </label>
      ) : (
        <>
          <label className="block text-sm font-medium text-slate-700">
            Exit type
            <select value={exitType} onChange={(event) => { setExitType(event.target.value as ExitType); touchWorkflow("details_entered"); }} className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2">
              <option value="dispatch">Customer dispatch</option>
              <option value="loss">Warehouse loss</option>
            </select>
          </label>
          {exitType === "dispatch" && (
            <label className="block text-sm font-medium text-slate-700">
              Tracking number
              <input required maxLength={60} value={trackingNumber} onChange={(event) => { setTrackingNumber(event.target.value); if (event.target.value) touchWorkflow("details_entered"); }} className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2" />
            </label>
          )}
        </>
      )}

      <button disabled={submitting || Boolean(stockWarning)} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400">
        {submitting ? "Saving…" : direction === "inbound" ? "Confirm goods receipt" : "Confirm stock exit"}
      </button>
    </form>
  );
}
