import { AgentControlClient } from "@/lib/agent-control";

jest.mock("@/lib/api", () => ({ API_BASE_URL: "http://localhost:8000" }));
jest.mock("@/lib/auth", () => ({ getToken: () => "test-jwt" }));

class FakeWebSocket {
  static OPEN = 1;
  readyState = FakeWebSocket.OPEN;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((message: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  close = jest.fn();

  constructor(public url: string) {
    sockets.push(this);
  }

  send(value: string) {
    this.sent.push(value);
  }
}

const sockets: FakeWebSocket[] = [];

describe("agent control WebSocket client", () => {
  beforeEach(() => {
    sockets.length = 0;
    Object.defineProperty(global, "WebSocket", {
      value: FakeWebSocket,
      configurable: true,
    });
  });

  it("authenticates, subscribes, and sends a targeted control command", () => {
    const updates = jest.fn();
    const client = new AgentControlClient("rfp_pipeline", "rfp-123", updates);
    client.connect();
    const socket = sockets[0];
    expect(socket.url).toBe("ws://localhost:8000/observability/control");

    socket.onopen?.();
    expect(JSON.parse(socket.sent[0])).toEqual({
      command: "authenticate",
      data: { token: "test-jwt" },
    });

    socket.onmessage?.({
      data: JSON.stringify({ event: "authenticated", data: { actor_id: "user_1" } }),
    });
    expect(JSON.parse(socket.sent[1])).toEqual({
      command: "subscribe",
      data: { agent_id: "rfp_pipeline", flow_id: "rfp-123" },
    });

    client.send("pause");
    expect(JSON.parse(socket.sent[2])).toEqual({
      command: "pause",
      data: { agent_id: "rfp_pipeline", flow_id: "rfp-123" },
    });
  });
});
