# Graub AI
### Track 3: Agent Society — Global AI Hackathon Series with Qwen Cloud

## Inspiration

I've always noticed the structural advantage large companies have over small ones: a team, with the workload spread across people who each go deep in their own area. Most SMEs can't afford that — the founder ends up as marketer, accountant, IT support, and HR department, all at once, all without the depth any of those roles actually deserves. I've wanted for a long time to build something like a community — a shared pool of labor and expertise SMEs could draw on without needing to hire a full team themselves. Graub AI is my attempt at that: not a single assistant, but a small team of specialists an SME owner can actually delegate to.

## What it does

Graub AI is an agency of seven specialist AI agents — Marketing & Sales, Finance, IT/Technology, Operations, HR, Customer Service, and Leadership — each a junior-level assistant to a human expert in that domain. Given a business goal, an Orchestrator decomposes it into subtasks and assigns each to the right specialist. That agent drafts a proposal; Finance and IT_Tech independently audit it against hard, programmatically-enforced constraints (a budget ceiling, a technical-capacity cap); if either objects, the proposal goes back for revision, bounded to two negotiation rounds. If it still can't be resolved, the task escalates to a human Leadership authority rather than looping forever. Every proposal requires explicit human approval, and — separately — an explicit human publish step before anything is considered "live." Nothing executes on approval alone.

Beyond the core pipeline:
- **Business memory that compounds.** Every resolved task leaves a structured observation. Every five resolved tasks, one Qwen call distills recent observations into durable, reusable insights — which get fed back into every future agent's prompt. The system genuinely gets more informed over time, without prompts growing unboundedly.
- **Explainable, risk-aware decisions.** Every verdict carries a stated reason, a confidence score, and a low/medium/high risk rating — visible per task on a full negotiation timeline, not buried in logs.
- **Agents that are real standalone assistants, not pipeline-only stubs.** Every agent can be invoked independently — via a CLI (`run_agent.py`), a JSON REST API (`api.py`), or direct import — proving the architecture isn't just a monolith wearing seven hats.
- **A governance-gated path to real actions.** IT_Tech can propose file edits within a sandboxed workspace; the actual write only happens after the same approve → publish flow as any other proposal.
- **A path to SaaS, not just a demo.** A web-based setup wizard lets a client pick exactly which agents they want (enabled/disabled is enforced everywhere, not cosmetic), with subscription tiers already modeled — billing is explicitly future work, but the selection mechanism it depends on is real today.

## How I approached Track 3, specifically

The track asks for three things, and I built directly against each:

1. **How agents decompose tasks and assign roles** — the Orchestrator only offers domains that can actually propose or arbitrate as assignment targets (reviewer-only agents like Finance and IT_Tech are excluded at the prompt level, with a code-level redirect as a backstop even if the model tries anyway).
2. **How they resolve disagreements and execution conflicts** — real critique/revision cycles, bounded rounds, and a genuine escalation path to a different authority (Leadership) when agents can't resolve it themselves — not an infinite loop, not a silent pass-through.
3. **A measurable efficiency gain over a single-agent baseline** — `baseline_single_agent.py` runs the identical scenario through one generalist LLM call with the same constraints stated in its prompt; `run_comparison.py` runs the same scenarios through both systems and times them, reporting real negotiation-round counts, not estimates. Results are rendered directly on the live dashboard, not left in a file judges have to dig for.

## How I built it

Python, Flask, and SQLite, calling Qwen Cloud (`qwen3.7-plus`) through the OpenAI-compatible endpoint. A few technical decisions worth calling out:
- **Structured output with defense in depth.** Budget checks run as a fast regex pass *before* any LLM call, so a violation can't slip through even if a model reasons around it in conversation — the LLM review is a second layer, not the only one.
- **Extended "thinking" mode explicitly disabled.** In non-streaming mode, `qwen3.7-plus`'s default reasoning phase meant no response bytes at all until an entire hidden chain-of-thought finished — a real, measured latency problem I found and fixed, not a theoretical one.
- **Permission gates enforced in code, not just prompted.** An agent without "propose" permission is refused before a request is ever sent to Qwen Cloud.
- **Deployed on Alibaba Cloud ECS**, with connection resilience (retry with backoff, distinguishing genuine connection failures from recoverable JSON formatting issues) built after hitting both in practice.

## Challenges I ran into

Real ones, not manufactured for the narrative: an initially mis-scoped API endpoint (a dedicated-throughput hostname that doesn't resolve for standard accounts), a negotiation loop that looked complete but never actually called the reviewer functions, a UI querying the wrong task status so genuinely-ready approvals were invisible, and the thinking-mode latency issue above. Each is fixed and, where it seemed useful, documented in the README rather than hidden.

## Accomplishments I'm proud of

A negotiation pipeline that actually negotiates — verified by running real scenarios end to end and watching genuine critique → revision → resolution (or escalation) happen, not scripted. A memory system that meaningfully changes future agent behavior, not just a transcript log. Three independent ways to invoke any single agent, proving the "society" is made of real individual parts. Building this solo, end to end — architecture, agents, governance, UI, and deployment — in one hackathon window.

## What's next

Real billing (Stripe) tied to the subscription tiers that already exist structurally. Multi-tenant authentication, replacing the current single-hardcoded-client web session with real per-client login. Deeper integrations (Slack, QuickBooks, Shopify) once the core governance loop — the part I prioritized for this submission — has more real-world mileage on it. Longer term, this is the first piece of a bigger idea I've wanted to build for a while: a shared labor/expertise pool SMEs can draw from without each one needing to build or hire a full team of their own.

## Built With
Python · Flask · SQLite · Qwen Cloud (`qwen3.7-plus`, OpenAI-compatible API) · Alibaba Cloud ECS · Jinja2

---

*Track: Track 3 — Agent Society*
