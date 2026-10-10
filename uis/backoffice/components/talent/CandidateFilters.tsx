"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useDebounced } from "@/hooks/useDebounced";
import {
  STAGE_LABELS,
  STAGE_OPTIONS,
  STATUS_LABELS,
  STATUS_OPTIONS,
} from "@/lib/talent";

export function CandidateFilters() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const currentStatus = searchParams.get("status") ?? "";
  const currentStage = searchParams.get("stage") ?? "";
  const currentSearch = searchParams.get("search") ?? "";
  const [searchInput, setSearchInput] = useState(currentSearch);
  const debouncedSearch = useDebounced(searchInput, 300);

  function updateParam(key: string, value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value) params.set(key, value);
    else params.delete(key);
    const query = params.toString();
    router.replace(query ? `/talent?${query}` : "/talent");
  }

  useEffect(() => {
    if (debouncedSearch !== currentSearch) {
      updateParam("search", debouncedSearch);
    }
    // updateParam intentionally follows the current URL snapshot.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch, currentSearch]);

  useEffect(() => {
    queueMicrotask(() => setSearchInput(currentSearch));
  }, [currentSearch]);

  return (
    <div className="flex flex-col gap-3 md:flex-row md:items-end">
      <label className="flex-1">
        <span className="mb-1 block text-xs font-medium text-slate-600">
          Search by name or email
        </span>
        <input
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
          placeholder="e.g. Michael or michael@example.com"
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
        />
      </label>

      <label className="md:w-56">
        <span className="mb-1 block text-xs font-medium text-slate-600">
          Status
        </span>
        <select
          value={currentStatus}
          onChange={(event) => updateParam("status", event.target.value)}
          className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
        >
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((status) => (
            <option key={status} value={status}>
              {STATUS_LABELS[status]}
            </option>
          ))}
        </select>
      </label>

      <label className="md:w-56">
        <span className="mb-1 block text-xs font-medium text-slate-600">
          Pipeline stage
        </span>
        <select
          value={currentStage}
          onChange={(event) => updateParam("stage", event.target.value)}
          className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
        >
          <option value="">All stages</option>
          {STAGE_OPTIONS.map((stage) => (
            <option key={stage} value={stage}>
              {STAGE_LABELS[stage]}
            </option>
          ))}
        </select>
      </label>

      {(currentStatus || currentStage || currentSearch) && (
        <button
          type="button"
          onClick={() => router.replace("/talent")}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
        >
          Clear
        </button>
      )}
    </div>
  );
}
