/**
 * Freight-quote implementation for TrackFlow.
 *
 * Authoritative — see CONTEXT.md and rule MONO-1. UIs and services
 * must import this module; never re-implement the formula.
 */

export type Country = "US" | "ES";
export type Zone = "metro" | "regional" | "remote";
export type ServiceTier = "standard" | "express" | "priority";
export type Currency = "USD" | "EUR";

export interface QuoteInput {
  country: Country;
  originZone: Zone;
  destinationZone: Zone;
  serviceTier: ServiceTier;
  distanceKm: number;
  weightKg: number;
}

export interface QuoteBreakdown {
  base: number;
  distance: number;
  weight: number;
  tierMultiplier: number;
}

export interface QuoteResult {
  currency: Currency;
  serviceTier: ServiceTier;
  totalPrice: number;
  breakdown: QuoteBreakdown;
}

// Prices are in the destination currency (see CONTEXT.md units). US list
// rates mirror the UPS sample carrier in the official Milestone 2 briefing.
const BASE_FEE: Record<Country, number> = {
  US: 5, // USD
  ES: 4, // EUR
};

const PRICE_PER_KM: Record<Country, number> = {
  US: 0.05, // USD
  ES: 0.28, // EUR
};

const PRICE_PER_KG: Record<Country, number> = {
  US: 1.2, // USD
  ES: 0.6, // EUR
};

const TIER_MULTIPLIER: Record<ServiceTier, number> = {
  standard: 1.0,
  express: 1.35,
  priority: 1.8,
};

const ZONE_UPLIFT: Record<Zone, number> = {
  metro: 1.0,
  regional: 1.15,
  remote: 1.4,
};

/**
 * Country → currency mapping. Kept as a function so the invariant is
 * declared in exactly one place and picked up by the
 * freight-quote-invariants skill.
 */
export function currencyForCountry(country: Country): Currency {
  return country === "US" ? "USD" : "EUR";
}

export function isPriorityEligible(input: {
  originZone: Zone;
  destinationZone: Zone;
}): boolean {
  return input.originZone === "metro" && input.destinationZone === "metro";
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

/**
 * Compute a freight quote for a single shipment.
 *
 * Throws when the input violates a CONTEXT.md invariant — never
 * returns a "zero quote" for invalid input.
 */
export function quoteShipment(input: QuoteInput): QuoteResult {
  if (!(input.weightKg > 0)) {
    throw new Error("weightKg must be greater than 0");
  }
  if (!(input.distanceKm > 0)) {
    throw new Error("distanceKm must be greater than 0");
  }
  if (input.serviceTier === "priority" && !isPriorityEligible(input)) {
    throw new Error(
      "priority service tier requires both zones=metro (CONTEXT.md § Constraints)",
    );
  }

  const base = BASE_FEE[input.country];
  const distanceCost = PRICE_PER_KM[input.country] * input.distanceKm;
  const weightCost = PRICE_PER_KG[input.country] * input.weightKg;
  const zoneUplift =
    (ZONE_UPLIFT[input.originZone] + ZONE_UPLIFT[input.destinationZone]) / 2;
  const tierMultiplier = TIER_MULTIPLIER[input.serviceTier];

  const raw = (base + distanceCost + weightCost) * zoneUplift * tierMultiplier;

  return {
    currency: currencyForCountry(input.country),
    serviceTier: input.serviceTier,
    totalPrice: round2(raw),
    breakdown: {
      base: round2(base),
      distance: round2(distanceCost),
      weight: round2(weightCost),
      tierMultiplier,
    },
  };
}
