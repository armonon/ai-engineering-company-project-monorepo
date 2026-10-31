import {
  humanize,
  initials,
  isLiveStatus,
  progressFraction,
  RFP_STAGES,
  rfpProgress,
  statusTone,
  type Tone,
} from "@/lib/presentation";

/** Static class strings so Tailwind keeps every tone in the build. */
export const TONE: Record<Tone, { pill: string; dot: string; ring: string; soft: string; text: string }> = {
  slate: { pill: "bg-slate-100 text-slate-700 ring-slate-200", dot: "bg-slate-400", ring: "ring-slate-300", soft: "bg-slate-50", text: "text-slate-700" },
  amber: { pill: "bg-amber-50 text-amber-800 ring-amber-200", dot: "bg-amber-500", ring: "ring-amber-300", soft: "bg-amber-50", text: "text-amber-700" },
  blue: { pill: "bg-blue-50 text-blue-800 ring-blue-200", dot: "bg-blue-500", ring: "ring-blue-300", soft: "bg-blue-50", text: "text-blue-700" },
  violet: { pill: "bg-violet-50 text-violet-800 ring-violet-200", dot: "bg-violet-500", ring: "ring-violet-300", soft: "bg-violet-50", text: "text-violet-700" },
  cyan: { pill: "bg-cyan-50 text-cyan-800 ring-cyan-200", dot: "bg-cyan-500", ring: "ring-cyan-300", soft: "bg-cyan-50", text: "text-cyan-700" },
  emerald: { pill: "bg-emerald-50 text-emerald-800 ring-emerald-200", dot: "bg-emerald-500", ring: "ring-emerald-300", soft: "bg-emerald-50", text: "text-emerald-700" },
  orange: { pill: "bg-orange-50 text-orange-800 ring-orange-200", dot: "bg-orange-500", ring: "ring-orange-300", soft: "bg-orange-50", text: "text-orange-700" },
  red: { pill: "bg-red-50 text-red-800 ring-red-200", dot: "bg-red-500", ring: "ring-red-300", soft: "bg-red-50", text: "text-red-700" },
};

export function LiveDot({ tone = "blue", live = true }: { tone?: Tone; live?: boolean }) {
  return (
    <span className="relative inline-flex h-2 w-2" aria-hidden="true">
      {live ? <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 ${TONE[tone].dot}`} /> : null}
      <span className={`relative inline-flex h-2 w-2 rounded-full ${TONE[tone].dot}`} />
    </span>
  );
}

export function StatusPill({ status, label }: { status: string; label?: string }) {
  const tone = statusTone(status);
  return (
    <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset ${TONE[tone].pill}`}>
      <LiveDot tone={tone} live={isLiveStatus(status)} />
      {label ?? humanize(status)}
    </span>
  );
}

const AVATAR_GRADIENTS = [
  "from-blue-500 to-indigo-600",
  "from-violet-500 to-fuchsia-600",
  "from-emerald-500 to-teal-600",
  "from-amber-500 to-orange-600",
  "from-cyan-500 to-sky-600",
];

export function Avatar({ name, size = "md" }: { name: string; size?: "sm" | "md" | "lg" }) {
  const index = [...name].reduce((sum, char) => sum + char.charCodeAt(0), 0) % AVATAR_GRADIENTS.length;
  const dimensions = size === "lg" ? "h-12 w-12 text-base" : size === "sm" ? "h-7 w-7 text-[10px]" : "h-9 w-9 text-xs";
  return (
    <span
      aria-hidden="true"
      className={`inline-grid shrink-0 place-items-center rounded-full bg-gradient-to-br font-bold text-white shadow-sm ring-2 ring-white ${dimensions} ${AVATAR_GRADIENTS[index]}`}
    >
      {initials(name)}
    </span>
  );
}

export function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function StatTile({ label, value, hint, tone = "blue", delay = 0 }: { label: string; value: React.ReactNode; hint?: string; tone?: Tone; delay?: number }) {
  return (
    <div
      className="animate-fade-up rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm"
      style={{ animationDelay: `${delay}ms` }}
    >
      <p className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-slate-500">
        <span className={`h-1.5 w-1.5 rounded-full ${TONE[tone].dot}`} aria-hidden="true" />
        {label}
      </p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">{value}</p>
      {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

/** Animated five-stage tracker for an RFP ticket. */
export function RfpProgress({ status }: { status: string }) {
  const progress = rfpProgress(status);
  const fraction = progressFraction(progress);
  return (
    <div className="mt-5" aria-label={`Progress: ${progress.discarded ? "discarded" : RFP_STAGES[Math.min(progress.current, RFP_STAGES.length - 1)]}`}>
      <div className="relative">
        <div className="absolute left-4 right-4 top-4 h-1 rounded-full bg-slate-100" aria-hidden="true" />
        <div
          className="absolute left-4 top-4 h-1 rounded-full bg-gradient-to-r from-blue-500 via-violet-500 to-emerald-500 transition-[width] duration-700 ease-out"
          style={{ width: `calc((100% - 2rem) * ${fraction})` }}
          aria-hidden="true"
        />
        <ol className="relative flex justify-between">
          {RFP_STAGES.map((stage, index) => {
            const complete = index < progress.current;
            const active = index === progress.current && !progress.discarded;
            return (
              <li key={stage} className="flex w-14 flex-col items-center gap-2 text-center sm:w-16">
                <span
                  className={`grid h-9 w-9 place-items-center rounded-full border-2 text-xs font-bold transition-all duration-500 ${
                    complete
                      ? "border-transparent bg-gradient-to-br from-blue-500 to-violet-600 text-white shadow-md shadow-violet-500/20"
                      : active
                        ? "animate-glow border-blue-500 bg-white text-blue-700"
                        : "border-slate-200 bg-white text-slate-400"
                  }`}
                >
                  {complete ? (
                    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor" aria-hidden="true">
                      <path fillRule="evenodd" d="M16.7 5.3a1 1 0 0 1 0 1.4l-7.5 7.5a1 1 0 0 1-1.4 0L3.3 9.7a1 1 0 1 1 1.4-1.4l3.8 3.8 6.8-6.8a1 1 0 0 1 1.4 0Z" clipRule="evenodd" />
                    </svg>
                  ) : active && progress.working ? (
                    <Spinner className="h-4 w-4" />
                  ) : (
                    index + 1
                  )}
                </span>
                <span className={`text-[9px] font-semibold uppercase tracking-normal sm:text-[11px] sm:tracking-wide ${complete || active ? "text-slate-800" : "text-slate-400"}`}>
                  {stage}
                </span>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}

export function PageHero({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: string; children?: React.ReactNode }) {
  return (
    <header className="relative overflow-hidden rounded-3xl border border-slate-200/70 bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-900 px-6 py-8 text-white shadow-lg sm:px-8">
      <div className="pointer-events-none absolute -right-16 -top-24 h-72 w-72 rounded-full bg-blue-500/30 blur-3xl" aria-hidden="true" />
      <div className="pointer-events-none absolute -bottom-24 left-1/3 h-64 w-64 rounded-full bg-violet-500/25 blur-3xl" aria-hidden="true" />
      <div className="relative flex flex-wrap items-end justify-between gap-6">
        <div className="max-w-3xl animate-fade-up">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-blue-200">{eyebrow}</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
          <p className="mt-3 text-sm leading-6 text-slate-300 sm:text-base">{description}</p>
        </div>
        {children ? <div className="relative animate-fade-up [animation-delay:120ms]">{children}</div> : null}
      </div>
    </header>
  );
}
