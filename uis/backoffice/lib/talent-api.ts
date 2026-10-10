import {
  NETWORK_MESSAGE,
  UserFacingError,
  toUserMessage,
} from "@/lib/errors";
import type {
  Candidate,
  CandidateInput,
  CandidateListFilters,
  CandidateListResponse,
  CandidateNote,
  CandidateStage,
  CandidateStatus,
} from "@/lib/talent";

const DEFAULT_TALENT_API_URL = "/talent-api";

export function resolveTalentApiUrl(value?: string): string {
  return (value?.trim() || DEFAULT_TALENT_API_URL).replace(/\/+$/, "");
}

export const TALENT_API_URL = resolveTalentApiUrl(
  process.env.NEXT_PUBLIC_TALENT_API_URL,
);

const GENERIC_REQUEST_FAILURE =
  "That request didn't go through. Please try again — if it keeps " +
  "happening, contact support.";

export class TalentApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly body: unknown,
  ) {
    super(message);
    this.name = "TalentApiError";
  }
}

async function talentFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${TALENT_API_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(init.headers ?? {}),
      },
      cache: "no-store",
    });
  } catch (error) {
    throw new UserFacingError(toUserMessage(error, NETWORK_MESSAGE));
  }

  const text = await response.text();
  const body = safeJson(text);

  if (!response.ok) {
    const message =
      body && typeof body === "object" && "detail" in body
        ? formatDetail((body as { detail: unknown }).detail)
        : null;
    throw new TalentApiError(
      response.status,
      message || GENERIC_REQUEST_FAILURE,
      body,
    );
  }

  return body as T;
}

export function buildCandidateQuery(filters: CandidateListFilters): string {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.stage) params.set("stage", filters.stage);
  if (filters.search) params.set("search", filters.search);
  if (filters.page) params.set("page", String(filters.page));
  if (filters.limit) params.set("limit", String(filters.limit));
  const query = params.toString();
  return query ? `?${query}` : "";
}

export const candidatesService = {
  list(filters: CandidateListFilters = {}): Promise<CandidateListResponse> {
    return talentFetch(`/records${buildCandidateQuery(filters)}`);
  },

  get(id: string): Promise<Candidate> {
    return talentFetch(`/records/${encodeURIComponent(id)}`);
  },

  create(data: CandidateInput): Promise<Candidate> {
    return talentFetch("/records", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  replace(id: string, data: CandidateInput): Promise<Candidate> {
    return talentFetch(`/records/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  patch(
    id: string,
    data: { status?: CandidateStatus; stage?: CandidateStage },
  ): Promise<Candidate> {
    return talentFetch(`/records/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  listNotes(id: string): Promise<CandidateNote[]> {
    return talentFetch(`/records/${encodeURIComponent(id)}/notes`);
  },

  addNote(id: string, content: string): Promise<CandidateNote> {
    return talentFetch(`/records/${encodeURIComponent(id)}/notes`, {
      method: "POST",
      body: JSON.stringify({ content }),
    });
  },

  deleteNote(id: string, noteId: string): Promise<void> {
    return talentFetch(
      `/records/${encodeURIComponent(id)}/notes/${encodeURIComponent(noteId)}`,
      { method: "DELETE" },
    );
  },
};

function safeJson(text: string): unknown {
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function formatDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (!Array.isArray(detail)) return null;
  return detail
    .map((item) => {
      if (item && typeof item === "object" && "msg" in item) {
        const location =
          "loc" in item && Array.isArray(item.loc) ? item.loc.join(".") : "";
        return location ? `${location}: ${item.msg}` : String(item.msg);
      }
      return JSON.stringify(item);
    })
    .join("; ");
}
