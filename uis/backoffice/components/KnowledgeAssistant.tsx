"use client";

import { FormEvent, useState } from "react";
import { askTrackFlow } from "@/lib/knowledge";

export function KnowledgeAssistant() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanQuestion = question.trim();
    if (cleanQuestion.length < 3) {
      setError("Enter a complete question about TrackFlow policy.");
      return;
    }
    setLoading(true);
    setError("");
    setAnswer("");
    try {
      const result = await askTrackFlow(cleanQuestion);
      setAnswer(result.answer);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The knowledge service is unavailable.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="max-w-3xl rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label htmlFor="knowledge-question" className="block text-sm font-semibold text-slate-900 dark:text-slate-100">
            Ask a policy question
          </label>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
            Get grounded guidance about delivery, returns, carrier coverage, or storage pricing.
          </p>
        </div>
        <textarea
          id="knowledge-question"
          rows={4}
          maxLength={500}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Can we promise express delivery during Black Friday?"
          className="w-full rounded-lg border border-slate-300 bg-white p-3 text-slate-900 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-200 dark:border-slate-600 dark:bg-slate-950 dark:text-slate-100"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-wait disabled:opacity-60"
        >
          {loading ? "Checking TrackFlow policies…" : "Ask TrackFlow"}
        </button>
      </form>

      {error && <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">{error}</p>}
      {answer && (
        <div aria-live="polite" className="mt-5 rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-900 dark:bg-blue-950">
          <h2 className="text-sm font-semibold text-blue-950 dark:text-blue-100">Verified answer</h2>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-800 dark:text-slate-200">{answer}</p>
        </div>
      )}
    </section>
  );
}
