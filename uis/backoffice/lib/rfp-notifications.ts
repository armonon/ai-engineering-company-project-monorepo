import { authFetch, readApiError } from "@/lib/auth";

export interface RfpTicketCreatedData {
  ticket_id: string;
  rfp_id: string | null;
  client_name: string;
  client_country: string;
  services_requested: string[];
  status: "analyzing";
  created_at: string;
}

export interface RfpTicketCreatedEvent {
  id: number;
  event: "rfp_ticket_created";
  data: RfpTicketCreatedData;
}

export function parseRfpNotificationBlock(block: string): RfpTicketCreatedEvent | null {
  let id = 0;
  let event = "";
  let data = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("id:")) id = Number(line.slice(3).trim());
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!id || event !== "rfp_ticket_created" || !data) return null;
  return {
    id,
    event,
    data: JSON.parse(data) as RfpTicketCreatedData,
  };
}

/**
 * Authenticated SSE with progressive backoff and Last-Event-ID replay.
 * The reconnect callback refreshes the list once as a second recovery layer;
 * individual live events update only their own ticket.
 */
export async function consumeRfpNotificationStream(
  onEvent: (event: RfpTicketCreatedEvent) => void,
  onReconnect: () => void,
  signal: AbortSignal,
): Promise<void> {
  let lastEventId = 0;
  let retryMs = 500;
  let connectedBefore = false;

  while (!signal.aborted) {
    try {
      const headers = new Headers({ Accept: "text/event-stream" });
      if (lastEventId) headers.set("Last-Event-ID", String(lastEventId));
      const response = await authFetch("/rfp/tickets/stream", { headers, signal });
      if (!response.ok || !response.body) throw new Error(await readApiError(response));
      if (connectedBefore) onReconnect();
      connectedBefore = true;
      retryMs = 500;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (!signal.aborted) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          const parsed = parseRfpNotificationBlock(block);
          if (!parsed || parsed.id <= lastEventId) continue;
          lastEventId = parsed.id;
          onEvent(parsed);
        }
      }
    } catch {
      if (signal.aborted) return;
      await new Promise((resolve) => window.setTimeout(resolve, retryMs));
      retryMs = Math.min(retryMs * 2, 10_000);
    }
  }
}
