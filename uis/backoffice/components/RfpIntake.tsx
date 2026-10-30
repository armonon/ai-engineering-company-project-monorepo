"use client";

import { useCallback, useEffect, useState } from "react";
import {
  decideRfpApproval,
  fetchRfpTicket,
  fetchRfpTickets,
  RfpTicket,
  startRfpApproval,
  startRfpGeneration,
  uploadRfp,
} from "@/lib/rfp";
import {
  consumeRfpNotificationStream,
  RfpTicketCreatedData,
} from "@/lib/rfp-notifications";

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
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [liveArrivals, setLiveArrivals] = useState<RfpTicketCreatedData[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setTickets(await fetchRfpTickets());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load RFP tickets.");
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  useEffect(() => {
    const controller = new AbortController();
    void consumeRfpNotificationStream(
      (event) => {
        setLiveArrivals((current) => {
          if (current.some((item) => item.ticket_id === event.data.ticket_id)) return current;
          return [event.data, ...current].slice(0, 5);
        });
        void fetchRfpTicket(event.data.ticket_id).then((ticket) => {
          setTickets((current) => {
            const withoutDuplicate = current.filter(
              (item) => item.ticket_id !== ticket.ticket_id,
            );
            return [ticket, ...withoutDuplicate];
          });
        });
      },
      () => void load(),
      controller.signal,
    );
    return () => controller.abort();
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

  async function beginApproval(ticketId: string) {
    setBusyTicket(ticketId);
    setError("");
    try {
      await startRfpApproval(ticketId);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not start approval.");
    } finally {
      setBusyTicket("");
    }
  }

  async function decide(
    ticketId: string,
    departmentId: string,
    decision: "approve" | "reject" | "request_changes",
  ) {
    const key = `${ticketId}:${departmentId}`;
    setBusyTicket(key);
    setError("");
    try {
      await decideRfpApproval(ticketId, departmentId, decision, reasons[key] ?? "");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not record the decision.");
    } finally {
      setBusyTicket("");
    }
  }

  return (
    <div className="space-y-6">
      {liveArrivals.length ? (
        <section
          aria-live="assertive"
          className="rounded-xl border border-blue-300 bg-blue-50 p-5 shadow-sm"
        >
          <p className="text-xs font-semibold uppercase tracking-widest text-blue-700">
            Live commercial notification
          </p>
          <h2 className="mt-1 text-lg font-semibold text-slate-950">
            New RFP ticket needs processing
          </h2>
          <ul className="mt-3 space-y-2">
            {liveArrivals.map((arrival) => (
              <li key={arrival.ticket_id} className="rounded-lg bg-white p-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-semibold text-slate-950">
                    {arrival.client_name} · {arrival.client_country}
                  </span>
                  <span className="rounded-full bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-800">
                    {arrival.status}
                  </span>
                </div>
                <p className="mt-1 font-mono text-xs text-slate-500">
                  {arrival.ticket_id} · {arrival.rfp_id ?? "RFP id pending"}
                </p>
                <p className="mt-1 text-xs text-slate-600">
                  {arrival.services_requested.join(", ")}
                </p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
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
            {(ticket.status === "under_evaluation" || ticket.status === "needs_human_review") ? (
              <button
                type="button"
                onClick={() => void beginApproval(ticket.ticket_id)}
                disabled={busyTicket === ticket.ticket_id}
                className="mt-4 rounded-md bg-violet-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {busyTicket === ticket.ticket_id ? "Preparing approvals…" : "Start department approvals"}
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
                    {section.approval_status === "waiting_for_approval" ? (
                      <div className="mt-4 border-t border-slate-200 pt-3">
                        <p className="text-sm font-semibold text-slate-900">
                          Decision for {section.contact}
                        </p>
                        <textarea
                          aria-label={`Reason for ${section.department_id}`}
                          value={reasons[`${ticket.ticket_id}:${section.department_id}`] ?? ""}
                          onChange={(event) => setReasons((current) => ({
                            ...current,
                            [`${ticket.ticket_id}:${section.department_id}`]: event.target.value,
                          }))}
                          placeholder="Optional decision note"
                          className="mt-2 min-h-20 w-full rounded-md border border-slate-300 p-2 text-sm"
                        />
                        <div className="mt-2 flex flex-wrap gap-2">
                          {(["approve", "request_changes", "reject"] as const).map((decision) => (
                            <button
                              key={decision}
                              type="button"
                              disabled={busyTicket === `${ticket.ticket_id}:${section.department_id}`}
                              onClick={() => void decide(ticket.ticket_id, section.department_id, decision)}
                              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-800 disabled:opacity-50"
                            >
                              {decision.replaceAll("_", " ")}
                            </button>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    {section.approval_status === "approved" ? (
                      <p className="mt-3 text-sm font-semibold text-emerald-700">
                        Approved by {section.contact}
                      </p>
                    ) : null}
                  </section>
                ))}
              </div>
            ) : null}
            {ticket.final_document ? (
              <details className="mt-5 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
                <summary className="cursor-pointer font-semibold text-emerald-900">
                  Final approved proposal · {ticket.final_document.currency}
                </summary>
                <div className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-800">
                  {ticket.final_document.content}
                </div>
              </details>
            ) : null}
          </article>
        ))}
      </section>
    </div>
  );
}
