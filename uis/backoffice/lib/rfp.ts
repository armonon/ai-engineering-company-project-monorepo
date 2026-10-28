import { authFetch, authJson, readApiError } from "@/lib/auth";

export type RfpStatus = "analyzing" | "discarded" | "intake_complete";

export interface RfpMetadata {
  client_name: string;
  client_country: string;
  currency: string;
  services_requested: string[];
  monthly_volume: number | null;
  deadline: string | null;
  budget_range: string | null;
  departments_needed: string[];
  readability_metrics: Record<string, number>;
}

export interface RfpSection {
  department_id: string;
  contact: string;
  key_aspects: string[];
  approval_status: string;
}

export interface RfpTicket {
  ticket_id: string;
  rfp_id: string | null;
  status: RfpStatus;
  created_at: string;
  updated_at: string;
  processing_error: string | null;
  sales_summary: string | null;
  ready_for_generation: boolean;
  metadata: RfpMetadata | null;
  sections: RfpSection[];
}

export async function uploadRfp(document: File): Promise<{
  ticket_id: string;
  status: "analyzing";
}> {
  const body = new FormData();
  body.append("document", document);
  const response = await authFetch("/rfp/tickets", { method: "POST", body });
  if (!response.ok) throw new Error(await readApiError(response));
  return response.json();
}

export function fetchRfpTickets(): Promise<RfpTicket[]> {
  return authJson<RfpTicket[]>("/rfp/tickets");
}

export function fetchRfpTicket(ticketId: string): Promise<RfpTicket> {
  return authJson<RfpTicket>(`/rfp/tickets/${encodeURIComponent(ticketId)}`);
}
