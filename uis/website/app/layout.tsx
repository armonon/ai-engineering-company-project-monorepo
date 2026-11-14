import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://trackflow.com"),
  title: {
    default: "TrackFlow — Logistics that scales with your e-commerce",
    template: "%s · TrackFlow",
  },
  description:
    "Warehouse management, last-mile deliveries, and reverse logistics in the United States and Spain for fashion, electronics, and cosmetics brands.",
  alternates: { canonical: "/" },
  openGraph: {
    title: "TrackFlow — Logistics that scales with your e-commerce",
    description:
      "Warehouse management, last-mile deliveries, and reverse logistics in the United States and Spain.",
    type: "website",
    locale: "en_US",
  },
  robots: { index: true, follow: true },
};

/**
 * Organization schema carried over verbatim from the Milestone 1 static
 * site, so the migration does not lose its structured data.
 */
const ORGANIZATION_SCHEMA = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "TrackFlow",
  description:
    "Warehouse management and last-mile deliveries for e-commerce",
  url: "https://trackflow.com",
  foundingDate: "2009",
  address: [
    {
      "@type": "PostalAddress",
      addressCountry: "US",
      addressLocality: "Los Angeles",
      addressRegion: "California",
    },
    {
      "@type": "PostalAddress",
      addressCountry: "ES",
      addressLocality: "Zaragoza",
      addressRegion: "Aragón",
    },
  ],
  contactPoint: {
    "@type": "ContactPoint",
    telephone: "+1-213-555-0147",
    contactType: "sales",
    availableLanguage: ["Spanish", "English"],
  },
  sameAs: ["https://linkedin.com/company/trackflow"],
  areaServed: [
    { "@type": "Country", name: "United States" },
    { "@type": "Country", name: "Spain" },
  ],
};

const NAV = [
  { href: "/#home", label: "Home" },
  { href: "/#services", label: "Services" },
  { href: "/#coverage", label: "Coverage" },
  { href: "/#why", label: "Why TrackFlow" },
  { href: "/#contact", label: "Contact" },
];

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} bg-white text-slate-900 antialiased`}
      >
        <script
          type="application/ld+json"
          // Static, author-controlled object — not user input.
          dangerouslySetInnerHTML={{
            __html: JSON.stringify(ORGANIZATION_SCHEMA),
          }}
        />
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:shadow"
        >
          Skip to content
        </a>

        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-4">
            <Link
              href="/"
              className="flex items-center gap-2 text-lg font-bold tracking-tight text-slate-900"
            >
              <span className="grid h-8 w-8 place-items-center rounded-md bg-slate-900 text-sm font-bold text-white">
                TF
              </span>
              TrackFlow
            </Link>
            <nav aria-label="Main navigation">
              <ul className="flex flex-wrap items-center gap-1 text-sm font-medium text-slate-700 sm:gap-2">
                {NAV.map((item) => (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className="rounded-md px-3 py-2 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-700"
                    >
                      {item.label}
                    </Link>
                  </li>
                ))}
                <li>
                  <Link
                    href="/application"
                    className="rounded-md bg-blue-800 px-3 py-2 text-white hover:bg-blue-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-800"
                  >
                    Request information
                  </Link>
                </li>
              </ul>
            </nav>
          </div>
        </header>

        <main id="main">{children}</main>

        <footer className="border-t border-slate-200 bg-white">
          <div className="mx-auto flex max-w-6xl flex-col gap-2 px-6 py-6 text-sm text-slate-700 sm:flex-row sm:items-center sm:justify-between">
            <p>
              © {new Date().getFullYear()} TrackFlow. All rights reserved.
            </p>
            <a
              href="https://linkedin.com/company/trackflow"
              rel="noopener"
              className="font-medium underline underline-offset-4 hover:text-slate-950"
              aria-label="TrackFlow on LinkedIn"
            >
              LinkedIn
            </a>
          </div>
        </footer>
      </body>
    </html>
  );
}
