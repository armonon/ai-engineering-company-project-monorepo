# TrackFlow — five-minute pitch

Use this as speaking guidance, not a word-for-word teleprompter. The target is
4:45–5:15 including the personal Q&A.

## 0:00–0:30 — Hook and introduction (camera)

> Logistics teams should not have to choose between fast AI automation and
> accountable human control. I’m [YOUR NAME], and I built TrackFlow, a last-mile
> delivery and warehousing platform that turns complex support and proposal work
> into grounded, observable agent workflows. It combines a real operations
> backoffice with evidence-based AI, durable approvals, and live controls.

## 0:30–1:10 — Problem and opportunity (camera, then product overview)

> Warehouse operators, dispatchers, and account managers work across inventory,
> incidents, customer questions, and detailed enterprise proposals. Their data
> is fragmented, decisions are time-sensitive, and a generic chatbot is risky:
> it can invent policy, expose another tenant’s data, or lose its place during a
> long approval. TrackFlow reduces that manual coordination while keeping every
> answer, tool call, and approval traceable.

Show the backoffice navigation briefly. Keep the screen zoomed to the workflow,
not the browser chrome.

## 1:10–3:10 — AI solution and live workflow (screen recording)

1. Open **RFP** and select the prepared ModaViva request.
2. Show intake extracting the request and routing work to the correct TrackFlow
   departments.
3. Explain that retrieval searches approved TrackFlow knowledge before a
   separate generation model drafts anything. If evidence is missing or weak,
   the system refuses to invent an answer.
4. Show the department drafts, evaluation evidence, and the independent human
   approval branches. Explain that each branch checkpoints state, so one pending
   owner does not block a different department.
5. Approve the prepared branches and show the final proposal being synthesized
   only after every active owner approves.
6. Open **Observability**. Show the flow trace, task chain, agent status, and one
   pause/resume control. Explain that controls are authenticated, resumable, and
   audited rather than killing work invisibly.

Suggested narration:

> The user experiences one workflow, but the engineering separates retrieval,
> routing, tools, drafting, evaluation, and approval. LangGraph gives each step
> an explicit transition and durable checkpoint. The company-tools MCP server
> exposes typed, read-only operations. The backoffice receives live progress
> through persisted server-sent events, while WebSockets carry authenticated
> pause, resume, and cancel controls. That makes the AI useful to operations,
> not just impressive in a chat window.

## 3:10–3:55 — Engineering decisions and challenge (camera plus trace)

> The hardest problem was making a long-running agent both grounded and
> interruptible. A free-form agent could answer quickly, but it was difficult to
> prove why it acted or resume safely after a human decision. I chose an explicit
> LangGraph workflow over an open-ended loop because proposal work needs durable
> checkpoints, deterministic routing, and independent approvals. I also chose
> evidence-only RAG and typed read-only tools over model memory because company
> policy and tenant boundaries cannot be guessed. I’m most proud that every AI
> step is observable and every human control becomes part of the same audit
> chain.

## 3:55–4:55 — Personal 4Geeks Q&A (camera)

Use your truthful answers from `QA_WORKSHEET.md`. For each response:

- look directly into the lens;
- pause for two full seconds before speaking;
- include the full question in the answer;
- pause for two full seconds after speaking.

Do not substitute generated personal claims. Shorten the earlier demo if the
three authentic answers need more time.

## Final frame

End on the TrackFlow backoffice or repository title and say:

> TrackFlow shows how I build AI systems that are useful, measurable, secure,
> and ready for human operators—not just prototypes that call a model.
