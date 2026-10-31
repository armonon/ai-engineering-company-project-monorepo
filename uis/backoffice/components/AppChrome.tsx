"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PUBLIC_ROUTES } from "@/lib/auth";
import { activeNavigationHref, BACKOFFICE_NAV as NAV } from "@/lib/navigation";
import { useAuth } from "@/components/AuthProvider";
import { Avatar, LiveDot } from "@/components/ui/Showcase";

/**
 * Sidebar + header. Rendered only for authenticated views — the
 * login and register pages get their own full-screen shell instead.
 */
export function AppChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const isPublic = PUBLIC_ROUTES.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`),
  );

  // /login and /register render bare, with no chrome around them.
  if (isPublic) return <>{children}</>;

  const activeHref = activeNavigationHref(
    pathname,
    NAV.map((item) => item.href),
  );

  const navigationLinks = (mobile = false) =>
    NAV.map((item) => {
      const active = item.href === activeHref;
      return (
        <Link
          key={item.href}
          href={item.href}
          aria-current={active ? "page" : undefined}
          className={`relative rounded-lg px-3 py-2 transition-all duration-200 ${mobile ? "whitespace-nowrap" : ""} ${
            active
              ? mobile
                ? "bg-slate-900 text-white"
                : "bg-gradient-to-r from-blue-600/30 to-violet-600/10 font-semibold text-white shadow-inner ring-1 ring-inset ring-white/10"
              : mobile
                ? "text-slate-700 hover:bg-slate-100"
                : "text-slate-300 hover:translate-x-0.5 hover:bg-white/5 hover:text-white"
          }`}
        >
          {active && !mobile ? (
            <span className="absolute inset-y-1.5 left-0 w-1 rounded-r-full bg-gradient-to-b from-blue-400 to-violet-400" aria-hidden="true" />
          ) : null}
          {item.label}
        </Link>
      );
    });

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 overflow-y-auto bg-gradient-to-b from-slate-950 via-slate-900 to-indigo-950 text-slate-100 md:block">
        <div className="flex h-16 items-center gap-3 border-b border-white/10 px-4">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-blue-500 to-violet-600 text-xs font-bold text-white shadow-lg shadow-blue-500/30">
            TF
          </span>
          <span>
            <span className="block text-sm font-semibold leading-tight">TrackFlow</span>
            <span className="block text-[11px] text-slate-400">Backoffice</span>
          </span>
        </div>
        <nav className="flex flex-col gap-0.5 p-3 text-sm">
          {navigationLinks()}
        </nav>
        <div className="mx-3 mb-4 mt-2 rounded-xl bg-white/5 p-3 text-[11px] text-slate-400 ring-1 ring-inset ring-white/10">
          <p className="flex items-center gap-2 font-semibold text-slate-200">
            <LiveDot tone="emerald" /> Systems live
          </p>
          <p className="mt-1">Los Angeles · Zaragoza</p>
        </div>
      </aside>

      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-slate-200/70 bg-white/80 px-4 backdrop-blur md:px-6">
          <span className="text-sm font-semibold text-slate-900">
            TrackFlow Backoffice
          </span>
          <div className="flex items-center gap-3">
            <span className="hidden items-center gap-2 text-xs text-slate-500 sm:flex">
              {user?.email ? <Avatar name={user.profile?.name || user.email} size="sm" /> : null}
              Signed in as <strong className="text-slate-700">{user?.email ?? "…"}</strong>
            </span>
            <button
              type="button"
              onClick={logout}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm transition-colors hover:bg-slate-50"
            >
              Sign out
            </button>
          </div>
        </header>
        <nav
          aria-label="Mobile backoffice navigation"
          className="overflow-x-auto border-b border-slate-200 bg-white md:hidden"
        >
          <div className="flex min-w-max gap-1 p-2 text-sm font-medium">
            {navigationLinks(true)}
          </div>
        </nav>
        <main className="flex-1 p-4 md:p-8">{children}</main>
      </div>
    </div>
  );
}
