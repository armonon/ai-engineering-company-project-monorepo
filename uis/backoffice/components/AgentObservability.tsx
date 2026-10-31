"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AgentControlClient, ControlAction } from "@/lib/agent-control";
import {
  AgentDetail,
  consumeObservationStream,
  fetchAgentDetail,
  fetchExecutionLog,
  fetchObservedAgents,
  fetchObservedFlows,
  ObservedAgent,
  ObservedFlow,
  ObservedTask,
} from "@/lib/observability";
import { Avatar, LiveDot, StatTile, StatusPill, TONE } from "@/components/ui/Showcase";
import {
  actionLabel,
  actionTone,
  departmentName,
  describeTrigger,
  humanize,
  isLiveStatus,
  relativeTime,
  shortId,
  statusTone,
} from "@/lib/presentation";

/** One step of an agent's work, as a node on a vertical timeline. */
function TaskTrace({ task, index = 0, last = false }: { task: ObservedTask; index?: number; last?: boolean }) {
  const tone = actionTone(task.action_type);
  return (
    <li className="animate-fade-up relative flex gap-3 pb-4" style={{ animationDelay: `${Math.min(index, 10) * 50}ms` }}>
      {!last ? <span className="absolute left-[15px] top-8 h-[calc(100%-1.5rem)] w-px bg-gradient-to-b from-slate-200 to-transparent" aria-hidden="true" /> : null}
      <span className={`relative z-10 mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full ring-4 ring-white ${TONE[tone].soft}`}>
        <span className={`h-2.5 w-2.5 rounded-full ${TONE[tone].dot}`} aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1 rounded-xl border border-slate-200/80 bg-white p-3 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-semibold text-slate-900">
            {actionLabel(task.action_type)}
            {task.department_id ? <span className="font-normal text-slate-500"> · {departmentName(task.department_id)}</span> : null}
          </p>
          <span className="flex items-center gap-2 text-xs text-slate-500">
            {task.status ? <span className={`font-semibold ${TONE[statusTone(task.status)].text}`}>{humanize(task.status)}</span> : null}
            <span>{relativeTime(task.created_at)}</span>
          </span>
        </div>
        <details className="mt-1 text-xs text-slate-500">
          <summary className="cursor-pointer select-none hover:text-slate-700">Trace details · #{shortId(task.task_id)}</summary>
          <dl className="mt-2 grid gap-1 rounded-lg bg-slate-50 p-2 font-mono text-[11px] text-slate-600 sm:grid-cols-2">
            <div><dt className="inline font-sans font-semibold">Task: </dt><dd className="inline break-all">{task.task_id}</dd></div>
            <div><dt className="inline font-sans font-semibold">Trigger: </dt><dd className="inline break-all">{task.trigger}</dd></div>
            <div><dt className="inline font-sans font-semibold">Previous: </dt><dd className="inline break-all">{task.previous_task_id ?? "external"}</dd></div>
            <div><dt className="inline font-sans font-semibold">Next: </dt><dd className="inline break-all">{task.next_task_id ?? "end"}</dd></div>
            <div className="sm:col-span-2"><dt className="inline font-sans font-semibold">Derived: </dt><dd className="inline break-all">{task.derived_task_ids.join(", ") || "none"}</dd></div>
          </dl>
        </details>
      </div>
    </li>
  );
}

function Timeline({ tasks }: { tasks: ObservedTask[] }) {
  return (
    <ol className="mt-3">
      {tasks.map((task, index) => (
        <TaskTrace key={task.task_id} task={task} index={index} last={index === tasks.length - 1} />
      ))}
    </ol>
  );
}

function FlowSummary({ flowId, flowType, status, triggeredBy }: { flowId: string; flowType?: string; status: string; triggeredBy: string }) {
  return (
    <summary className="flex cursor-pointer flex-wrap items-center justify-between gap-3">
      <span className="min-w-0">
        <span className="block text-sm font-semibold text-slate-900">
          {flowType ? humanize(flowType) : "Flow"} <span className="font-mono text-xs font-normal text-slate-400">#{shortId(flowId)}</span>
        </span>
        <span className="block text-xs text-slate-500">Triggered by {describeTrigger(triggeredBy)}</span>
      </span>
      <StatusPill status={status} />
    </summary>
  );
}

