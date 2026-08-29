import {
  buildCandidateQuery,
  resolveTalentApiUrl,
} from "@/lib/talent-api";
import { safeExternalUrl } from "@/lib/talent";

describe("talent pipeline integration", () => {
  it("uses the same-origin talent proxy when no override is provided", () => {
    expect(resolveTalentApiUrl()).toBe("/talent-api");
  });

  it("normalizes an explicit talent API URL", () => {
    expect(resolveTalentApiUrl(" https://talent.example/api/// ")).toBe(
      "https://talent.example/api",
    );
  });

  it("builds the supported candidate filters", () => {
    expect(
      buildCandidateQuery({
        status: "in_progress",
        stage: "technical_interview",
        search: "Ada Lovelace",
        page: 2,
        limit: 25,
      }),
    ).toBe(
      "?status=in_progress&stage=technical_interview&search=Ada+Lovelace&page=2&limit=25",
    );
  });

  it("omits empty filters", () => {
    expect(buildCandidateQuery({ status: "", stage: "", search: "" })).toBe(
      "",
    );
  });

  it("allows HTTP links and rejects unsafe candidate URLs", () => {
    expect(safeExternalUrl("https://linkedin.com/in/ada")).toBe(
      "https://linkedin.com/in/ada",
    );
    expect(safeExternalUrl("javascript:alert(1)")).toBeNull();
    expect(safeExternalUrl("not a URL")).toBeNull();
  });
});
