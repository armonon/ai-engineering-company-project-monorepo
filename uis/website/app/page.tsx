import Link from "next/link";
import { Section } from "@/components/Section";

/**
 * Migration of the Milestone 1 static site (uis/public-website/index.html)
 * into the Next.js App Router. Every section of the static page is carried
 * over with its content and its anchor id — home, services, coverage, why,
 * contact — so the nav and any existing deep link keep working. The service
 * tiers are the one addition this milestone makes.
 */

const SERVICES = [
  {
    title: "Warehouse Management",
    points: [
      "Storage, picking and packing",
      "Real-time inventory",
      "We operate warehouses in Los Angeles and Zaragoza",
    ],
  },
  {
    title: "Last-Mile Deliveries",
    points: [
      "Certified carrier network in both countries",
      "Unified shipment tracking",
      "Incident and returns management",
    ],
  },
  {
    title: "Reverse Logistics",
    points: [
      "Complete returns management",
      "Inspection and reconditioning",
      "Integration with your sales platform",
    ],
  },
];

const COVERAGE = [
  {
    country: "United States",
    points: ["Warehouse in Los Angeles", "National coverage", "Carriers: UPS, FedEx, DHL"],
  },
  {
    country: "Spain",
    points: ["Warehouse in Zaragoza", "Peninsular and island coverage", "Carriers: MRW, SEUR, DHL"],
  },
];

const WHY = [
  {
    title: "Binational operation",
    detail:
      "The only operator with own infrastructure in the United States and Spain.",
  },
  { title: "+130 professionals", detail: "Dedicated to your logistics." },
  { title: "Own technology", detail: "For total visibility of your inventory." },
  {
    title: "E-commerce specialization",
    detail: "In fashion, electronics, and cosmetics.",
  },
];

const TIERS = [
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
];

export default function HomePage() {
  return (
    <>
      <section
        id="home"
        aria-labelledby="hero-title"
        className="border-b border-slate-200 bg-gradient-to-b from-slate-50 to-white"
      >
        <div className="mx-auto max-w-6xl px-6 py-16 sm:py-24 lg:py-28">
          <p className="text-sm font-semibold uppercase tracking-wider text-blue-800">
            Last-mile delivery · Warehouse management · Since 2009
          </p>
          <h1
            id="hero-title"
            className="mt-3 max-w-3xl text-4xl font-bold tracking-tight text-slate-950 sm:text-5xl lg:text-6xl"
          >
            Logistics that scales with your e-commerce
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-slate-700">
            Warehouse management, last-mile deliveries, and reverse logistics in
            the United States and Spain. Over 15 years helping fashion,
            electronics, and cosmetics brands grow without worrying about
            operations.
          </p>
          <Link
            href="/application"
            className="mt-8 inline-block rounded-md bg-blue-800 px-6 py-3 text-base font-semibold text-white shadow-sm hover:bg-blue-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-800"
          >
            Request information
          </Link>
        </div>
      </section>

      <Section
        id="services"
        eyebrow="What we do"
        title="Services"
        className="border-t border-slate-100"
      >
        <p className="-mt-6 mb-8 max-w-2xl text-slate-700">
          Everything between your online checkout and your customer&apos;s front
          door.
        </p>
        <div className="grid gap-6 md:grid-cols-3">
          {SERVICES.map((service) => (
            <article
              key={service.title}
              className="rounded-lg border border-slate-200 bg-white p-6"
            >
              <h3 className="text-xl font-semibold">{service.title}</h3>
              <ul className="mt-4 list-disc space-y-2 pl-5 text-slate-700">
                {service.points.map((point) => (
                  <li key={point}>{point}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </Section>

      <Section
        id="coverage"
        eyebrow="Where we operate"
        title="Coverage"
        className="border-t border-slate-100 bg-slate-50"
      >
        <div className="grid gap-6 sm:grid-cols-2">
          {COVERAGE.map((area) => (
            <article
              key={area.country}
              className="rounded-lg border border-slate-200 bg-white p-6"
            >
              <h3 className="text-xl font-semibold">{area.country}</h3>
              <ul className="mt-4 list-disc space-y-2 pl-5 text-slate-700">
                {area.points.map((point) => (
                  <li key={point}>{point}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </Section>

      <Section
        id="why"
        eyebrow="Why us"
        title="Why TrackFlow"
        className="border-t border-slate-100"
      >
        <ul className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {WHY.map((reason) => (
            <li
              key={reason.title}
              className="rounded-lg border border-slate-200 bg-white p-6"
            >
              <h3 className="font-semibold">{reason.title}</h3>
              <p className="mt-2 text-slate-700">{reason.detail}</p>
            </li>
          ))}
        </ul>
      </Section>

      <Section
        id="pricing"
        eyebrow="Service tiers"
        title="Every shipment fits one of three tiers."
        className="border-t border-slate-100 bg-slate-50"
      >
        <div className="grid gap-6 sm:grid-cols-3">
          {TIERS.map((tier) => (
            <div
              key={tier.name}
              className="flex flex-col rounded-lg border border-slate-200 bg-white p-6"
            >
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                {tier.name}
              </p>
              <p className="mt-2 text-3xl font-semibold tracking-tight">
                {tier.time}
              </p>
              <p className="mt-3 flex-1 text-sm text-slate-600">{tier.detail}</p>
            </div>
          ))}
        </div>
      </Section>

      <section
        id="contact"
        aria-labelledby="contact-title"
        className="bg-slate-900 text-white"
      >
        <div className="mx-auto max-w-6xl px-6 py-16 sm:py-20">
          <h2
            id="contact-title"
            className="text-3xl font-bold tracking-tight"
          >
            Contact
          </h2>
          <address className="mt-6 grid gap-4 not-italic sm:grid-cols-3">
            <p>
              <span className="block text-sm text-slate-300">Email</span>
              <a
                href="mailto:comercial@trackflow.com"
                className="font-semibold underline underline-offset-4 hover:text-blue-200"
              >
                comercial@trackflow.com
              </a>
            </p>
            <p>
              <span className="block text-sm text-slate-300">Los Angeles</span>
              <a
                href="tel:+12135550147"
                className="font-semibold underline underline-offset-4 hover:text-blue-200"
              >
                +1 213 555 0147
              </a>
            </p>
            <p>
              <span className="block text-sm text-slate-300">Zaragoza</span>
              <a
                href="tel:+34976123456"
                className="font-semibold underline underline-offset-4 hover:text-blue-200"
              >
                +34 976 123 456
              </a>
            </p>
          </address>
          <Link
            href="/application"
            className="mt-8 inline-block rounded-md bg-white px-6 py-3 font-semibold text-slate-900 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
          >
            Request information
          </Link>
        </div>
      </section>
    </>
  );
}