export function AgentObservability() {
  const [agents, setAgents] = useState<ObservedAgent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState("first_line_cx");
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [flows, setFlows] = useState<ObservedFlow[]>([]);
  const [log, setLog] = useState<{ total: number; items: ObservedTask[] }>({ total: 0, items: [] });
  const [page, setPage] = useState(1);
  const [agentFilter, setAgentFilter] = useState("");
  const [flowFilter, setFlowFilter] = useState("");
  const [error, setError] = useState("");
  const [controlStatus, setControlStatus] = useState("");
  const [controlError, setControlError] = useState("");
  const controlClient = useRef<AgentControlClient | null>(null);

  const loadAgents = useCallback(async () => {
    const values = await fetchObservedAgents();
    setAgents(values);
    if (!values.some((agent) => agent.agent_id === selectedAgent) && values[0]) {
      setSelectedAgent(values[0].agent_id);
    }
  }, [selectedAgent]);

  const load = useCallback(async () => {
    try {
      const [agentValues, flowValues, logValues] = await Promise.all([
        fetchObservedAgents(),
        fetchObservedFlows(),
        fetchExecutionLog(page, {
          agentId: agentFilter || undefined,
          flowId: flowFilter || undefined,
        }),
      ]);
      setAgents(agentValues);
      setFlows(flowValues);
      setLog(logValues);
      if (selectedAgent) setDetail(await fetchAgentDetail(selectedAgent));
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load observability data.");
    }
  }, [agentFilter, flowFilter, page, selectedAgent]);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  useEffect(() => {
    const controller = new AbortController();
    void consumeObservationStream(() => {
      void loadAgents();
      if (selectedAgent) void fetchAgentDetail(selectedAgent).then(setDetail);
    }, controller.signal);
    return () => controller.abort();
  }, [loadAgents, selectedAgent]);

  const activeFlowId = detail?.last_5_flows[0]?.flow_id ?? "";

  useEffect(() => {
    controlClient.current?.close();
    controlClient.current = null;
    if (!selectedAgent || !activeFlowId) return;
    const client = new AgentControlClient(selectedAgent, activeFlowId, (event, data) => {
      if (event === "control_state") {
        setControlStatus(data.agent_status ?? "");
        setControlError("");
      } else if (event === "control_applied") {
        setControlStatus(data.status ?? "");
        setControlError("");
        void loadAgents();
        void fetchAgentDetail(selectedAgent).then(setDetail);
      } else if (event === "control_error") {
        setControlError(data.message ?? "The control action was rejected.");
      }
    });
    controlClient.current = client;
    client.connect();
    return () => client.close();
  }, [activeFlowId, loadAgents, selectedAgent]);

  function control(action: ControlAction) {
    try {
      setControlError("");
      controlClient.current?.send(action);
    } catch (reason) {
      setControlError(reason instanceof Error ? reason.message : "The control action failed.");
    }
  }

  const liveAgents = agents.filter((agent) => isLiveStatus(agent.status)).length;
  const interventions = agents.filter((agent) => agent.needs_intervention).length;
  const operationalStatus = controlStatus || detail?.status || "";
  const controls: Array<{ action: ControlAction; label: string; enabled: boolean; style: string; icon: string }> = [
    { action: "pause", label: "Pause", enabled: ["running", "waiting_for_human"].includes(controlStatus), style: "text-amber-800 hover:bg-amber-50", icon: "❚❚" },
    { action: "resume", label: "Resume", enabled: controlStatus === "paused", style: "text-emerald-700 hover:bg-emerald-50", icon: "▶" },
    { action: "cancel", label: "Cancel", enabled: ["running", "paused", "waiting_for_human"].includes(controlStatus), style: "text-red-700 hover:bg-red-50", icon: "■" },
  ];

  return (
    <div className="space-y-8">
      {error ? <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p> : null}

      <section aria-label="Observability summary" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile label="Agents registered" value={agents.length} hint={`${liveAgents} working right now`} tone="blue" />
        <StatTile label="Flows recorded" value={flows.length} hint="Persisted end-to-end runs" tone="violet" delay={60} />
        <StatTile label="Steps traced" value={log.total} hint="Every task, chained in order" tone="cyan" delay={120} />
        <StatTile
          label="Needs intervention"
          value={interventions}
          hint={interventions ? "A human should look now" : "All agents healthy"}
          tone={interventions ? "red" : "emerald"}
          delay={180}
        />
      </section>

      <section>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-blue-700">Live registry</p>
            <h2 className="mt-1 text-xl font-semibold text-slate-950">TrackFlow agents</h2>
          </div>
          <p className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm ring-1 ring-slate-200">
            <LiveDot tone="emerald" /> Streaming over authenticated SSE
          </p>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {agents.map((agent, index) => {
            const selected = selectedAgent === agent.agent_id;
            return (
              <button
                key={agent.agent_id}
                type="button"
                onClick={() => setSelectedAgent(agent.agent_id)}
                aria-pressed={selected}
                className={`animate-fade-up group rounded-2xl border p-4 text-left transition-all hover:-translate-y-0.5 hover:shadow-md ${
                  selected ? "border-blue-400 bg-gradient-to-br from-blue-50 to-violet-50 shadow-md ring-2 ring-blue-200" : "border-slate-200 bg-white shadow-sm"
                }`}
                style={{ animationDelay: `${index * 80}ms` }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <Avatar name={agent.name} />
                    <div>
                      <p className="font-semibold text-slate-950">{agent.name}</p>
                      <p className="mt-0.5 text-xs text-slate-500">{agent.owner_area}</p>
                    </div>
                  </div>
                  {agent.needs_intervention ? (
                    <StatusPill status="failed" label="Needs intervention" />
                  ) : (
                    <StatusPill status={agent.status} />
                  )}
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {agent.flow_types.map((flowType) => (
                    <span key={flowType} className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                      {humanize(flowType)}
                    </span>
                  ))}
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {detail ? (
        <section className="animate-fade-up rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <Avatar name={detail.name} size="lg" />
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-violet-700">Agent detail</p>
                <h2 className="mt-0.5 text-xl font-semibold text-slate-950">{detail.name}</h2>
                <p className="text-sm text-slate-600">{detail.owner_area}</p>
              </div>
            </div>
            <div className="flex flex-col items-end gap-2">
              <p className="flex items-center gap-2 text-xs text-slate-500">
                Operational control <StatusPill status={operationalStatus} />
              </p>
              <div className="inline-flex overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm" role="group" aria-label="Agent operational controls">
                {controls.map(({ action, label, enabled, style, icon }) => (
                  <button
                    key={action}
                    type="button"
                    onClick={() => control(action)}
                    disabled={!enabled}
                    className={`flex items-center gap-1.5 border-r border-slate-200 px-3.5 py-2 text-xs font-semibold transition-colors last:border-r-0 disabled:cursor-not-allowed disabled:text-slate-300 disabled:hover:bg-transparent ${style}`}
                  >
                    <span aria-hidden="true" className="text-[10px]">{icon}</span>
                    {label}
                  </button>
                ))}
              </div>
              {controlStatus === "waiting_for_human" ? <p className="text-xs text-violet-700">Waiting on business approval; operational controls stay separate.</p> : null}
              {controlError ? <p role="alert" className="text-xs text-red-700">{controlError}</p> : null}
            </div>
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-2">
            <div>
              <h3 className="font-semibold text-slate-900">Recent flows</h3>
              <div className="mt-3 space-y-3">
                {detail.last_5_flows.map((flow) => (
                  <details key={flow.flow_id} className="rounded-xl border border-slate-200 bg-slate-50/60 p-3">
                    <FlowSummary flowId={flow.flow_id} flowType={flow.flow_type} status={flow.status} triggeredBy={flow.triggered_by} />
                    <Timeline tasks={flow.tasks} />
                  </details>
                ))}
                {detail.last_5_flows.length === 0 ? (
                  <p className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">No flows yet. Start a conversation to see this agent work.</p>
                ) : null}
              </div>
            </div>
            <div>
              <h3 className="font-semibold text-slate-900">Latest steps</h3>
              {detail.last_10_tasks.length ? <Timeline tasks={detail.last_10_tasks} /> : <p className="mt-3 text-sm text-slate-500">No steps yet.</p>}
            </div>
          </div>
        </section>
      ) : null}

      <section className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm">
        <h2 className="text-xl font-semibold text-slate-950">Flow history</h2>
        <p className="text-sm text-slate-500">Each run, the agents that took part, and every step they took.</p>
        <div className="mt-4 space-y-3">
          {flows.map((flow) => (
            <details key={flow.flow_id} className="rounded-xl border border-slate-200 p-4 transition-shadow open:shadow-md">
              <FlowSummary flowId={flow.flow_id} flowType={flow.flow_type} status={flow.status} triggeredBy={flow.triggered_by} />
              {flow.participating_agents.map((participant) => (
                <div key={participant.agent_id} className="mt-4 rounded-xl bg-slate-50/70 p-3">
                  <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                    <Avatar name={participant.agent_name} size="sm" /> {participant.agent_name}
                    <StatusPill status={participant.status} />
                  </p>
                  <Timeline tasks={participant.tasks} />
                </div>
              ))}
            </details>
          ))}
          {flows.length === 0 ? <p className="text-sm text-slate-500">No flows recorded yet.</p> : null}
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-950">Full execution log</h2>
            <p className="text-sm text-slate-500">{log.total} persisted steps</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <select value={agentFilter} onChange={(event) => { setAgentFilter(event.target.value); setPage(1); }} className="rounded-lg border border-slate-200 bg-white p-2 text-sm shadow-sm" aria-label="Filter by agent">
              <option value="">All agents</option>
              {agents.map((agent) => <option key={agent.agent_id} value={agent.agent_id}>{agent.name}</option>)}
            </select>
            <select value={flowFilter} onChange={(event) => { setFlowFilter(event.target.value); setPage(1); }} className="rounded-lg border border-slate-200 bg-white p-2 text-sm shadow-sm" aria-label="Filter by flow">
              <option value="">All flows</option>
              {flows.map((flow) => <option key={flow.flow_id} value={flow.flow_id}>{humanize(flow.flow_type)} #{shortId(flow.flow_id)}</option>)}
            </select>
          </div>
        </div>
        <Timeline tasks={log.items} />
        <div className="mt-2 flex items-center justify-between">
          <button type="button" disabled={page === 1} onClick={() => setPage((value) => value - 1)} className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium shadow-sm transition-colors hover:bg-slate-50 disabled:opacity-40">← Previous</button>
          <span className="text-sm text-slate-600">Page {page}</span>
          <button type="button" disabled={page * 20 >= log.total} onClick={() => setPage((value) => value + 1)} className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium shadow-sm transition-colors hover:bg-slate-50 disabled:opacity-40">Next →</button>
        </div>
      </section>
    </div>
  );
}
