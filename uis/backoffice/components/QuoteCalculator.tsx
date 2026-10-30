"use client";

import { useMemo, useState } from "react";
import {
  quoteShipment,
  type Country,
  type QuoteInput,
  type QuoteResult,
  type ServiceTier,
  type Zone,
} from "@trackflow/business-logic";

const COUNTRIES: Country[] = ["US", "ES"];
const ZONES: Zone[] = ["metro", "regional", "remote"];
const TIERS: ServiceTier[] = ["standard", "express", "priority"];

const CURRENCY_LOCALE: Record<Country, string> = {
  US: "en-US",
  ES: "es-ES",
};

function formatMoney(value: number, currency: string, country: Country) {
  return new Intl.NumberFormat(CURRENCY_LOCALE[country], {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(value);
}

const DEFAULTS: QuoteInput = {
  country: "US",
  originZone: "metro",
  destinationZone: "metro",
  serviceTier: "standard",
  distanceKm: 12,
  weightKg: 2.5,
};

export function QuoteCalculator() {
  const [input, setInput] = useState<QuoteInput>(DEFAULTS);

  const outcome = useMemo<
    | { ok: true; quote: QuoteResult }
    | { ok: false; error: string }
  >(() => {
    try {
      return { ok: true, quote: quoteShipment(input) };
    } catch (err) {
      return {
        ok: false,
        error: err instanceof Error ? err.message : String(err),
      };
    }
  }, [input]);

  function patch<K extends keyof QuoteInput>(key: K, value: QuoteInput[K]) {
    setInput((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,420px)]">
      <form
        onSubmit={(e) => e.preventDefault()}
        className="space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Country">
            <select
              className={selectCls}
              value={input.country}
              onChange={(e) => patch("country", e.target.value as Country)}
            >
              {COUNTRIES.map((c) => (
                <option key={c} value={c}>
                  {c === "US" ? "United States (USD)" : "Spain (EUR)"}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Service tier">
            <select
              className={selectCls}
              value={input.serviceTier}
              onChange={(e) =>
                patch("serviceTier", e.target.value as ServiceTier)
              }
            >
              {TIERS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Origin zone">
            <select
              className={selectCls}
              value={input.originZone}
              onChange={(e) => patch("originZone", e.target.value as Zone)}
            >
              {ZONES.map((z) => (
                <option key={z} value={z}>
                  {z}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Destination zone">
            <select
              className={selectCls}
              value={input.destinationZone}
              onChange={(e) =>
                patch("destinationZone", e.target.value as Zone)
              }
            >
              {ZONES.map((z) => (
                <option key={z} value={z}>
                  {z}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Distance (km)">
            <input
              type="number"
              min={1}
              step="0.5"
              className={inputCls}
              value={input.distanceKm}
              onChange={(e) => patch("distanceKm", Number(e.target.value))}
            />
          </Field>

          <Field label="Weight (kg)">
            <input
              type="number"
              min={0.1}
              step="0.1"
              className={inputCls}
              value={input.weightKg}
              onChange={(e) => patch("weightKg", Number(e.target.value))}
            />
          </Field>
        </div>
      </form>

      <aside className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Live quote
        </h2>
        {outcome.ok ? (
          <>
            <p className="mt-2 text-4xl font-semibold tracking-tight text-slate-900">
              {formatMoney(
                outcome.quote.totalPrice,
                outcome.quote.currency,
                input.country,
              )}
            </p>
            <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">
              {outcome.quote.currency} · tier{" "}
              <strong>{outcome.quote.serviceTier}</strong>
            </p>
            <dl className="mt-6 space-y-2 text-sm">
              <Row label="Base fee" value={outcome.quote.breakdown.base} country={input.country} currency={outcome.quote.currency} />
              <Row label="Distance cost" value={outcome.quote.breakdown.distance} country={input.country} currency={outcome.quote.currency} />
              <Row label="Weight cost" value={outcome.quote.breakdown.weight} country={input.country} currency={outcome.quote.currency} />
              <div className="flex justify-between border-t border-slate-100 pt-2 text-slate-600">
                <dt>Tier multiplier</dt>
                <dd>×{outcome.quote.breakdown.tierMultiplier}</dd>
              </div>
            </dl>
          </>
        ) : (
          <div className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            <p className="font-medium">Cannot quote</p>
            <p className="mt-1">{outcome.error}</p>
          </div>
        )}
        <p className="mt-6 border-t border-slate-100 pt-4 text-xs text-slate-500">
          Computed by{" "}
          <code className="rounded bg-slate-100 px-1">
            quoteShipment
          </code>{" "}
          from{" "}
          <code className="rounded bg-slate-100 px-1">
            @trackflow/business-logic
          </code>
          . Nothing about this formula lives in the backoffice —
          see rule MONO-1.
        </p>
      </aside>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium text-slate-700">{label}</span>
      {children}
    </label>
  );
}

function Row({
  label,
  value,
  currency,
  country,
}: {
  label: string;
  value: number;
  currency: string;
  country: Country;
}) {
  return (
    <div className="flex justify-between text-slate-600">
      <dt>{label}</dt>
      <dd className="font-mono">
        {formatMoney(value, currency, country)}
      </dd>
    </div>
  );
}

const inputCls =
  "w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-400";
const selectCls =
  "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-400";
