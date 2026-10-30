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
  metadataBase: new URL(
    "https://trackflow-coursework-demo.armonon.chatgpt.site",
  ),
  title: {
    default: "TrackFlow · Last-mile delivery and warehousing SaaS",
    template: "%s · TrackFlow",
  },
  description:
    "TrackFlow gives mid-market retailers in the United States and Spain a single tool for warehouse operations, driver dispatch, and shipment tracking.",
  openGraph: {
    title: "TrackFlow · Last-mile delivery and warehousing SaaS",
    description:
      "Warehouse, dispatch, and shipment tracking for mid-market retailers in the United States and Spain.",
    type: "website",
    locale: "en_US",
    images: [
      {
        url: "/og.png",
        width: 1730,
        height: 909,
        alt: "TrackFlow — One workspace for every shipment.",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "TrackFlow · Last-mile delivery and warehousing SaaS",
    description:
      "Warehouse, dispatch, and shipment tracking for retailers in the United States and Spain.",
    images: ["/og.png"],
  },
  robots: { index: true, follow: true },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} bg-white text-slate-900 antialiased`}
      >
        <header className="border-b border-slate-200 bg-white/80 backdrop-blur">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
            <Link href="/" className="flex items-center gap-2">
              <span className="grid h-8 w-8 place-items-center rounded-md bg-slate-900 text-sm font-bold text-white">
                TF
              </span>
              <span className="text-sm font-semibold">TrackFlow</span>
            </Link>
            <nav
              aria-label="Primary"
              className="flex items-center gap-3 text-xs text-slate-700 sm:gap-5 sm:text-sm"
            >
              <a href="#offering" className="hover:text-slate-900">
                Product
              </a>
              <a href="#countries" className="hover:text-slate-900">
                Countries
              </a>
              <a
                href="#pricing"
                className="hidden hover:text-slate-900 sm:inline"
              >
                Pricing
              </a>
              <a
                href="#contact"
                className="rounded-md bg-slate-900 px-3 py-1.5 text-white hover:bg-slate-800"
              >
                Talk to sales
              </a>
            </nav>
          </div>
        </header>
        <main id="main">{children}</main>
        <footer className="border-t border-slate-200 bg-slate-50">
          <div className="mx-auto flex max-w-6xl flex-col gap-2 px-6 py-6 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
            <span>© {new Date().getFullYear()} TrackFlow. All rights reserved.</span>
            <span>Operating in the United States and Spain.</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
