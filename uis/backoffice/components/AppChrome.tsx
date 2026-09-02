"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PUBLIC_ROUTES } from "@/lib/auth";
import { activeNavigationHref } from "@/lib/navigation";
import { useAuth } from "@/components/AuthProvider";

const NAV = [
  { href: "/", label: "Freight quote" },
  { href: "/incident-manager", label: "Incident manager" },
  { href: "/incidents", label: "Incident analysis" },
  { href: "/backoffice/inventory/products", label: "Inventory" },
  { href: "/backoffice/inventory/orders", label: "Stock movements" },
  { href: "/suppliers", label: "Supplier directory" },
  { href: "/account/profile", label: "My profile" },
  { href: "/account/change-password", label: "Change password" },
];

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
          className={`rounded-md px-3 py-2 ${mobile ? "whitespace-nowrap" : ""} ${
            active
              ? mobile
                ? "bg-slate-900 text-white"
                : "bg-white/10 text-white"
              : mobile
                ? "text-slate-700 hover:bg-slate-100"
                : "text-slate-100 hover:bg-white/10"
          }`}
        >
          {item.label}
        </Link>
      );
    });

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-56 shrink-0 border-r border-slate-200 bg-slate-900 text-slate-100 md:block">
        <div className="flex h-14 items-center gap-2 border-b border-white/10 px-4">
          <span className="grid h-7 w-7 place-items-center rounded-md bg-white text-xs font-bold text-slate-900">
            TF
          </span>
          <span className="text-sm font-semibold">Backoffice</span>
        </div>
        <nav className="flex flex-col gap-1 p-3 text-sm">
          {navigationLinks()}
          <span className="rounded-md px-3 py-2 text-slate-400">
            Dispatch <em className="text-xs">(soon)</em>
          </span>
        </nav>
      </aside>

      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-4 md:px-6">
          <span className="text-sm font-semibold text-slate-900">
            TrackFlow Backoffice
          </span>
          <div className="flex items-center gap-3">
            <span className="hidden text-xs text-slate-500 sm:inline">
              Signed in as <strong>{user?.email ?? "…"}</strong>
            </span>
            <button
              type="button"
              onClick={logout}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
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
        <main className="flex-1 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
