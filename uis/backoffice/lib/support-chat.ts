import { getToken } from "@/lib/auth";
import { websocketUrl } from "@/lib/websocket";

export type ChatMessageStatus = "completed" | "streaming" | "interrupted";

export interface ChatMessage {
  message_id: string;
  role: "user" | "assistant";
  text: string;
  status: ChatMessageStatus;
  created_at: string;
}

export interface ChatEvent {
  event:
    | "session_snapshot"
    | "user_message"
    | "token_chunk"
    | "generation_interrupted"
    | "generation_completed"
    | "chat_error";
  data: Record<string, unknown>;
}

export type ChatConnectionState = "connecting" | "connected" | "reconnecting" | "closed";

export function applyChatEvent(current: ChatMessage[], payload: ChatEvent): ChatMessage[] {
  const data = payload.data;
  if (payload.event === "session_snapshot") {
    return (data.messages as ChatMessage[] | undefined) ?? [];
  }
  const messageId = String(data.message_id ?? "");
  if (payload.event === "user_message") {
    if (current.some((message) => message.message_id === messageId)) return current;
    return [
      ...current,
      {
        message_id: messageId,
        role: "user",
        text: String(data.text ?? ""),
        status: "completed",
        created_at: new Date().toISOString(),
      },
    ];
  }
  if (payload.event === "token_chunk") {
    const token = String(data.token ?? "");
    const existing = current.find((message) => message.message_id === messageId);
    if (!existing) {
      return [
        ...current,
        {
          message_id: messageId,
          role: "assistant",
          text: token,
          status: "streaming",
          created_at: new Date().toISOString(),
        },
      ];
    }
    return current.map((message) =>
      message.message_id === messageId
        ? { ...message, text: `${message.text}${token}`, status: "streaming" }
        : message,
    );
  }
  if (payload.event === "generation_interrupted" || payload.event === "generation_completed") {
    const status: ChatMessageStatus =
      payload.event === "generation_interrupted" ? "interrupted" : "completed";
    return current.map((message) =>
      message.message_id === messageId ? { ...message, status } : message,
    );
  }
  return current;
}

export class SupportChatClient {
  private socket: WebSocket | null = null;
  private closed = false;
  private retryMs = 500;

  constructor(
    readonly sessionId: string,
    private readonly onEvent: (event: ChatEvent) => void,
    private readonly onConnection: (state: ChatConnectionState) => void,
  ) {}

  connect(): void {
    this.closed = false;
    this.onConnection(this.retryMs === 500 ? "connecting" : "reconnecting");
    const token = getToken();
    const url = websocketUrl(
      `/agent/chat/${encodeURIComponent(this.sessionId)}?token=${encodeURIComponent(token ?? "")}`,
    );
    this.socket = new WebSocket(url);
    this.socket.onopen = () => {
      this.retryMs = 500;
      this.onConnection("connected");
    };
    this.socket.onmessage = (message) => {
      this.onEvent(JSON.parse(String(message.data)) as ChatEvent);
    };
    this.socket.onclose = () => {
      if (this.closed) {
        this.onConnection("closed");
        return;
      }
      this.onConnection("reconnecting");
      const wait = this.retryMs;
      this.retryMs = Math.min(this.retryMs * 2, 10_000);
      window.setTimeout(() => this.connect(), wait);
    };
  }

  send(text: string, interrupt = false): void {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      throw new Error("The live chat is reconnecting. Your message was not sent.");
    }
    this.socket.send(JSON.stringify({
      event: interrupt ? "interrupt_requested" : "user_message",
      data: interrupt
        ? { session_id: this.sessionId, new_input: text }
        : { session_id: this.sessionId, text },
    }));
  }

  close(): void {
    this.closed = true;
    this.socket?.close();
    this.socket = null;
  }
}
