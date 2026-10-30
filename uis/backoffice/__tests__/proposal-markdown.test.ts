import { parseInline, parseProposalMarkdown } from "@/lib/proposal-markdown";

describe("RFP proposal markdown", () => {
  it("splits bold segments without losing surrounding text", () => {
    expect(parseInline("**Client:** ModaViva, S.L.")).toEqual([
      { text: "Client:", bold: true },
      { text: " ModaViva, S.L.", bold: false },
    ]);
  });

  it("parses headings, joins hard-wrapped paragraphs, and keeps bullets", () => {
    const blocks = parseProposalMarkdown(
      [
        "# TrackFlow Logistics Proposal",
        "",
        "**Ticket:** abc",
        "",
        "## Warehouse Operations",
        "",
        "TrackFlow will confirm storage capacity",
        "before launch.",
        "",
        "### RFP requirements and open questions",
        "- OPEN QUESTION: confirm monthly order volume.",
        "- Confirm storage capacity, unit basis,",
        "  and onboarding lead time.",
      ].join("\n"),
    );

    expect(blocks.map((block) => block.type)).toEqual([
      "heading",
      "paragraph",
      "heading",
      "paragraph",
      "heading",
      "list",
    ]);
    expect(blocks[0]).toMatchObject({ level: 1 });
    expect(blocks[3]).toEqual({
      type: "paragraph",
      segments: [{ text: "TrackFlow will confirm storage capacity before launch.", bold: false }],
    });
    expect(blocks[5]).toEqual({
      type: "list",
      items: [
        [{ text: "OPEN QUESTION: confirm monthly order volume.", bold: false }],
        [{ text: "Confirm storage capacity, unit basis, and onboarding lead time.", bold: false }],
      ],
    });
  });

  it("renders the volume-discount table and keeps label lines separate", () => {
    const blocks = parseProposalMarkdown(
      [
        "**Ticket:** abc",
        "**Client:** ModaViva, S.L.",
        "",
        "| Monthly volume | Discount |",
        "| --- | ---: |",
        "| 0-4,999 orders | 0% |",
        "| 10,000+ orders | 6% |",
      ].join("\n"),
    );
    expect(blocks.map((block) => block.type)).toEqual(["paragraph", "paragraph", "table"]);
    expect(blocks[2]).toEqual({
      type: "table",
      header: ["Monthly volume", "Discount"],
      rows: [
        ["0-4,999 orders", "0%"],
        ["10,000+ orders", "6%"],
      ],
    });
  });

  it("treats markup characters as text, never HTML", () => {
    const [block] = parseProposalMarkdown("<script>alert(1)</script>");
    expect(block).toEqual({
      type: "paragraph",
      segments: [{ text: "<script>alert(1)</script>", bold: false }],
    });
  });
});
