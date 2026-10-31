"use client";

import { useCallback, useEffect, useState } from "react";
import { ProposalDocument } from "@/components/ProposalDocument";
import {
  Avatar,
  LiveDot,
  RfpProgress,
  Spinner,
  StatTile,
  StatusPill,
  TONE,
} from "@/components/ui/Showcase";
import { departmentName, humanize, shortId } from "@/lib/presentation";
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
          className="animate-slide-in relative overflow-hidden rounded-2xl border border-blue-200 bg-white p-5 shadow-lg shadow-blue-500/10"
        >
          <div className="pointer-events-none absolute inset-x-0 top-0 h-1 animate-shimmer bg-[linear-gradient(90deg,#3b82f6,#8b5cf6,#06b6d4,#3b82f6)] bg-[length:200%_100%]" aria-hidden="true" />
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-2 rounded-full bg-blue-600 px-2.5 py-1 text-[11px] font-bold uppercase tracking-widest text-white">
              <LiveDot tone="cyan" /> Live
            </span>
            <p className="text-xs font-semibold uppercase tracking-widest text-blue-700">
              Commercial notification
            </p>
          </div>
          <h2 className="mt-2 text-lg font-semibold text-slate-950">
            New RFP ticket needs processing
          </h2>
          <ul className="mt-3 space-y-2">
            {liveArrivals.map((arrival, index) => (
              <li
                key={arrival.ticket_id}
                className="animate-fade-up flex flex-wrap items-center gap-3 rounded-xl bg-gradient-to-r from-blue-50 to-violet-50 p-3 text-sm"
                style={{ animationDelay: `${index * 80}ms` }}
              >
                <Avatar name={arrival.client_name} size="sm" />
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-slate-950">
                    {arrival.client_name} · {arrival.client_country}
                  </p>
                  <p className="text-xs text-slate-600">
                    {arrival.services_requested.map(humanize).join(" · ")}
                    {arrival.rfp_id ? <span className="ml-2 font-mono text-slate-400">{arrival.rfp_id}</span> : null}
                  </p>
                </div>
                <StatusPill
                  status={tickets.find((ticket) => ticket.ticket_id === arrival.ticket_id)?.status ?? arrival.status}
                />
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <form
        onSubmit={submit}
        className="group animate-fade-up rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
      >
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center">
          <label
            htmlFor="rfp-document"
            className={`flex flex-1 cursor-pointer items-center gap-4 rounded-xl border-2 border-dashed p-4 transition-colors ${
              file ? "border-blue-400 bg-blue-50/60" : "border-slate-200 hover:border-blue-300 hover:bg-slate-50"
            }`}
          >
            <span className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-blue-500 to-violet-600 text-white shadow-md shadow-blue-500/20">
              <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 16V4m0 0-4 4m4-4 4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
              </svg>
            </span>
            <span className="min-w-0">
              <span className="block text-sm font-semibold text-slate-900">
                {file ? file.name : "Client RFP (PDF)"}
              </span>
              <span className="block text-xs text-slate-500">
                {file
                  ? `${(file.size / 1024).toFixed(1)} KB · ready to upload`
                  : "Choose a PDF. TrackFlow converts, classifies, and routes it in the background."}
              </span>
            </span>
            <input
              id="rfp-document"
              type="file"
              accept="application/pdf,.pdf"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              className="sr-only"
            />
          </label>
          <button
            type="submit"
            disabled={!file || busy}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 px-5 py-3 text-sm font-semibold text-white shadow-md shadow-blue-600/20 transition-all hover:-translate-y-0.5 hover:shadow-lg disabled:translate-y-0 disabled:opacity-40 disabled:shadow-none"
          >
            {busy ? <><Spinner /> Creating ticket…</> : "Upload RFP"}
          </button>
        </div>
        {error ? <p role="alert" className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
      </form>

      <section className="space-y-5" aria-live="polite">
        {tickets.length === 0 ? (
          <div className="animate-fade-up rounded-2xl border border-dashed border-slate-300 bg-white/60 p-10 text-center">
            <p className="text-sm font-semibold text-slate-700">No RFP tickets yet</p>
            <p className="mt-1 text-sm text-slate-500">Upload a client request to watch it flow through intake, drafting, evaluation, and approval.</p>
          </div>
        ) : null}
        {tickets.map((ticket, ticketIndex) => (
          <article
            key={ticket.ticket_id}
            className="animate-fade-up overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm"
            style={{ animationDelay: `${ticketIndex * 60}ms` }}
          >
            <div className="border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white p-5">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <Avatar name={ticket.metadata?.client_name ?? "RFP"} size="lg" />
                  <div>
                    <h2 className="text-lg font-semibold text-slate-950">
                      {ticket.metadata?.client_name ?? "Document under analysis"}
                    </h2>
                    <p className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                      {ticket.rfp_id ? <span className="font-semibold text-slate-700">{ticket.rfp_id}</span> : null}
                      <span className="rounded-md bg-slate-100 px-1.5 py-0.5 font-mono" title={ticket.ticket_id}>
                        #{shortId(ticket.ticket_id)}
                      </span>
                    </p>
                  </div>
                </div>
                <StatusPill status={ticket.status} />
              </div>
              <RfpProgress status={ticket.status} />
            </div>

            <div className="p-5">
              {ticket.processing_error ? (
                <p role="alert" className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{ticket.processing_error}</p>
              ) : null}
              {ticket.sales_summary ? <p className="text-sm leading-6 text-slate-700">{ticket.sales_summary.replaceAll("_", " ")}</p> : null}

              {ticket.metadata ? (
                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <StatTile label="Market" value={`${ticket.metadata.client_country} · ${ticket.metadata.currency}`} tone="blue" />
                  <StatTile
                    label="Monthly volume"
                    value={ticket.metadata.monthly_volume?.toLocaleString() ?? "Open question"}
                    tone={ticket.metadata.monthly_volume ? "emerald" : "amber"}
                    delay={60}
                  />
                  <StatTile label="Deadline" value={ticket.metadata.deadline ?? "—"} tone="violet" delay={120} />
                  <StatTile label="Departments" value={ticket.metadata.departments_needed.length} hint={ticket.metadata.departments_needed.map(departmentName).join(" · ")} tone="cyan" delay={180} />
                </div>
              ) : null}

              {ticket.status === "intake_complete" ? (
                <button
                  type="button"
                  onClick={() => void generate(ticket.ticket_id)}
                  disabled={busyTicket === ticket.ticket_id}
                  className="mt-5 inline-flex items-center gap-2 rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white shadow-md transition-all hover:-translate-y-0.5 hover:bg-slate-800 hover:shadow-lg disabled:opacity-50"
                >
                  {busyTicket === ticket.ticket_id ? <><Spinner /> Generating…</> : <>Generate evaluated response <span aria-hidden="true">→</span></>}
                </button>
              ) : null}
              {(ticket.status === "under_evaluation" || ticket.status === "needs_human_review") ? (
                <button
                  type="button"
                  onClick={() => void beginApproval(ticket.ticket_id)}
                  disabled={busyTicket === ticket.ticket_id}
                  className="mt-5 inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-violet-600/20 transition-all hover:-translate-y-0.5 hover:shadow-lg disabled:opacity-50"
                >
                  {busyTicket === ticket.ticket_id ? <><Spinner /> Preparing approvals…</> : <>Start department approvals <span aria-hidden="true">→</span></>}
                </button>
              ) : null}

              {ticket.sections.length ? (
                <div className="mt-6 grid items-start gap-4 lg:grid-cols-2">
                  {ticket.sections.map((section, sectionIndex) => {
                    const decisionKey = `${ticket.ticket_id}:${section.department_id}`;
                    const evaluation = section.evaluation_result;
                    const checks = evaluation
                      ? [
                          ["Readability", evaluation.readability.pass],
                          ["Relevance", evaluation.relevance.pass],
                          ["Compliance", evaluation.compliance.pass],
                        ] as const
                      : [];
                    return (
                      <section
                        key={section.department_id}
                        className={`animate-fade-up rounded-2xl border p-4 transition-shadow hover:shadow-md ${
                          section.approval_status === "approved" ? "border-emerald-200 bg-emerald-50/40" : "border-slate-200 bg-slate-50/60"
                        }`}
                        style={{ animationDelay: `${sectionIndex * 90}ms` }}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-center gap-3">
                            <Avatar name={section.contact} />
                            <div>
                              <h3 className="font-semibold text-slate-900">{departmentName(section.department_id)}</h3>
                              <p className="text-xs text-slate-500">Owner · {section.contact}</p>
                            </div>
                          </div>
                          {section.approval_status === "approved" ? (
                            <span className="animate-pop inline-flex items-center gap-1 rounded-full bg-emerald-600 px-2.5 py-1 text-xs font-semibold text-white shadow-sm">
                              <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="currentColor" aria-hidden="true"><path fillRule="evenodd" d="M16.7 5.3a1 1 0 0 1 0 1.4l-7.5 7.5a1 1 0 0 1-1.4 0L3.3 9.7a1 1 0 1 1 1.4-1.4l3.8 3.8 6.8-6.8a1 1 0 0 1 1.4 0Z" clipRule="evenodd" /></svg>
                              Approved
                            </span>
                          ) : section.approval_status && section.approval_status !== "pending" ? (
                            <StatusPill status={section.approval_status} />
                          ) : null}
                        </div>

                        <ul className="mt-3 space-y-1.5 text-sm text-slate-700">
                          {section.key_aspects.map((aspect) => (
                            <li key={aspect} className="flex gap-2">
                              <span className={`mt-2 h-1.5 w-1.5 shrink-0 rounded-full ${aspect.startsWith("OPEN QUESTION") ? "bg-amber-500" : "bg-blue-400"}`} aria-hidden="true" />
                              <span className={aspect.startsWith("OPEN QUESTION") ? "font-medium text-amber-800" : undefined}>{aspect}</span>
                            </li>
                          ))}
                        </ul>

                        {evaluation ? (
                          <div className="mt-4">
                            <p className={`text-sm font-semibold ${evaluation.overall_pass ? "text-emerald-700" : "text-orange-700"}`}>
                              {evaluation.overall_pass ? "Evaluation passed" : "Human review required"}
                            </p>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {checks.map(([name, pass], checkIndex) => (
                                <span
                                  key={name}
                                  className={`animate-pop inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${pass ? TONE.emerald.pill : TONE.red.pill}`}
                                  style={{ animationDelay: `${checkIndex * 90}ms` }}
                                >
                                  {pass ? "✓" : "✕"} {name}
                                </span>
                              ))}
                            </div>
                            {evaluation.feedback_for_generator ? (
                              <p className="mt-2 text-xs text-orange-800">{evaluation.feedback_for_generator}</p>
                            ) : null}
                          </div>
                        ) : null}

                        {section.draft_content ? (
                          <details className="mt-4 rounded-xl border border-slate-200 bg-white p-3">
                            <summary className="cursor-pointer text-sm font-semibold text-slate-900">
                              Proposal draft
                            </summary>
                            <div className="mt-3">
                              <ProposalDocument markdown={section.draft_content} />
                            </div>
                          </details>
                        ) : null}

                        {section.approval_status === "waiting_for_approval" ? (
                          <div className="mt-4 rounded-xl border border-cyan-200 bg-white p-3">
                            <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                              <LiveDot tone="cyan" /> Decision for {section.contact}
                            </p>
                            <textarea
                              aria-label={`Reason for ${section.department_id}`}
                              value={reasons[decisionKey] ?? ""}
                              onChange={(event) => setReasons((current) => ({
                                ...current,
                                [decisionKey]: event.target.value,
                              }))}
                              placeholder="Optional decision note"
                              className="mt-2 min-h-20 w-full rounded-lg border border-slate-200 p-2 text-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-200"
                            />
                            <div className="mt-2 flex flex-wrap gap-2">
                              {(["approve", "request_changes", "reject"] as const).map((decision) => (
                                <button
                                  key={decision}
                                  type="button"
                                  disabled={busyTicket === decisionKey}
                                  onClick={() => void decide(ticket.ticket_id, section.department_id, decision)}
                                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all hover:-translate-y-0.5 disabled:opacity-50 ${
                                    decision === "approve"
                                      ? "bg-emerald-600 text-white shadow-sm hover:bg-emerald-500"
                                      : decision === "reject"
                                        ? "border border-red-200 bg-white text-red-700 hover:bg-red-50"
                                        : "border border-amber-200 bg-white text-amber-800 hover:bg-amber-50"
                                  }`}
                                >
                                  {humanize(decision)}
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
                    );
                  })}
                </div>
              ) : null}

              {ticket.final_document ? (
                <details className="animate-fade-up group/final mt-6 overflow-hidden rounded-2xl border border-emerald-200 bg-white shadow-sm">
                  <summary className="flex cursor-pointer items-center justify-between gap-3 bg-gradient-to-r from-emerald-500 to-teal-600 px-5 py-4 text-white">
                    <span className="flex items-center gap-3">
                      <span className="grid h-9 w-9 place-items-center rounded-full bg-white/20" aria-hidden="true">
                        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" /></svg>
                      </span>
                      <span>
                        <span className="block font-semibold">Final approved proposal · {ticket.final_document.currency}</span>
                        <span className="block text-xs text-emerald-50">Every department signed off · ready to send</span>
                      </span>
                    </span>
                    <span className="text-sm font-semibold transition-transform group-open/final:rotate-180" aria-hidden="true">⌄</span>
                  </summary>
                  <div className="bg-emerald-50/40 p-5">
                    <ProposalDocument markdown={ticket.final_document.content} />
                  </div>
                </details>
              ) : null}
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}
