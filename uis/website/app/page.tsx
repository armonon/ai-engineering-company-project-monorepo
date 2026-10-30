import { Section } from "@/components/Section";
import { FeatureCard } from "@/components/FeatureCard";

export default function HomePage() {
  return (
    <>
      {/* Hero */}
      <section className="border-b border-slate-200 bg-gradient-to-b from-white to-slate-50">
        <div className="mx-auto max-w-6xl px-6 py-20 sm:py-28">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Last-mile delivery · Warehouse operations
          </p>
          <h1 className="mt-3 max-w-3xl text-4xl font-semibold tracking-tight text-slate-900 sm:text-5xl">
            One workspace for every shipment your team moves in
            the United States and Spain.
          </h1>
          <p className="mt-5 max-w-2xl text-lg text-slate-600">
            TrackFlow gives mid-market retailers a single tool for
            warehouse operations, driver dispatch, and shipment tracking —
            no more spreadsheets, no more phone-tag with drivers.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href="#contact"
              className="rounded-md bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-800"
            >
              Talk to sales
            </a>
            <a
              href="#offering"
              className="rounded-md border border-slate-300 px-5 py-2.5 text-sm font-medium text-slate-700 hover:bg-white"
            >
              See how it works
            </a>
          </div>
        </div>
      </section>

      {/* Offering */}
      <Section
        id="offering"
        eyebrow="What TrackFlow does"
        title="Three surfaces, one source of truth for every shipment."
      >
        <div className="grid gap-4 sm:grid-cols-3">
          <FeatureCard
            title="Warehouse"
            description="Handheld-scanner-friendly picking, packing, and loading flows. Legible under bad warehouse lighting, usable with gloves."
            icon={<span className="text-sm font-bold">W</span>}
          />
          <FeatureCard
            title="Dispatch"
            description="Assign routes to drivers, monitor delayed shipments, and respond to incidents from one desktop workspace."
            icon={<span className="text-sm font-bold">D</span>}
          />
          <FeatureCard
            title="Tenant ops"
            description="Account managers onboard retailers, configure tenants, and run live pricing quotes during sales calls."
            icon={<span className="text-sm font-bold">T</span>}
          />
        </div>
      </Section>

      {/* Countries */}
      <Section
        id="countries"
        eyebrow="Where we operate"
        title="Deployed in the United States and Spain — priced in local currency."
        className="border-t border-slate-100 bg-slate-50"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <h3 className="text-lg font-semibold">United States</h3>
            <p className="mt-2 text-sm text-slate-600">
              Served from our Los Angeles warehouse. Metropolitan same-day
              delivery available on the priority tier. Prices in USD.
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <h3 className="text-lg font-semibold">Spain</h3>
            <p className="mt-2 text-sm text-slate-600">
              24h express and 48h standard tiers across mainland Spain.
              Prices in EUR.
            </p>
          </div>
        </div>
      </Section>

      {/* Pricing tiers */}
      <Section id="pricing" eyebrow="Service tiers" title="Every shipment fits one of three tiers.">
        <div className="grid gap-4 sm:grid-cols-3">
          {[
            {
              name: "Standard",
              time: "48h",
              detail: "Both countries. Any zone. The default for non-urgent parcels.",
            },
            {
              name: "Express",
              time: "24h",
              detail: "Both countries. Regional and metro zones. Prioritised on route builds.",
            },
            {
              name: "Priority",
              time: "Same day",
              detail: "Both countries, metro→metro only. Reserved for retailers with a priority SLA.",
            },
          ].map((tier) => (
            <div
              key={tier.name}
              className="flex flex-col rounded-lg border border-slate-200 bg-white p-5"
            >
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                {tier.name}
              </p>
              <p className="mt-2 text-3xl font-semibold tracking-tight">
                {tier.time}
              </p>
              <p className="mt-3 flex-1 text-sm text-slate-600">
                {tier.detail}
              </p>
            </div>
          ))}
        </div>
      </Section>

      {/* Contact */}
      <Section
        id="contact"
        eyebrow="Talk to us"
        title="Book a 30-minute call with a TrackFlow account manager."
        className="border-t border-slate-100"
      >
        <div className="grid gap-6 sm:grid-cols-2">
          <div>
            <p className="text-slate-600">
              We&apos;ll walk through your current shipment volume, the
              warehouses you run today, and where TrackFlow would fit.
              No procurement paperwork required for the first call.
            </p>
            <p className="mt-4 text-sm text-slate-500">
              Prefer email?{" "}
              <a
                href="mailto:sales@trackflow.example.com"
                className="text-slate-900 underline"
              >
                sales@trackflow.example.com
              </a>
            </p>
          </div>
          <form className="space-y-3 rounded-lg border border-slate-200 bg-white p-5">
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">
                Company
              </span>
              <input
                required
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">
                Work email
              </span>
              <input
                type="email"
                required
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">
                Country
              </span>
              <select className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400">
                <option>United States</option>
                <option>Spain</option>
              </select>
            </label>
            <button
              type="submit"
              className="w-full rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
            >
              Request a call
            </button>
          </form>
        </div>
      </Section>
    </>
  );
}
