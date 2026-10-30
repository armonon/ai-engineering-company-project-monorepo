# CONTEXT — TrackFlow

> Assigned company context for this monorepo. Everything the AI or a
> human contributor builds here must be consistent with the domain
> below. When something is not covered here, follow the pattern that
> already exists in the repo — do not invent parallel domain concepts.
>
> The official company briefing is [`BRIEFING.md`](./BRIEFING.md). This
> file condenses it into engineering rules; when the two disagree on a
> company fact (markets, cities, people, carriers), `BRIEFING.md` wins.

## The company

**TrackFlow** is a last-mile delivery and warehouse management company
founded in 2009 in Los Angeles. It operates in two markets — the **United
States** and **Spain** — with warehouses in **Los Angeles** and
**Zaragoza**, and sells to mid-market e-commerce brands. The product is used
by three kinds of people:

- **Warehouse operators** — pick, pack, and load shipments; work on
  handheld scanners inside a warehouse. Their screens must be legible
  under bad lighting and usable with gloves.
- **Dispatchers** — assign routes to drivers, monitor delayed
  shipments, respond to incidents. Work at a desktop.
- **Account managers** (TrackFlow employees) — onboard new retailers,
  configure their tenants, run pricing quotes with customers on
  video calls. Work in a browser, need fast round-trips.

## Domain vocabulary (canonical)

Use these names verbatim in code, schemas, and copy. Do not
paraphrase.

| Concept          | Definition                                                                                     |
| ---------------- | ---------------------------------------------------------------------------------------------- |
| **Shipment**     | A parcel or set of parcels moving from one origin to one destination under a single tracking id. |
| **Route**        | An ordered sequence of Shipments assigned to a Driver for a single working day.                  |
| **Driver**       | A person authorised to execute a Route. Each Driver belongs to exactly one Warehouse.            |
| **Warehouse**    | A physical location where shipments enter, are sorted, and depart. TrackFlow runs two: Los Angeles (`LA`, country `US`) and Zaragoza (`ZGZ`, country `ES`). |
| **Tenant**       | A retailer or operator paying for TrackFlow. Tenants have their own users, warehouses, drivers, and pricing agreement. |
| **Service tier** | Contractual promise: `standard` (48 h), `express` (24 h), `priority` (same-day, metro→metro only). |
| **Zone**         | Geographic grouping used for pricing. Metro / regional / remote.                                 |
| **Incident**     | Anything that stops a Shipment from meeting its Service tier promise (address error, damaged, refused, etc.). |

## Constraints and non-negotiables

- **Units**: distances in **kilometres**, weights in **kilograms**,
  prices in **USD** for US tenants and **EUR** for ES tenants —
  never mixed currencies, never miles.
- **Time**: everything internal is stored in UTC and rendered in the
  tenant's warehouse timezone. Dates as ISO-8601 `YYYY-MM-DD`.
- **Tenant isolation**: no cross-tenant data ever leaves the API for
  a request scoped to a tenant. There is no "global" view of
  shipments across tenants for anyone outside TrackFlow ops.
- **Priority tier**: only available for Shipments whose origin **and**
  destination Zones are both `metro`, in either served country.
- **Freight quote formula (Milestone 2 business logic)** —
  authoritative implementation lives in
  [`packages/business-logic/src/freight-quote.ts`](./packages/business-logic/src/freight-quote.ts).
  Do not duplicate this formula in the frontend or in another
  package. UIs consume the exported `quoteShipment` function.

## Scoped context precedence

This file remains authoritative for shared TrackFlow vocabulary, shipment
pricing, currencies, service tiers, and the public product. The inventory
milestone has a narrower source of truth at
[`docs/CONTEXT-inventory-trackflow.md`](./docs/CONTEXT-inventory-trackflow.md).
For `/inventory` models, endpoints, seeded SKUs, and the warehouse agent, that
scoped document adds the inventory-specific fields. It does not override the
US/ES freight-quote or tenant-pricing rules in this file.

## Product surfaces in this repo

| Surface                                | Audience                       | Lives in            |
| -------------------------------------- | ------------------------------ | ------------------- |
| Corporate website                      | Prospective customers, public  | `./uis/website`     |
| Backoffice (internal admin app)        | TrackFlow account managers     | `./uis/backoffice`  |
| Business-logic library (freight quote) | Consumed by backoffice + APIs  | `./packages/business-logic` |
| Backend services                       | Programmatic consumers         | `./services/`       |
| AI agents                              | Internal support & dispatchers | `./agents/`, `./.openclaw/` |

## Out of scope for this monorepo

- Customer-facing consumer app (a shipper does not log into TrackFlow
  directly — they are notified by their retailer).
- Driver mobile app (native, lives in a separate repo).
- Shipment-pricing or tenant expansion beyond the United States and Spain.
