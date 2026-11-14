import { QuoteCalculator } from "@/components/QuoteCalculator";

export const metadata = { title: "Freight quote" };

export default function FreightQuotePage() {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight text-slate-900">
          Live freight quote
        </h2>
        <p className="mt-1 max-w-3xl text-sm text-slate-600">
          Quote a prospective TrackFlow shipment. Numbers come from{" "}
          <code className="rounded bg-slate-100 px-1">
            @trackflow/business-logic
          </code>
          , the package the Milestone 4 skill{" "}
          <code className="rounded bg-slate-100 px-1">
            freight-quote-invariants
          </code>{" "}
          verifies — run{" "}
          <code className="rounded bg-slate-100 px-1">
            npm run verify:freight-quote
          </code>
          .
        </p>
      </div>
      <QuoteCalculator />
    </div>
  );
}
