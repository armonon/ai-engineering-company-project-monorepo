This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Inventory API configuration

For direct local development, copy `.env.example` to `.env.local` and keep
the file untracked:

```bash
cp .env.example .env.local
```

`NEXT_PUBLIC_INVENTORY_API_URL` points the authenticated backoffice at the
FastAPI service. Docker Compose leaves that override blank and uses the
same-origin `/trackflow-api` proxy, which reaches the backend container by
its `backend` service name.

The four inventory views use the assignment paths:

- `/backoffice/inventory/products`
- `/backoffice/inventory/orders/inbound`
- `/backoffice/inventory/orders/outbound`
- `/backoffice/inventory/orders`

## Telemetry capture

Set `NEXT_PUBLIC_TELEMETRY_ENDPOINT` in the untracked `.env.local` file. For
native development it is normally:

```text
NEXT_PUBLIC_TELEMETRY_ENDPOINT=http://localhost:8000/telemetry/events
```

All browser capture is centralised in `lib/telemetry.ts`. It validates event
properties against `docs/telemetry/event-schemas.json`, adds the standard
envelope, batches at 20 events or 10 seconds, retries a failed batch three times
with exponential backoff, and flushes pending events with `sendBeacon` when the
tab is hidden. The shared runtime captures navigation, LCP, and uncaught errors;
domain components add business events only at their confirmed decision points.

Additional governed inventory views support the approved event catalogue:

- `/backoffice/inventory/products/new` registers a zero-stock SKU.
- `/backoffice/inventory/audit` compares physical and computed stock without
  mutating it.

See [`../../docs/telemetry/capture-implementation.md`](../../docs/telemetry/capture-implementation.md)
for the complete event-to-component map and privacy contract.

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
