import { authFetch, authJson, readApiError } from "@/lib/auth";

export interface ObservedTask {
  task_id: string;
  flow_id: string;
  agent_id: string;
  action_type: string;
  status: string;
  trigger: string;
  derived_task_ids: string[];
  previous_task_id: string | null;
  next_task_id: string | null;
  department_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface ObservedAgent {
  agent_id: string;
  name: string;
  agent_type: string;
  owner_area: string;
  flow_types: string[];
  status: string;
  needs_intervention: boolean;
  available_actions: string[];
  updated_at: string;
}

export interface AgentDetail extends ObservedAgent {
  last_5_flows: Array<{
    flow_id: string;
    flow_type: string;
    status: string;
    triggered_by: string;
    tasks: ObservedTask[];
  }>;
  last_10_tasks: ObservedTask[];
}

export interface ObservedFlow {
  flow_id: string;
  flow_type: string;
  status: string;
  triggered_by: string;
  started_at: string;
  completed_at: string | null;
  participating_agents: Array<{
    agent_id: string;
    agent_name: string;
    status: string;
    tasks: ObservedTask[];
  }>;
}

export function fetchObservedAgents(): Promise<ObservedAgent[]> {
  return authJson<ObservedAgent[]>("/observability/agents");
}

export function fetchAgentDetail(agentId: string): Promise<AgentDetail> {
  return authJson<AgentDetail>(`/observability/agents/${encodeURIComponent(agentId)}`);
}

export function fetchObservedFlows(): Promise<ObservedFlow[]> {
  return authJson<ObservedFlow[]>("/observability/flows");
}

export function fetchExecutionLog(
  page: number,
  filters: { agentId?: string; flowId?: string } = {},
): Promise<{ page: number; page_size: number; total: number; items: ObservedTask[] }> {
  const query = new URLSearchParams({ page: String(page), page_size: "20" });
  if (filters.agentId) query.set("agent_id", filters.agentId);
  if (filters.flowId) query.set("flow_id", filters.flowId);
  return authJson(`/observability/executions?${query}`);
}

export interface ObservationEvent {
  id: number;
  event: "agent_step" | "agent_status_changed";
  data: Record<string, unknown>;
}

function parseEventBlock(block: string): ObservationEvent | null {
  let id = 0;
  let event = "";
  let data = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("id:")) id = Number(line.slice(3).trim());
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!id || !data || !["agent_step", "agent_status_changed"].includes(event)) return null;
  return {
    id,
    event: event as ObservationEvent["event"],
    data: JSON.parse(data) as Record<string, unknown>,
  };
}

export async function consumeObservationStream(
  onEvent: (event: ObservationEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  let lastEventId = 0;
  let retryMs = 500;
  while (!signal.aborted) {
    try {
      const headers = new Headers({ Accept: "text/event-stream" });
      if (lastEventId) headers.set("Last-Event-ID", String(lastEventId));
      const response = await authFetch("/observability/stream", { headers, signal });
      if (!response.ok || !response.body) throw new Error(await readApiError(response));
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      retryMs = 500;
      while (!signal.aborted) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          const event = parseEventBlock(block);
          if (event) {
            lastEventId = event.id;
            onEvent(event);
          }
        }
      }
    } catch (error) {
      if (signal.aborted) return;
      await new Promise((resolve) => window.setTimeout(resolve, retryMs));
      retryMs = Math.min(retryMs * 2, 10_000);
      if (error instanceof TypeError) continue;
    }
  }
}
