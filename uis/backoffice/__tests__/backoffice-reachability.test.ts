import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { PUBLIC_ROUTES } from "@/lib/auth";
import { BACKOFFICE_NAV } from "@/lib/navigation";

const root = join(__dirname, "..");

function files(directory: string, match: (name: string) => boolean): string[] {
  return readdirSync(directory).flatMap((name) => {
    const path = join(directory, name);
    if (statSync(path).isDirectory()) return files(path, match);
    return match(name) ? [path] : [];
  });
}

function routeOf(page: string): string {
  const segments = relative(join(root, "app"), page).split(sep).slice(0, -1);
  return `/${segments.join("/")}`;
}

const pages = files(join(root, "app"), (name) => name === "page.tsx");
const sources = [
  ...files(join(root, "app"), (name) => /\.tsx?$/.test(name)),
  ...files(join(root, "components"), (name) => /\.tsx?$/.test(name)),
].map((path) => readFileSync(path, "utf8"));

/** Literal hrefs anywhere in the UI, with query strings and template tails cut. */
const linkedHrefs = new Set(
  sources.flatMap((source) =>
    [...source.matchAll(/href=\{?[`"](\/[^`"?$]*)/g)].map((match) =>
      match[1].replace(/\/$/, "") || "/",
    ),
  ),
);
const navHrefs = new Set(BACKOFFICE_NAV.map((item) => item.href));

describe("backoffice reachability (capstone: every module reachable by clicking)", () => {
  const routes = pages
    .filter((page) => !/^\s*redirect\(/m.test(readFileSync(page, "utf8")))
    .map(routeOf)
    .filter((route) => !route.includes("["))
    .filter((route) => !PUBLIC_ROUTES.some((publicRoute) => route === publicRoute));

  it.each(routes)("%s has a sidebar entry or an in-app link", (route) => {
    expect(navHrefs.has(route) || linkedHrefs.has(route)).toBe(true);
  });

  it("every sidebar entry points at a real page", () => {
    const existing = new Set(pages.map(routeOf));
    for (const { href } of BACKOFFICE_NAV) {
      expect(existing.has(href)).toBe(true);
    }
  });

  it("exposes the telemetry report and weekly reporting modules", () => {
    expect(navHrefs.has("/telemetry")).toBe(true);
    expect(navHrefs.has("/reporting")).toBe(true);
  });
});
