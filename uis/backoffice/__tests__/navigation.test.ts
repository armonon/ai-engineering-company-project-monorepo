import { activeNavigationHref } from "@/lib/navigation";

const hrefs = [
  "/",
  "/backoffice/inventory/products",
  "/backoffice/inventory/orders",
  "/suppliers",
];

describe("activeNavigationHref", () => {
  it("selects only the most specific matching destination", () => {
    expect(
      activeNavigationHref("/backoffice/inventory/orders", hrefs),
    ).toBe(
      "/backoffice/inventory/orders",
    );
  });

  it("keeps the inventory parent active for its form routes", () => {
    expect(
      activeNavigationHref(
        "/backoffice/inventory/products/details",
        hrefs,
      ),
    ).toBe(
      "/backoffice/inventory/products",
    );
  });

  it("does not treat the root destination as a prefix", () => {
    expect(activeNavigationHref("/suppliers", hrefs)).toBe("/suppliers");
    expect(activeNavigationHref("/", hrefs)).toBe("/");
  });
});
