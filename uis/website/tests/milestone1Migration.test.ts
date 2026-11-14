/**
 * Guards the Milestone 1 → Next.js migration.
 *
 * The first submission of this milestone rebuilt the public site from
 * CONTEXT.md and lost sections the static site had. These tests read the
 * App Router sources and fail if a section, its anchor, or the structured
 * data stops being carried over.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

// npm runs a workspace script with the workspace root as cwd.
const read = (relative: string) =>
  readFileSync(path.resolve(process.cwd(), relative), "utf8");

const page = read("app/page.tsx");
const layout = read("app/layout.tsx");

test("every Milestone 1 section is present with its anchor", () => {
  for (const id of ["home", "services", "coverage", "why", "contact"]) {
    assert.ok(
      page.includes(`id="${id}"`),
      `the migrated page dropped the "${id}" section`,
    );
  }
});

test("the main navigation links to every Milestone 1 section", () => {
  for (const href of [
    "/#home",
    "/#services",
    "/#coverage",
    "/#why",
    "/#contact",
  ]) {
    assert.ok(layout.includes(href), `navigation is missing ${href}`);
  }
});

test("Milestone 1 section content survived the migration", () => {
  for (const phrase of [
    "Logistics that scales with your e-commerce",
    "Warehouse Management",
    "Last-Mile Deliveries",
    "Reverse Logistics",
    "Carriers: UPS, FedEx, DHL",
    "Carriers: MRW, SEUR, DHL",
    "Binational operation",
    "+130 professionals",
    "Own technology",
    "E-commerce specialization",
    "comercial@trackflow.com",
    "+1 213 555 0147",
    "+34 976 123 456",
  ]) {
    assert.ok(page.includes(phrase), `the migrated page dropped "${phrase}"`);
  }
});

test("the Schema.org Organization markup survived the migration", () => {
  for (const phrase of [
    '"@type": "Organization"',
    "foundingDate",
    "Los Angeles",
    "Zaragoza",
    "application/ld+json",
  ]) {
    assert.ok(layout.includes(phrase), `layout is missing ${phrase}`);
  }
});

test("the information-request page is reachable from the landing page", () => {
  assert.ok(
    page.includes('href="/application"'),
    "the landing page no longer links to the information-request form",
  );
  assert.ok(
    layout.includes('href="/application"'),
    "the header no longer links to the information-request form",
  );
});

test("the accessibility affordances of the static site survived", () => {
  assert.ok(layout.includes("Skip to content"), "skip link is missing");
  assert.ok(layout.includes('id="main"'), "main landmark is missing");
  assert.ok(
    layout.includes('aria-label="Main navigation"'),
    "navigation landmark label is missing",
  );
});
