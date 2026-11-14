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
  title: {
    default: "TrackFlow Backoffice",
    template: "%s · TrackFlow Backoffice",
  },
  description:
    "Internal admin app for TrackFlow account managers — inventory operations, carrier selection, and freight quoting.",
  robots: { index: false, follow: false },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} min-h-screen bg-slate-50 text-slate-900 antialiased`}
      >
        <div className="flex min-h-screen">
          <aside className="hidden w-56 shrink-0 border-r border-slate-200 bg-slate-900 text-slate-100 md:block">
            <div className="flex h-14 items-center gap-2 border-b border-white/10 px-4">
              <span className="grid h-7 w-7 place-items-center rounded-md bg-white text-xs font-bold text-slate-900">
                TF
              </span>
              <span className="text-sm font-semibold">Backoffice</span>
            </div>
            <nav className="flex flex-col gap-1 p-3 text-sm">
              <Link
                href="/"
                className="rounded-md bg-white/10 px-3 py-2 text-white"
              >
                Inventory operations
              </Link>
              <Link
                href="/freight-quote"
                className="rounded-md px-3 py-2 text-slate-200 hover:bg-white/10 hover:text-white"
              >
                Freight quote
              </Link>
              <span className="rounded-md px-3 py-2 text-slate-400">
                Tenants <em className="text-xs">(soon)</em>
              </span>
              <span className="rounded-md px-3 py-2 text-slate-400">
                Dispatch <em className="text-xs">(soon)</em>
              </span>
              <span className="rounded-md px-3 py-2 text-slate-400">
                Incidents <em className="text-xs">(soon)</em>
              </span>
            </nav>
          </aside>
          <div className="flex min-h-screen flex-1 flex-col">
            <header className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-4 md:px-6">
              <h1 className="text-sm font-semibold text-slate-900">
                TrackFlow operations
              </h1>
              <span className="text-xs text-slate-500">
                Signed in as <strong>account-manager@trackflow</strong>
              </span>
            </header>
            <main className="flex-1 p-4 md:p-6">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
