import { SupportChat } from "@/components/SupportChat";

export default function SupportPage() {
  return (
    <div className="space-y-5">
      <header>
        <p className="text-xs font-semibold uppercase tracking-wider text-blue-700">
          Live customer support
        </p>
        <h1 className="mt-1 text-2xl font-bold text-slate-950">Streaming support chat</h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-600">
          Responses arrive token by token. Send a correction while the agent is responding to
          abort that turn, preserve the partial answer, and redirect the next turn.
        </p>
      </header>
      <SupportChat />
    </div>
  );
}
