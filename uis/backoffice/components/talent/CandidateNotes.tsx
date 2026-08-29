"use client";

import { useEffect, useState, type FormEvent } from "react";
import { toUserMessage } from "@/lib/errors";
import type { CandidateNote } from "@/lib/talent";
import { candidatesService } from "@/lib/talent-api";

interface CandidateNotesProps {
  candidateId: string;
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
}

export function CandidateNotes({
  candidateId,
  onError,
  onSuccess,
}: CandidateNotesProps) {
  const [notes, setNotes] = useState<CandidateNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [adding, setAdding] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (!cancelled) {
        setLoading(true);
        setLoadError(null);
      }
    });
    candidatesService
      .listNotes(candidateId)
      .then((response) => {
        if (!cancelled) setNotes(response);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setLoadError(toUserMessage(error, "Failed to load notes"));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [candidateId]);

  async function handleAdd(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = draft.trim();
    if (!content) return;
    setAdding(true);
    try {
      const created = await candidatesService.addNote(candidateId, content);
      setNotes((current) => [created, ...current]);
      setDraft("");
      onSuccess("Note added");
    } catch (error) {
      onError(toUserMessage(error, "Failed to add note"));
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(noteId: string) {
    setDeletingId(noteId);
    try {
      await candidatesService.deleteNote(candidateId, noteId);
      setNotes((current) => current.filter((note) => note.id !== noteId));
      onSuccess("Note deleted");
    } catch (error) {
      onError(toUserMessage(error, "Failed to delete note"));
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={handleAdd} className="space-y-2">
        <label
          htmlFor="candidate-note"
          className="block text-sm font-medium text-slate-700"
        >
          Add an internal note
        </label>
        <textarea
          id="candidate-note"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          rows={3}
          placeholder="Anything the team should know — visible only to TrackFlow recruiters."
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
        />
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={adding || !draft.trim()}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60"
          >
            {adding ? "Saving…" : "Add note"}
          </button>
        </div>
      </form>

      {loading && <NoteState>Loading notes…</NoteState>}
      {loadError && (
        <div
          role="alert"
          className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700"
        >
          {loadError}
        </div>
      )}
      {!loading && !loadError && notes.length === 0 && (
        <NoteState>No notes yet.</NoteState>
      )}
      {!loading && !loadError && notes.length > 0 && (
        <ul className="space-y-2">
          {notes.map((note) => (
            <li
              key={note.id}
              className="flex items-start justify-between gap-3 rounded-md border border-slate-200 bg-white p-3 text-sm shadow-sm"
            >
              <div>
                <p className="whitespace-pre-wrap text-slate-800">
                  {note.content}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {formatDateTime(note.created_at)}
                </p>
              </div>
              <button
                type="button"
                onClick={() => void handleDelete(note.id)}
                disabled={deletingId === note.id}
                className="text-xs font-medium text-red-600 hover:underline disabled:opacity-60"
              >
                {deletingId === note.id ? "Deleting…" : "Delete"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function NoteState({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-4 text-sm text-slate-500">
      {children}
    </div>
  );
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : date.toLocaleString();
}
