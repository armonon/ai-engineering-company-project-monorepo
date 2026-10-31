"use client";

import { useEffect, useRef, useState } from "react";
import {
  applyChatEvent,
  ChatConnectionState,
  ChatMessage,
  SupportChatClient,
} from "@/lib/support-chat";
import { humanize, type Tone } from "@/lib/presentation";
import { Avatar, LiveDot, TONE } from "@/components/ui/Showcase";

const SESSION_KEY = "trackflow.first_line_cx.session_id";

const SUGGESTIONS = [
  "Where is my shipment? Incident 72",
  "How many Wireless Earbuds Pro are in stock?",
  "What is the returns window in Spain?",
];

const CAPABILITIES: { title: string; detail: string; tone: Tone }[] = [
  { title: "Live ticket status", detail: "Reads incidents through the OAuth-protected company-tools MCP server.", tone: "blue" },
  { title: "Read-only stock checks", detail: "Looks up inventory per warehouse; it can never change stock.", tone: "cyan" },
  { title: "Guardrails first", detail: "Blocks prompt injection and other customers' orders before any lookup.", tone: "violet" },
  { title: "Human-style control", detail: "Interrupt a reply mid-stream; the partial answer is kept.", tone: "amber" },
];

function sessionId(): string {
  const saved = window.sessionStorage.getItem(SESSION_KEY);
  if (saved) return saved;
  const created = `chat_${window.crypto.randomUUID()}`;
  window.sessionStorage.setItem(SESSION_KEY, created);
  return created;
}

export function SupportChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [connection, setConnection] = useState<ChatConnectionState>("connecting");
  const [error, setError] = useState("");
  const client = useRef<SupportChatClient | null>(null);

  const streaming = messages.some(
    (message) => message.role === "assistant" && message.status === "streaming",
  );

  useEffect(() => {
    const chat = new SupportChatClient(
      sessionId(),
      (event) => {
        if (event.event === "chat_error") {
          setError(String(event.data.message ?? "The live chat failed."));
          return;
        }
        setMessages((current) => applyChatEvent(current, event));
        setError("");
      },
      setConnection,
    );
    client.current = chat;
    chat.connect();
    return () => {
      chat.close();
      client.current = null;
    };
  }, []);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    try {
      client.current?.send(text, streaming);
      setDraft("");
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The message could not be sent.");
    }
  }

  const tone: Tone =
    connection === "connected" ? "emerald" : connection === "closed" ? "red" : "amber";

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
      <section className="animate-fade-up overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-gradient-to-r from-white to-violet-50/60 px-5 py-4">
          <div className="flex items-center gap-3">
            <Avatar name="Valentina Cruz" />
            <div>
              <p className="text-sm font-semibold text-slate-950">First-line CX agent</p>
              <p className="text-xs text-slate-500">Owned by Valentina Cruz · Customer Experience</p>
            </div>
          </div>
          <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset ${TONE[tone].pill}`}>
            <LiveDot tone={tone} live={connection === "connected"} />
            {humanize(connection)}
          </span>
        </header>

        <div className="min-h-[26rem] space-y-4 bg-slate-50/40 p-5" aria-live="polite">
          {messages.length === 0 ? (
            <div className="animate-fade-up rounded-xl border border-dashed border-slate-200 bg-white p-5 text-sm text-slate-600">
              <p>Ask about shipment tracking, stock, returns, or delivery incidents.</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => setDraft(suggestion)}
                    className="rounded-full bg-violet-50 px-3 py-1.5 text-xs font-medium text-violet-800 ring-1 ring-inset ring-violet-200 transition hover:bg-violet-100"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          {messages.map((message) =>
            message.role === "user" ? (
              <div key={message.message_id} className="flex animate-slide-in justify-end">
                <p className="max-w-xl whitespace-pre-wrap rounded-2xl rounded-br-md bg-gradient-to-br from-blue-600 to-indigo-600 px-4 py-2.5 text-sm text-white shadow-sm">
                  {message.text}
                </p>
              </div>
            ) : (
              <div key={message.message_id} className="flex animate-fade-up items-start gap-3">
                <span aria-hidden="true" className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-600 text-[10px] font-bold text-white shadow-sm ring-2 ring-white">
                  TF
                </span>
                <div className="max-w-2xl rounded-2xl rounded-tl-md bg-white px-4 py-2.5 text-sm text-slate-900 shadow-sm ring-1 ring-slate-200/80">
                  {message.text ? (
                    <p className="whitespace-pre-wrap">{message.text}</p>
                  ) : (
                    <span className="inline-flex gap-1 py-1" aria-label="Agent is typing">
                      {[0, 150, 300].map((delay) => (
                        <span key={delay} className="h-1.5 w-1.5 animate-bounce rounded-full bg-violet-400" style={{ animationDelay: `${delay}ms` }} />
                      ))}
                    </span>
                  )}
                  {message.status === "streaming" ? (
                    <span className="mt-2 flex items-center gap-2 text-xs font-medium text-violet-700">
                      <LiveDot tone="violet" />
                      Responding live…
                    </span>
                  ) : null}
                  {message.status === "interrupted" ? (
                    <span className="mt-2 inline-block animate-pop rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800 ring-1 ring-inset ring-amber-200">
                      Interrupted
                    </span>
                  ) : null}
                </div>
              </div>
            ),
          )}
        </div>

        <form onSubmit={submit} className="border-t border-slate-100 bg-white p-5">
          <label htmlFor="cx-message" className="text-sm font-semibold text-slate-900">
            {streaming ? "Redirect the active response" : "Message"}
          </label>
          <div className="mt-2 flex flex-col gap-3 sm:flex-row">
            <input
              id="cx-message"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              maxLength={500}
              placeholder={
                streaming
                  ? "Type the correction; sending will interrupt this response"
                  : "Where is shipment 1042?"
              }
              className="min-w-0 flex-1 rounded-xl border border-slate-300 px-4 py-2.5 text-sm shadow-sm outline-none transition focus:border-violet-400 focus:ring-4 focus:ring-violet-100"
            />
            <button
              type="submit"
              disabled={!draft.trim() || connection !== "connected"}
              className={`rounded-xl px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition disabled:opacity-50 ${
                streaming
                  ? "bg-gradient-to-r from-amber-500 to-orange-600"
                  : "bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700"
              }`}
            >
              {streaming ? "Interrupt and redirect" : "Send"}
            </button>
          </div>
          {error ? <p role="alert" className="mt-3 text-sm text-red-700">{error}</p> : null}
          <p className="mt-2 text-xs text-slate-500">
            The same session reconnects automatically and restores the full conversation.
          </p>
        </form>
      </section>

      <aside className="animate-fade-up space-y-4 [animation-delay:120ms]">
        <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">What it can do</p>
          <ul className="mt-3 space-y-3 text-sm text-slate-700">
            {CAPABILITIES.map(({ title, detail, tone: itemTone }) => (
              <li key={title} className="flex gap-3">
                <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${TONE[itemTone].dot}`} aria-hidden="true" />
                <span>
                  <span className="font-semibold text-slate-900">{title}</span>
                  <span className="block text-xs text-slate-500">{detail}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  );
}
