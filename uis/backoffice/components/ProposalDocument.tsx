import { parseProposalMarkdown, type InlineSegment } from "@/lib/proposal-markdown";

function Inline({ segments }: { segments: InlineSegment[] }) {
  return (
    <>
      {segments.map((segment, index) =>
        segment.bold ? (
          <strong key={index} className="font-semibold text-slate-900">
            {segment.text}
          </strong>
        ) : (
          <span key={index}>{segment.text}</span>
        ),
      )}
    </>
  );
}

const HEADING_CLASSES = {
  1: "text-lg font-semibold text-slate-950",
  2: "mt-4 text-base font-semibold text-slate-900",
  3: "mt-3 text-sm font-semibold uppercase tracking-wide text-slate-600",
} as const;

/** Renders the synthesized RFP proposal as formatted, readable text. */
export function ProposalDocument({ markdown }: { markdown: string }) {
  return (
    <div className="space-y-2 text-sm leading-6 text-slate-800">
      {parseProposalMarkdown(markdown).map((block, index) => {
        if (block.type === "heading") {
          const Tag = (["h3", "h4", "h5"] as const)[block.level - 1];
          return (
            <Tag key={index} className={HEADING_CLASSES[block.level]}>
              <Inline segments={block.segments} />
            </Tag>
          );
        }
        if (block.type === "table") {
          return (
            <div key={index} className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                <thead className="bg-white/60 text-xs uppercase tracking-wide text-slate-600">
                  <tr>
                    {block.header.map((cell, cellIndex) => (
                      <th key={cellIndex} scope="col" className="px-3 py-2">
                        {cell}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {block.rows.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {row.map((cell, cellIndex) => (
                        <td key={cellIndex} className="px-3 py-2">
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        if (block.type === "list") {
          return (
            <ul key={index} className="list-disc space-y-1 pl-5">
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>
                  <Inline segments={item} />
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p key={index}>
            <Inline segments={block.segments} />
          </p>
        );
      })}
    </div>
  );
}
