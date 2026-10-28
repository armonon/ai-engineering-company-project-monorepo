import { API_BASE_URL } from "@/lib/api";
import { getToken } from "@/lib/auth";

export type ControlAction = "pause" | "resume" | "cancel";

export interface ControlUpdate {
  agent_id: string;
  flow_id: string;
  agent_status?: string;
  status?: string;
  actor_id?: string;
  action?: ControlAction;
  checkpoint?: Record<string, unknown> | null;
}

export class AgentControlClient {
  private socket: WebSocket | null = null;
  private closed = false;
  private retryMs = 500;

  constructor(
    private readonly agentId: string,
    private readonly flowId: string,
    private readonly onUpdate: (event: string, data: ControlUpdate & { message?: string }) => void,
  ) {}

  connect(): void {
    this.closed = false;
    const url = `${API_BASE_URL.replace(/^http/, "ws")}/observability/control`;
    this.socket = new WebSocket(url);
    this.socket.onopen = () => {
      const token = getToken();
      this.socket?.send(JSON.stringify({ command: "authenticate", data: { token } }));
      this.retryMs = 500;
    };
    this.socket.onmessage = (message) => {
      const payload = JSON.parse(String(message.data)) as {
        event: string;
        data: ControlUpdate & { message?: string };
      };
      if (payload.event === "authenticated") {
        this.socket?.send(JSON.stringify({
          command: "subscribe",
          data: { agent_id: this.agentId, flow_id: this.flowId },
        }));
        return;
      }
      this.onUpdate(payload.event, payload.data);
    };
    this.socket.onclose = () => {
      if (this.closed) return;
      window.setTimeout(() => this.connect(), this.retryMs);
      this.retryMs = Math.min(this.retryMs * 2, 10_000);
    };
  }

  send(action: ControlAction): void {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      throw new Error("The live control channel is reconnecting. Try again in a moment.");
    }
    this.socket.send(JSON.stringify({
      command: action,
      data: { agent_id: this.agentId, flow_id: this.flowId },
    }));
  }

  close(): void {
    this.closed = true;
    this.socket?.close();
    this.socket = null;
  }
}
