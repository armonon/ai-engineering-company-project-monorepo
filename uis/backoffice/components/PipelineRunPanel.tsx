"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { toUserMessage } from "@/lib/errors";
import {
  canTriggerPipelineRun,
  fetchTaskStatus,
  isFinishedTask,
  triggerPipelineRun,
  type TaskStatus,
} from "@/lib/reporting";

const POLL_INTERVAL_MS = 2000;

/**
 * Queues the weekly business pipeline on the Celery worker and follows the
 * task through `/tasks/{task_id}`, so the async offloading is reachable from
 * the backoffice instead of only from the API docs.
 */
export function PipelineRunPanel({ onFinished }: { onFinished: () => void }) {
  const { user } = useAuth();
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<TaskStatus | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const onFinishedRef = useRef(onFinished);
  useEffect(() => {
    onFinishedRef.current = onFinished;
  }, [onFinished]);

  useEffect(() => {
    if (!taskId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      try {
        const task = await fetchTaskStatus(taskId);
        if (cancelled) return;
        setStatus(task.status);
        if (isFinishedTask(task.status)) {
          setMessage(task.error);
          setTaskId(null);
          if (task.status === "success") onFinishedRef.current();
          return;
        }
      } catch (caught) {
        if (cancelled) return;
        setMessage(toUserMessage(caught, "We couldn't read the task status."));
      }
      timer = setTimeout(() => void poll(), POLL_INTERVAL_MS);
    };

    void poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [taskId]);

  if (!canTriggerPipelineRun(user?.role)) return null;

  const start = async () => {
    setSubmitting(true);
    setMessage(null);
    try {
      const accepted = await triggerPipelineRun();
      if (accepted.task_id) {
        setStatus("pending");
        setTaskId(accepted.task_id);
      } else {
        setStatus("started");
        setMessage("A run for this week is already in progress.");
      }
    } catch (caught) {
      setMessage(toUserMessage(caught, "We couldn't queue the pipeline run."));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section
      aria-label="Weekly pipeline run"
      className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white p-4 text-sm"
    >
      <button
        type="button"
        onClick={() => void start()}
        disabled={submitting || taskId !== null}
        className="rounded-md bg-slate-900 px-3 py-2 font-medium text-white hover:bg-slate-700 disabled:opacity-50"
      >
        Run weekly pipeline now
      </button>
      {status && (
        <span role="status" className="text-slate-700">
          Background task: <strong>{status}</strong>
        </span>
      )}
      {message && <span className="text-slate-600">{message}</span>}
    </section>
  );
}
