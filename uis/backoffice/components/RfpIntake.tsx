"use client";

import { useCallback, useEffect, useState } from "react";
import {
  fetchRfpTicket,
  fetchRfpTickets,
  RfpTicket,
  startRfpGeneration,
  uploadRfp,
} from "@/lib/rfp";

const STATUS_STYLE: Record<string, string> = {
  analyzing: "bg-amber-100 text-amber-800",
  intake_complete: "bg-emerald-100 text-emerald-800",
  discarded: "bg-slate-200 text-slate-700",
  drafting: "bg-blue-100 text-blue-800",
  under_evaluation: "bg-violet-100 text-violet-800",
  needs_human_review: "bg-orange-100 text-orange-800",
  waiting_for_approval: "bg-cyan-100 text-cyan-800",
  done: "bg-emerald-100 text-emerald-800",
};

function isProcessing(ticket: RfpTicket) {
  return (
    ticket.status === "analyzing" ||
    ticket.status === "drafting" ||
    (ticket.status === "under_evaluation" &&
      ticket.sections.some((section) => !section.evaluation_result))
  );
}

export function RfpIntake() {
  const [tickets, setTickets] = useState<RfpTicket[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [busyTicket, setBusyTicket] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setTickets(await fetchRfpTickets());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load RFP tickets.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!tickets.some(isProcessing)) return;
    const timer = window.setInterval(async () => {
      const refreshed = await Promise.all(
        tickets.map((ticket) =>
          isProcessing(ticket)
            ? fetchRfpTicket(ticket.ticket_id)
            : Promise.resolve(ticket),
        ),
      );
      setTickets(refreshed);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [tickets]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      await uploadRfp(file);
      setFile(null);
      const input = document.querySelector<HTMLInputElement>("#rfp-document");
      if (input) input.value = "";
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The upload failed.");
    } finally {
      setBusy(false);
    }
  }

  async function generate(ticketId: string) {
    setBusyTicket(ticketId);
    setError("");
    try {
      await startRfpGeneration(ticketId);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Response generation failed.");
    } finally {
      setBusyTicket("");
    }
  }

  return (
    <div className="space-y-6">
      <form onSubmit={submit} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <label htmlFor="rfp-document" className="block text-sm font-semibold text-slate-900">
          Client RFP (PDF)
        </label>
        <p className="mt-1 text-sm text-slate-600">
          The upload returns immediately. TrackFlow converts, classifies, and routes it in the background.
        </p>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
          <input
            id="rfp-document"
            type="file"
            accept="application/pdf,.pdf"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={!file || busy}
            className="rounded-md bg-blue-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {busy ? "Creating ticket…" : "Upload RFP"}
          </button>
        </div>
        {error ? <p role="alert" className="mt-3 text-sm text-red-700">{error}</p> : null}
      </form>

      <section className="space-y-4" aria-live="polite">
        {tickets.length === 0 ? (
          <p className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">
            No RFP tickets yet.
          </p>
        ) : null}
        {tickets.map((ticket) => (
          <article key={ticket.ticket_id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="font-mono text-xs text-slate-500">{ticket.ticket_id}</p>
                <h2 className="mt-1 font-semibold text-slate-950">
                  {ticket.metadata?.client_name ?? "Document under analysis"}
                </h2>
              </div>
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_STYLE[ticket.status]}`}>
                {ticket.status.replaceAll("_", " ")}
              </span>
            </div>
            {ticket.processing_error ? (
              <p role="alert" className="mt-3 text-sm text-red-700">{ticket.processing_error}</p>
            ) : null}
            {ticket.sales_summary ? <p className="mt-3 text-sm text-slate-700">{ticket.sales_summary}</p> : null}
            {ticket.status === "intake_complete" ? (
              <button
                type="button"
                onClick={() => void generate(ticket.ticket_id)}
                disabled={busyTicket === ticket.ticket_id}
                className="mt-4 rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {busyTicket === ticket.ticket_id ? "Generating…" : "Generate evaluated response"}
              </button>
            ) : null}
            {ticket.metadata ? (
              <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                <div><dt className="text-slate-500">Market</dt><dd className="font-medium">{ticket.metadata.client_country} · {ticket.metadata.currency}</dd></div>
                <div><dt className="text-slate-500">Monthly volume</dt><dd className="font-medium">{ticket.metadata.monthly_volume?.toLocaleString() ?? "Open question"}</dd></div>
                <div><dt className="text-slate-500">Estimated tokens</dt><dd className="font-medium">{ticket.metadata.readability_metrics.estimated_tokens}</dd></div>
              </dl>
            ) : null}
            {ticket.sections.length ? (
              <div className="mt-5 grid gap-3 lg:grid-cols-2">
                {ticket.sections.map((section) => (
                  <section key={section.department_id} className="rounded-lg bg-slate-50 p-4">
                    <h3 className="font-semibold capitalize text-slate-900">{section.department_id}</h3>
                    <p className="text-xs text-slate-500">Contact: {section.contact}</p>
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
                      {section.key_aspects.map((aspect) => <li key={aspect}>{aspect}</li>)}
                    </ul>
                    {section.draft_content ? (
                      <details className="mt-4 rounded-md border border-slate-200 bg-white p-3">
                        <summary className="cursor-pointer text-sm font-semibold text-slate-900">
                          Proposal draft
                        </summary>
                        <div className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-700">
                          {section.draft_content}
                        </div>
                      </details>
                    ) : null}
                    {section.evaluation_result ? (
                      <div className="mt-3 text-sm">
                        <p className={section.evaluation_result.overall_pass ? "font-semibold text-emerald-700" : "font-semibold text-orange-700"}>
                          {section.evaluation_result.overall_pass ? "Evaluation passed" : "Human review required"}
                        </p>
                        <p className="mt-1 text-xs text-slate-600">
                          Readability {section.evaluation_result.readability.pass ? "passed" : "failed"} · Relevance {section.evaluation_result.relevance.pass ? "passed" : "failed"} · Compliance {section.evaluation_result.compliance.pass ? "passed" : "failed"}
                        </p>
                        {section.evaluation_result.feedback_for_generator ? (
                          <p className="mt-2 text-xs text-orange-800">{section.evaluation_result.feedback_for_generator}</p>
                        ) : null}
                      </div>
                    ) : null}
                  </section>
                ))}
              </div>
            ) : null}
          </article>
        ))}
      </section>
    </div>
  );
}
