import { setToken } from "@/lib/auth";
import {
  applyChatEvent,
  ChatConnectionState,
  ChatEvent,
  ChatMessage,
  SupportChatClient,
} from "@/lib/support-chat";

class FakeWebSocket {
  static OPEN = 1;
  readyState = FakeWebSocket.OPEN;
  onopen: (() => void) | null = null;
  onmessage: ((message: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  sent: string[] = [];

  constructor(readonly url: string) {
    sockets.push(this);
  }

  send(value: string) {
    this.sent.push(value);
  }

  close() {
    this.onclose?.();
  }
}

const sockets: FakeWebSocket[] = [];

describe("First-line CX WebSocket client", () => {
  beforeEach(() => {
    sockets.length = 0;
    jest.useFakeTimers();
    Object.defineProperty(global, "WebSocket", {
      configurable: true,
      value: FakeWebSocket,
    });
    setToken("signed.jwt.token");
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("sends structured user and interrupt events and reconnects the same session", () => {
    const states: ChatConnectionState[] = [];
    const events: ChatEvent[] = [];
    const client = new SupportChatClient("chat_0219", (event) => events.push(event), (state) => states.push(state));

    client.connect();
    expect(sockets[0].url).toContain("/agent/chat/chat_0219?token=signed.jwt.token");
    sockets[0].onopen?.();
    client.send("Track my parcel");
    client.send("Wait, I need a return", true);

    expect(JSON.parse(sockets[0].sent[0])).toEqual({
      event: "user_message",
      data: { session_id: "chat_0219", text: "Track my parcel" },
    });
    expect(JSON.parse(sockets[0].sent[1])).toEqual({
      event: "interrupt_requested",
      data: { session_id: "chat_0219", new_input: "Wait, I need a return" },
    });

    sockets[0].onclose?.();
    jest.advanceTimersByTime(500);
    expect(sockets).toHaveLength(2);
    expect(sockets[1].url).toContain("/agent/chat/chat_0219");
    expect(states).toContain("reconnecting");
    client.close();
    expect(events).toEqual([]);
  });

  it("keeps an interrupted partial message and appends the redirected turn", () => {
    const base: ChatMessage[] = [];
    const withUser = applyChatEvent(base, {
      event: "user_message",
      data: { message_id: "user-1", text: "Track my parcel" },
    });
    const withPartial = applyChatEvent(withUser, {
      event: "token_chunk",
      data: { message_id: "assistant-1", token: "Your ", sequence: 1 },
    });
    const interrupted = applyChatEvent(withPartial, {
      event: "generation_interrupted",
      data: { message_id: "assistant-1", status: "interrupted" },
    });
    const redirected = applyChatEvent(interrupted, {
      event: "user_message",
      data: { message_id: "user-2", text: "Wait, I need a return" },
    });

    expect(redirected).toHaveLength(3);
    expect(redirected[1]).toMatchObject({
      message_id: "assistant-1",
      text: "Your ",
      status: "interrupted",
    });
    expect(redirected[2]).toMatchObject({
      message_id: "user-2",
      text: "Wait, I need a return",
    });
  });
});
