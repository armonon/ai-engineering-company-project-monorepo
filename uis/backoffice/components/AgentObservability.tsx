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

function TaskTrace({ task }: { task: ObservedTask }) {
  return (
    <li className="rounded-md border border-slate-200 bg-white p-3 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-slate-500">{task.task_id}</span>
        <span className="rounded-full bg-slate-100 px-2 py-1 font-semibold text-slate-700">
          {task.action_type}
        </span>
      </div>
      <dl className="mt-2 grid gap-1 text-slate-600 sm:grid-cols-2">
        <div><dt className="inline font-semibold">Trigger: </dt><dd className="inline">{task.trigger}</dd></div>
        <div><dt className="inline font-semibold">Previous: </dt><dd className="inline">{task.previous_task_id ?? "external"}</dd></div>
        <div><dt className="inline font-semibold">Next: </dt><dd className="inline">{task.next_task_id ?? "end"}</dd></div>
        <div><dt className="inline font-semibold">Derived: </dt><dd className="inline">{task.derived_task_ids.join(", ") || "none"}</dd></div>
      </dl>
    </li>
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

  return (
    <div className="space-y-8">
      {error ? <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p> : null}

      <section>
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-blue-700">Live registry</p>
            <h2 className="mt-1 text-xl font-semibold text-slate-950">TrackFlow agents</h2>
          </div>
          <p className="text-sm text-slate-500">Updates stream with authenticated SSE</p>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {agents.map((agent) => (
            <button
              key={agent.agent_id}
              type="button"
              onClick={() => setSelectedAgent(agent.agent_id)}
              className={`rounded-xl border p-4 text-left shadow-sm ${selectedAgent === agent.agent_id ? "border-blue-500 bg-blue-50" : "border-slate-200 bg-white"}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-mono text-xs text-slate-500">{agent.agent_id}</p>
                  <p className="mt-1 font-semibold text-slate-950">{agent.name}</p>
                  <p className="mt-1 text-xs text-slate-600">{agent.flow_types.join(", ")}</p>
                </div>
                <span className={`rounded-full px-2 py-1 text-xs font-semibold ${agent.needs_intervention ? "bg-red-100 text-red-800" : "bg-emerald-100 text-emerald-800"}`}>
                  {agent.needs_intervention ? "needs intervention" : agent.status}
                </span>
              </div>
            </button>
          ))}
        </div>
      </section>

      {detail ? (
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-violet-700">Agent detail</p>
              <h2 className="mt-1 text-xl font-semibold text-slate-950">{detail.name}</h2>
              <p className="mt-1 text-sm text-slate-600">{detail.owner_area}</p>
            </div>
            <div className="text-right">
              <p className="text-xs text-slate-500">Operational control · {controlStatus || detail.status}</p>
              <div className="mt-2 flex flex-wrap justify-end gap-2" aria-label="Agent operational controls">
                <button type="button" onClick={() => control("pause")} disabled={!(["running", "waiting_for_human"].includes(controlStatus))} className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold disabled:opacity-40">Pause</button>
                <button type="button" onClick={() => control("resume")} disabled={controlStatus !== "paused"} className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold disabled:opacity-40">Resume</button>
                <button type="button" onClick={() => control("cancel")} disabled={!(["running", "paused", "waiting_for_human"].includes(controlStatus))} className="rounded-md border border-red-300 px-3 py-1.5 text-xs font-semibold text-red-700 disabled:opacity-40">Cancel</button>
              </div>
              {controlStatus === "waiting_for_human" ? <p className="mt-2 text-xs text-violet-700">Waiting on business approval; operational controls remain separate.</p> : null}
              {controlError ? <p role="alert" className="mt-2 text-xs text-red-700">{controlError}</p> : null}
            </div>
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-2">
            <div>
              <h3 className="font-semibold text-slate-900">Last 5 flows</h3>
              <div className="mt-3 space-y-3">
                {detail.last_5_flows.map((flow) => (
                  <details key={flow.flow_id} className="rounded-lg bg-slate-50 p-3">
                    <summary className="cursor-pointer text-sm font-semibold">
                      {flow.flow_id} · {flow.status}
                    </summary>
                    <p className="mt-2 text-xs text-slate-600">Triggered by {flow.triggered_by}</p>
                    <ul className="mt-3 space-y-2">{flow.tasks.map((task) => <TaskTrace key={task.task_id} task={task} />)}</ul>
                  </details>
                ))}
                {detail.last_5_flows.length === 0 ? <p className="text-sm text-slate-500">No flows yet.</p> : null}
              </div>
            </div>
            <div>
              <h3 className="font-semibold text-slate-900">Last 10 tasks</h3>
              <ul className="mt-3 space-y-2">{detail.last_10_tasks.map((task) => <TaskTrace key={task.task_id} task={task} />)}</ul>
            </div>
          </div>
        </section>
      ) : null}

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-xl font-semibold text-slate-950">Flow history</h2>
        <div className="mt-4 space-y-3">
          {flows.map((flow) => (
            <details key={flow.flow_id} className="rounded-lg border border-slate-200 p-4">
              <summary className="cursor-pointer font-semibold text-slate-900">
                {flow.flow_id} · {flow.flow_type} · {flow.status}
              </summary>
              <p className="mt-2 text-sm text-slate-600">Triggered by {flow.triggered_by}</p>
              {flow.participating_agents.map((participant) => (
                <div key={participant.agent_id} className="mt-4 rounded-md bg-slate-50 p-3">
                  <p className="text-sm font-semibold">{participant.agent_name} · {participant.status}</p>
                  <ul className="mt-2 space-y-2">{participant.tasks.map((task) => <TaskTrace key={task.task_id} task={task} />)}</ul>
                </div>
              ))}
            </details>
          ))}
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div><h2 className="text-xl font-semibold text-slate-950">Full execution log</h2><p className="text-sm text-slate-500">{log.total} persisted tasks</p></div>
          <div className="flex flex-wrap gap-2">
            <select value={agentFilter} onChange={(event) => { setAgentFilter(event.target.value); setPage(1); }} className="rounded-md border border-slate-300 p-2 text-sm" aria-label="Filter by agent">
              <option value="">All agents</option>
              {agents.map((agent) => <option key={agent.agent_id} value={agent.agent_id}>{agent.name}</option>)}
            </select>
            <select value={flowFilter} onChange={(event) => { setFlowFilter(event.target.value); setPage(1); }} className="rounded-md border border-slate-300 p-2 text-sm" aria-label="Filter by flow">
              <option value="">All flows</option>
              {flows.map((flow) => <option key={flow.flow_id} value={flow.flow_id}>{flow.flow_id}</option>)}
            </select>
          </div>
        </div>
        <ul className="mt-4 space-y-2">{log.items.map((task) => <TaskTrace key={task.task_id} task={task} />)}</ul>
        <div className="mt-4 flex justify-between">
          <button type="button" disabled={page === 1} onClick={() => setPage((value) => value - 1)} className="rounded-md border px-3 py-2 text-sm disabled:opacity-40">Previous</button>
          <span className="text-sm text-slate-600">Page {page}</span>
          <button type="button" disabled={page * 20 >= log.total} onClick={() => setPage((value) => value + 1)} className="rounded-md border px-3 py-2 text-sm disabled:opacity-40">Next</button>
        </div>
      </section>
    </div>
  );
}
