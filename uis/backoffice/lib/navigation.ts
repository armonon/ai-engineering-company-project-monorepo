/** Every backoffice module's entry point, in sidebar order. */
export const BACKOFFICE_NAV: readonly { href: string; label: string }[] = [
  { href: "/", label: "Freight quote" },
  { href: "/incident-manager", label: "Incident manager" },
  { href: "/incidents", label: "Incident analysis" },
  { href: "/backoffice/inventory/products", label: "Inventory" },
  { href: "/backoffice/inventory/orders", label: "Stock movements" },
  { href: "/backoffice/inventory/audit", label: "Inventory audit" },
  { href: "/reporting", label: "Weekly reporting" },
  { href: "/telemetry", label: "Application telemetry" },
  { href: "/knowledge", label: "Sales knowledge" },
  { href: "/rfp", label: "RFP workflow" },
  { href: "/support", label: "CX agent chat" },
  { href: "/observability", label: "Agent observability" },
  { href: "/talent", label: "Talent pipeline" },
  { href: "/suppliers", label: "Supplier directory" },
  { href: "/account/profile", label: "My profile" },
  { href: "/account/change-password", label: "Change password" },
];

export function activeNavigationHref(
  pathname: string,
  hrefs: readonly string[],
): string | undefined {
  return hrefs
    .filter((href) =>
      href === "/"
        ? pathname === "/"
        : pathname === href || pathname.startsWith(`${href}/`),
    )
    .sort((left, right) => right.length - left.length)[0];
}
