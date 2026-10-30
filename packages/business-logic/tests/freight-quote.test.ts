import { test } from "node:test";
import assert from "node:assert/strict";

import {
  quoteShipment,
  currencyForCountry,
  isPriorityEligible,
} from "../src/index.js";

test("currency by country matches CONTEXT.md", () => {
  assert.equal(currencyForCountry("US"), "USD");
  assert.equal(currencyForCountry("ES"), "EUR");
});

test("priority eligibility only for metro→metro, in either country", () => {
  assert.equal(
    isPriorityEligible({ originZone: "metro", destinationZone: "metro" }),
    true,
  );
  assert.equal(
    isPriorityEligible({ originZone: "metro", destinationZone: "regional" }),
    false,
  );
  assert.equal(
    isPriorityEligible({ originZone: "remote", destinationZone: "metro" }),
    false,
  );
});

test("priority tier outside eligibility throws", () => {
  assert.throws(
    () =>
      quoteShipment({
        country: "US",
        originZone: "metro",
        destinationZone: "regional",
        serviceTier: "priority",
        distanceKm: 10,
        weightKg: 2,
      }),
    /priority/,
  );
});

test("priority tier is quoted for metro→metro in Spain and the US", () => {
  for (const country of ["US", "ES"] as const) {
    const quote = quoteShipment({
      country,
      originZone: "metro",
      destinationZone: "metro",
      serviceTier: "priority",
      distanceKm: 10,
      weightKg: 2,
    });
    assert.equal(quote.serviceTier, "priority");
  }
});

test("US quote uses the Milestone 2 UPS list rates in USD", () => {
  // (5 + 0.05 × 120 + 1.2 × 3) × metro uplift 1 × standard 1 = 14.60 USD
  const quote = quoteShipment({
    country: "US",
    originZone: "metro",
    destinationZone: "metro",
    serviceTier: "standard",
    distanceKm: 120,
    weightKg: 3,
  });
  assert.equal(quote.currency, "USD");
  assert.equal(quote.totalPrice, 14.6);
  assert.deepEqual(quote.breakdown, {
    base: 5,
    distance: 6,
    weight: 3.6,
    tierMultiplier: 1,
  });
});

test("weight and distance must be > 0", () => {
  assert.throws(() =>
    quoteShipment({
      country: "US",
      originZone: "metro",
      destinationZone: "metro",
      serviceTier: "standard",
      distanceKm: 10,
      weightKg: 0,
    }),
  );
  assert.throws(() =>
    quoteShipment({
      country: "US",
      originZone: "metro",
      destinationZone: "metro",
      serviceTier: "standard",
      distanceKm: 0,
      weightKg: 2,
    }),
  );
});

test("quote is deterministic and rounded to 2 decimals", () => {
  const input = {
    country: "ES" as const,
    originZone: "regional" as const,
    destinationZone: "metro" as const,
    serviceTier: "express" as const,
    distanceKm: 42,
    weightKg: 3.5,
  };
  const a = quoteShipment(input);
  const b = quoteShipment(input);

  assert.deepEqual(a, b);
  assert.equal(a.currency, "EUR");
  assert.equal(a.serviceTier, "express");
  // rounding: no more than 2 decimals in totalPrice
  assert.equal(a.totalPrice, Number(a.totalPrice.toFixed(2)));
  assert.ok(a.totalPrice > 0);
});
