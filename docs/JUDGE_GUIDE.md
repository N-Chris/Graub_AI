# Judge Quickstart — Graub AI (Track 3: Agent Society)

Five minutes, in this order:

## 1. Live demo (no setup required)
- Web portal: `http://<ECS-public-IP>:5002/dashboard` — scroll to "Baseline vs. Multi-Agent" for real measured numbers, and "Recent Activity" for live events.
- Click any Task ID (in Recent Activity, or in any agent's Review Activity) → `/task/<id>` — the full negotiation story for that task in plain English, followed by the raw event-by-event log.
- `/insights` — durable "business memory" the agents have accumulated, plus a live "Generate Predictions" button.

## 2. The core claim, and where the evidence is
The pitch: task decomposition → specialist negotiation with real Finance/IT audits → bounded conflict resolution (max 2 rounds) → escalation to a human authority if unresolved → mandatory human approval, separate from a mandatory human publish step.

- **Real negotiation, not a rubber stamp:** `main.py`'s `run_negotiation_pipeline()` — Finance and IT_Tech review every proposal inline; a rejected proposal gets revised and re-reviewed.
- **Real efficiency comparison:** `run_comparison.py` runs identical scenarios through a single-agent baseline (`baseline_single_agent.py`) and the full system, timing both. Results rendered on `/dashboard`, raw data in `comparison_results.json`.
- **Real governance, not just a demo:** approval (`/decide`) and publish (`/publish`) are two separate, separately-logged actions in `web_ui.py` — nothing executes on approval alone.

## 3. What makes this "Agent Society" rather than "one agent, several times"
- Agents disagree with each other. Finance/IT can reject a Marketing/HR/Operations proposal; that agent must revise it.
- Unresolved conflict escalates to a distinct human authority (Leadership), not back to the same reviewer.
- Every agent is independently invocable — `run_agent.py` (CLI), `api.py` (JSON REST), or import the module directly — proving they're real standalone assistants, not pipeline-only stubs.
- Institutional memory compounds: `business_memory.py` — every resolved task leaves an observation, periodically distilled into durable insights that get fed back into future prompts.

## 4. Fast ways to convince yourself it's real, not scripted
- `/task/<id>` for any resolved task shows genuine back-and-forth (critique → revision → re-review), with each agent's stated reasoning and risk rating, not just a final answer.
- Try `python run_agent.py --agent Finance --task "..."` — a real standalone call, no pipeline involved.
- `check_db.py` — dumps the live task board directly, if you want to verify the UI isn't showing anything staged.

## 5. Known, explicitly-scoped gaps (see README Roadmap)
Not hidden, not accidental — real billing, multi-tenant auth, and unrestricted local file access are all documented as deliberate post-hackathon scope, with the reasoning for why.
