/**
 * Minimal Markdown parser for the RFP final proposal.
 *
 * The synthesizer emits a small, known subset (#–### headings, "- " bullets,
 * **bold**, hard-wrapped paragraphs). Parsing into plain blocks lets React
 * render it as text nodes — never as injected HTML.
 */

export type InlineSegment = { text: string; bold: boolean };

export type ProposalBlock =
  | { type: "heading"; level: 1 | 2 | 3; segments: InlineSegment[] }
  | { type: "list"; items: InlineSegment[][] }
  | { type: "table"; header: string[]; rows: string[][] }
  | { type: "paragraph"; segments: InlineSegment[] };

function tableCells(line: string): string[] {
  return line
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

export function parseInline(text: string): InlineSegment[] {
  const segments: InlineSegment[] = [];
  const pattern = /\*\*(.+?)\*\*/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    const start = match.index ?? 0;
    if (start > last) segments.push({ text: text.slice(last, start), bold: false });
    segments.push({ text: match[1], bold: true });
    last = start + match[0].length;
  }
  if (last < text.length) segments.push({ text: text.slice(last), bold: false });
  return segments;
}

export function parseProposalMarkdown(markdown: string): ProposalBlock[] {
  const blocks: ProposalBlock[] = [];
  let paragraph: string[] = [];
  let list: string[] | null = null;
  let table: string[][] | null = null;

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push({ type: "paragraph", segments: parseInline(paragraph.join(" ")) });
      paragraph = [];
    }
  };
  const flushList = () => {
    if (list) {
      blocks.push({ type: "list", items: list.map(parseInline) });
      list = null;
    }
  };
  const flushTable = () => {
    if (table) {
      const [header = [], ...rows] = table;
      blocks.push({ type: "table", header, rows });
      table = null;
    }
  };
  const flushAll = () => {
    flushParagraph();
    flushList();
    flushTable();
  };

  for (const raw of markdown.split("\n")) {
    const line = raw.trim();
    const heading = /^(#{1,3})\s+(.*)$/.exec(line);
    if (!line) {
      flushAll();
    } else if (line.startsWith("|")) {
      flushParagraph();
      flushList();
      // Skip the |---|---| separator row.
      if (!/^\|[\s:|-]+\|$/.test(line)) (table ??= []).push(tableCells(line));
    } else if (heading) {
      flushAll();
      blocks.push({
        type: "heading",
        level: heading[1].length as 1 | 2 | 3,
        segments: parseInline(heading[2]),
      });
    } else if (line.startsWith("- ")) {
      flushParagraph();
      flushTable();
      (list ??= []).push(line.slice(2));
    } else if (list) {
      // A wrapped continuation of the previous bullet.
      list[list.length - 1] += ` ${line}`;
    } else {
      flushTable();
      // "**Label:** value" lines are separate facts, not a wrapped sentence.
      if (/^\*\*[^*]+:\*\*/.test(line)) flushParagraph();
      paragraph.push(line);
    }
  }
  flushAll();
  return blocks;
}
