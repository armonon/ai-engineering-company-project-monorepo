"use client";

import { useEffect, useRef, useState } from "react";
import {
  applyChatEvent,
  ChatConnectionState,
  ChatMessage,
  SupportChatClient,
} from "@/lib/support-chat";

const SESSION_KEY = "trackflow.first_line_cx.session_id";

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

  return (
    <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 p-5">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-violet-700">
            Valentina Cruz · Customer Experience
          </p>
          <h2 className="mt-1 text-xl font-semibold text-slate-950">First-line CX agent</h2>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
          connection === "connected"
            ? "bg-emerald-100 text-emerald-800"
            : "bg-amber-100 text-amber-800"
        }`}>
          {connection}
        </span>
      </header>

      <div className="min-h-96 space-y-4 p-5" aria-live="polite">
        {messages.length === 0 ? (
          <p className="rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
            Ask about TrackFlow shipment tracking, returns, or frequent delivery questions.
          </p>
        ) : null}
        {messages.map((message) => (
          <article
            key={message.message_id}
            className={`max-w-3xl rounded-xl px-4 py-3 text-sm ${
              message.role === "user"
                ? "ml-auto bg-blue-700 text-white"
                : "bg-slate-100 text-slate-900"
            }`}
          >
            <p className="whitespace-pre-wrap">{message.text || "…"}</p>
            {message.role === "assistant" && message.status === "streaming" ? (
              <span className="mt-2 inline-block animate-pulse text-xs text-slate-500">
                responding live…
              </span>
            ) : null}
            {message.status === "interrupted" ? (
              <span className="mt-2 inline-block rounded bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-800">
                Interrupted
              </span>
            ) : null}
          </article>
        ))}
      </div>

      <form onSubmit={submit} className="border-t border-slate-200 p-5">
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
            className="min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={!draft.trim() || connection !== "connected"}
            className={`rounded-md px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 ${
              streaming ? "bg-amber-700" : "bg-blue-700"
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
  );
}
