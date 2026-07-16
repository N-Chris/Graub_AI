"""
Persistent business memory: how Graub AI agents "learn" without model fine-tuning.

There's no weight-training happening here — that's a different, much larger project.
What this does instead is the standard pattern for LLM agent memory: record cheap,
structured observations after every resolved task (no LLM call needed), periodically
distill recent observations into a few compact "insights" via one Qwen call (so
prompts stay small even after months of history), and feed that memory back into
every agent's system prompt so its proposals and reviews are actually informed by
what's happened before — not just the task in front of it.

Three kinds of memory rows:
  - 'observation' — cheap, automatic, one line per resolved task. No LLM call.
  - 'insight'      — periodically distilled from recent observations. One LLM call
                      per CONSOLIDATE_EVERY_N_TASKS, replacing many raw rows with a
                      handful of durable lessons.
  - 'prediction'    — on-demand, human-triggered forward-looking suggestions.
"""
import sqlite3
from datetime import datetime
from config import DB_FILE, qwen_request

CONSOLIDATE_EVERY_N_TASKS = 5


def record_observation(client_id: str, domain: str, content: str, source_task_id: str = None):
    """Logs one cheap, structured fact. No LLM call — this just writes a row."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        "INSERT INTO business_memory (client_id, domain, category, content, source_task_id, created_at) "
        "VALUES (?, ?, 'observation', ?, ?, ?)",
        (client_id, domain, content, source_task_id, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


def record_task_outcome(client_id: str, task_id: str, domain: str, description: str, final_status: str):
    """Convenience wrapper: call this once a task is fully resolved (approved,
    rejected, or published). Turns the outcome into a short observation."""
    short_desc = (description[:140] + "...") if len(description) > 140 else description
    content = f"[{domain}] Task {task_id} ended as '{final_status}': {short_desc}"
    record_observation(client_id, domain, content, source_task_id=task_id)


def get_memory_context(client_id: str, domain: str = None, limit: int = 6) -> str:
    """Returns a short text block ready to drop into a system prompt: the most
    recent durable insights first, then recent raw observations if there's room.
    Returns '' (not an empty block) when there's no history yet, so early runs
    aren't cluttered with an empty 'Business Memory' section."""
    conn = sqlite3.connect(DB_FILE)
    insights = conn.execute(
        "SELECT content FROM business_memory WHERE client_id=? AND category='insight' "
        "AND (domain=? OR domain IS NULL OR domain='') ORDER BY id DESC LIMIT ?",
        (client_id, domain, limit)
    ).fetchall()
    remaining = max(0, limit - len(insights))
    observations = []
    if remaining:
        observations = conn.execute(
            "SELECT content FROM business_memory WHERE client_id=? AND category='observation' "
            "AND (domain=? OR domain IS NULL OR domain='') ORDER BY id DESC LIMIT ?",
            (client_id, domain, remaining)
        ).fetchall()
    conn.close()

    if not insights and not observations:
        return ""

    lines = [f"- {row[0]}" for row in insights] + [f"- {row[0]}" for row in observations]
    return (
        "BUSINESS MEMORY (what you've learned about this business so far — weigh this "
        "when drafting, it reflects real past outcomes, not hypotheticals):\n" + "\n".join(lines)
    )


def consolidate_if_needed(client_id: str):
    """Checks whether enough new observations have piled up since the last
    consolidation and, if so, makes ONE Qwen call to distill them into a few
    durable insights. This is what keeps memory compact and useful even after
    hundreds of resolved tasks, instead of prompts growing forever."""
    conn = sqlite3.connect(DB_FILE)
    last_insight = conn.execute(
        "SELECT id FROM business_memory WHERE client_id=? AND category='insight' ORDER BY id DESC LIMIT 1",
        (client_id,)
    ).fetchone()
    since_id = last_insight[0] if last_insight else 0

    new_observations = conn.execute(
        "SELECT content FROM business_memory WHERE client_id=? AND category='observation' AND id > ? ORDER BY id ASC",
        (client_id, since_id)
    ).fetchall()

    if len(new_observations) < CONSOLIDATE_EVERY_N_TASKS:
        conn.close()
        return  # not enough new activity yet — skip the LLM call entirely

    prior_insights = conn.execute(
        "SELECT content FROM business_memory WHERE client_id=? AND category='insight' ORDER BY id DESC LIMIT 5",
        (client_id,)
    ).fetchall()
    conn.close()

    obs_text = "\n".join(f"- {row[0]}" for row in new_observations)
    prior_text = "\n".join(f"- {row[0]}" for row in prior_insights) or "(none yet)"

    messages = [
        {"role": "system", "content": (
            "You maintain durable institutional memory for a small business run by AI "
            "agents. Read the prior insights and the new raw observations below. Output "
            "3-5 short, concrete, durable lessons (one sentence each, no preamble, no "
            "numbering, one per line) that would help agents make better decisions in "
            "future tasks — patterns, recurring friction, what tends to get approved vs "
            "critiqued, budget/timeline tendencies. Merge with prior insights rather than "
            "just appending; drop anything stale or superseded."
        )},
        {"role": "user", "content": f"Prior insights:\n{prior_text}\n\nNew observations:\n{obs_text}"}
    ]

    try:
        summary = qwen_request(messages, json_mode=False)
    except (ConnectionError, RuntimeError):
        return  # consolidation is a nice-to-have; never let it break the pipeline

    conn = sqlite3.connect(DB_FILE)
    for line in [l.strip("- ").strip() for l in summary.splitlines() if l.strip()]:
        conn.execute(
            "INSERT INTO business_memory (client_id, domain, category, content, source_task_id, created_at) "
            "VALUES (?, NULL, 'insight', ?, NULL, ?)",
            (client_id, line, datetime.utcnow().isoformat())
        )
    conn.commit()
    conn.close()


def generate_predictions(client_id: str, business_name: str) -> str:
    """On-demand: 'what should I expect / watch out for' suggestions for the human
    business owner, based on accumulated memory. This is the explicit 'predictions'
    feature — surfaced as a button in the dashboard, not run automatically."""
    conn = sqlite3.connect(DB_FILE)
    insights = conn.execute(
        "SELECT content FROM business_memory WHERE client_id=? AND category='insight' ORDER BY id DESC LIMIT 10",
        (client_id,)
    ).fetchall()
    recent_obs = conn.execute(
        "SELECT content FROM business_memory WHERE client_id=? AND category='observation' ORDER BY id DESC LIMIT 15",
        (client_id,)
    ).fetchall()
    conn.close()

    if not insights and not recent_obs:
        return "Not enough history yet — run a few tasks through main.py first, then check back here."

    memory_text = "\n".join(f"- {row[0]}" for row in insights + recent_obs)
    messages = [
        {"role": "system", "content": (
            f"You are a business-intelligence assistant for {business_name}. Based on the "
            f"accumulated history below, give the human owner 3-5 short, concrete, forward-"
            f"looking suggestions or predictions — things to watch out for, patterns worth "
            f"acting on, or recommended next steps. Be specific and practical, not generic. "
            f"One per line, no preamble, no numbering."
        )},
        {"role": "user", "content": memory_text}
    ]

    try:
        return qwen_request(messages, json_mode=False)
    except (ConnectionError, RuntimeError) as e:
        return f"Couldn't reach Qwen Cloud to generate predictions right now: {e}"
