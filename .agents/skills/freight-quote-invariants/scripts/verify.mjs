#!/usr/bin/env node
/**
 * freight-quote-invariants — verify skill acceptance criteria.
 *
 * Prints "freight-quote-invariants: OK (N assertions)" on success,
 * exits 0. On failure, names the CONTEXT.md section and the code
 * path that diverged and exits 1.
 *
 * Zero runtime deps outside Node stdlib.
 */

import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const repoRoot = resolve(__dirname, "../../../..");
const pkgDist = resolve(repoRoot, "packages/business-logic/dist/src/index.js");

if (!existsSync(pkgDist)) {
  console.error(
    `error: packages/business-logic is not built.\n` +
      `remedy: from the repo root, run \`npm run bootstrap\` (or \`npm run build --workspace @trackflow/business-logic\`).`,
  );
  process.exit(1);
}

const { quoteShipment, currencyForCountry, isPriorityEligible } = await import(
  pkgDist
);

let count = 0;
function check(label, fn) {
  try {
    fn();
    count += 1;
  } catch (err) {
    console.error(`\nfreight-quote-invariants: FAIL — ${label}`);
    console.error(err instanceof Error ? err.message : String(err));
    process.exit(1);
  }
}

// (1) Currency by country (CONTEXT.md § Constraints — Units)
check("currency = USD for country=US", () => {
  assert.equal(currencyForCountry("US"), "USD");
});
check("currency = EUR for country=ES", () => {
  assert.equal(currencyForCountry("ES"), "EUR");
});
check("an ES quote is never priced in USD or $", () => {
  const q = quoteShipment({
    country: "ES",
    originZone: "metro",
    destinationZone: "metro",
    serviceTier: "standard",
    distanceKm: 5,
    weightKg: 1,
  });
  assert.notEqual(q.currency, "USD");
  assert.notEqual(q.currency, "$");
});

// (2) Priority tier eligibility (CONTEXT.md § Constraints — Priority tier)
check("priority tier eligible when metro→metro", () => {
  assert.equal(
    isPriorityEligible({ originZone: "metro", destinationZone: "metro" }),
    true,
  );
});
check("priority tier quoted metro→metro in both countries", () => {
  for (const country of ["US", "ES"]) {
    assert.equal(
      quoteShipment({
        country,
        originZone: "metro",
        destinationZone: "metro",
        serviceTier: "priority",
        distanceKm: 10,
        weightKg: 2,
      }).serviceTier,
      "priority",
    );
  }
});
check("priority tier rejected when either zone is not metro", () => {
  assert.throws(() =>
    quoteShipment({
      country: "US",
      originZone: "metro",
      destinationZone: "regional",
      serviceTier: "priority",
      distanceKm: 10,
      weightKg: 2,
    }),
  );
});

// (3) Weight and distance floors (CONTEXT.md § Domain vocabulary / § Constraints)
check("weightKg <= 0 throws", () => {
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
});
check("distanceKm <= 0 throws", () => {
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

// (4) Deterministic pricing
check("two consecutive calls return identical results", () => {
  const input = {
    country: "US",
    originZone: "metro",
    destinationZone: "regional",
    serviceTier: "express",
    distanceKm: 42,
    weightKg: 3.5,
  };
  assert.deepEqual(quoteShipment(input), quoteShipment(input));
});

// (5) Rounding
check("totalPrice rounded to 2 decimals (no float drift)", () => {
  const q = quoteShipment({
    country: "ES",
    originZone: "remote",
    destinationZone: "metro",
    serviceTier: "express",
    distanceKm: 173,
    weightKg: 7.3,
  });
  assert.equal(q.totalPrice, Number(q.totalPrice.toFixed(2)));
});

console.log(`freight-quote-invariants: OK (${count} assertions)`);
