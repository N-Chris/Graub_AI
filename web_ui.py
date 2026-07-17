from flask import Flask, render_template_string, request, redirect, url_for
from database import log_message, update_task_status, get_task
from client_config import load_client_config, save_client_config, DEFAULT_CONFIG, SUBSCRIPTION_TIERS, validate_agent_name
from config import qwen_request, DB_FILE
import agent_it
import file_tools
import business_memory
import sqlite3
import os
import json
import uuid

app = Flask(__name__)

# NOTE (known scope limitation): this portal currently reads/writes the "graub_ai"
# client config directly. A production multi-tenant SaaS version would resolve the
# client from a login session rather than hardcoding it here — see README roadmap.
CLIENT_ID = "graub_ai"

NAV = """
<div class="nav-links">
    <div class="nav-group">
        <span class="nav-label">Agent Portals</span>
        <div class="nav-row nav-chips">
            {% for domain, cfg in agents.items() %}
                {% if cfg.enabled %}<a class="nav-chip" href="/agent/{{ domain }}">{{ cfg.custom_name }}</a>{% endif %}
            {% endfor %}
        </div>
    </div>
</div>
"""

HEADER = """
<div class="topbar">
    <div class="topbar-inner">
        <span class="wordmark">Graub AI</span>
        <nav class="topbar-nav">
            <a href="/">Home</a><a href="/setup">Setup</a><a href="/dashboard">Dashboard</a><a href="/insights">Insights</a>
        </nav>
    </div>
</div>
"""

STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

    :root {
        --forest: #1B4332;
        --forest-mid: #2D6A4F;
        --sage: #52B788;
        --powder: #A9D6E5;
        --powder-deep: #468FAF;
        --cream: #F6FAF7;
        --white: #FFFFFF;
        --ink: #16241D;
        --ink-soft: #5B6F64;
        --line: #DCE8E2;
        --warn: #C97B3D;
        --danger: #A8492E;
    }

    * { box-sizing: border-box; }

    body {
        font-family: 'IBM Plex Sans', -apple-system, sans-serif;
        margin: 0;
        padding: 0;
        color: var(--ink);
        line-height: 1.6;
        background: linear-gradient(180deg, #CFE7EF 0%, #E4F1F5 340px, #EEF6F8 100%);
        min-height: 100vh;
    }

    .topbar { background: var(--forest); }
    .topbar-inner {
        max-width: 920px;
        margin: 0 auto;
        padding: 16px 24px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 12px;
    }
    .wordmark {
        font-family: 'Fraunces', serif;
        font-weight: 600;
        font-size: 18px;
        letter-spacing: 0.01em;
        color: var(--white);
    }
    .topbar-nav { display: flex; gap: 26px; }
    .topbar-nav a {
        color: var(--powder);
        font-size: 13.5px;
        font-weight: 500;
        letter-spacing: 0.02em;
        text-decoration: none;
    }
    .topbar-nav a:hover { color: var(--white); text-decoration: none; }

    .container {
        max-width: 920px;
        margin: 44px auto;
        background: var(--white);
        padding: 44px 48px;
        border-radius: 16px;
        border: 1px solid rgba(27,67,50,0.08);
        box-shadow: 0 2px 4px rgba(27,67,50,0.05), 0 24px 48px -12px rgba(27,67,50,0.18);
    }

    .kicker {
        display: block;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 11px;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--powder-deep);
        font-weight: 500;
        margin-bottom: 10px;
    }

    h1 {
        font-family: 'Fraunces', serif;
        font-weight: 600;
        font-size: 33px;
        letter-spacing: -0.01em;
        color: var(--forest);
        margin: 0 0 8px 0;
        padding-bottom: 16px;
        border-bottom: 2px solid var(--powder);
    }
    h3 {
        font-family: 'Fraunces', serif;
        font-weight: 600;
        font-size: 19px;
        color: var(--forest-mid);
        margin-top: 34px;
        margin-bottom: 12px;
    }
    p { color: var(--ink-soft); }
    a { color: var(--powder-deep); text-decoration: none; font-weight: 500; }
    a:hover { color: var(--forest); text-decoration: underline; }
    code { background: var(--cream); border: 1px solid var(--line); border-radius: 4px; padding: 1px 6px; font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: var(--forest-mid); }

    /* Signature motif: every card reads like a stamped ledger entry — a solid
       forest spine on the left, consistent regardless of what kind of card it is. */
    .task-card, .publish-card, .file-card {
        border: 1px solid var(--line);
        border-left: 4px solid var(--forest);
        padding: 18px 20px;
        margin: 14px 0;
        border-radius: 8px;
        background: var(--cream);
    }
    .publish-card { border-left-color: var(--sage); background: #F1FAF5; }
    .file-card { border-left-color: var(--warn); background: #FDF6EE; }

    .btn {
        font-family: 'IBM Plex Sans', sans-serif;
        padding: 10px 22px;
        border: none;
        border-radius: 7px;
        font-weight: 600;
        font-size: 14px;
        cursor: pointer;
        margin-right: 10px;
        transition: transform 0.08s ease, box-shadow 0.15s ease;
    }
    .btn:hover { transform: translateY(-1px); }
    .btn:active { transform: translateY(0); }
    .btn-approve { background: var(--forest); color: var(--white); }
    .btn-approve:hover { background: var(--forest-mid); }
    .btn-reject { background: var(--white); color: var(--danger); border: 1.5px solid var(--danger); }
    .btn-reject:hover { background: #FBEEE9; }
    .btn-publish { background: var(--powder-deep); color: var(--white); }
    .btn-publish:hover { background: #3A7A97; }

    .input-text {
        width: 100%;
        padding: 11px 14px;
        margin: 10px 0;
        border: 1.5px solid var(--line);
        border-radius: 7px;
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 14px;
        background: var(--white);
    }
    .input-text:focus { outline: none; border-color: var(--powder-deep); box-shadow: 0 0 0 3px rgba(70,143,175,0.15); }

    .nav-links {
        margin-top: 32px;
        padding-top: 22px;
        border-top: 1px solid var(--line);
        display: flex;
        flex-wrap: wrap;
        gap: 28px;
        justify-content: space-between;
    }
    .nav-group { flex: 1; min-width: 220px; }
    .nav-label {
        display: block;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-size: 11px;
        color: var(--forest-mid);
        font-weight: 600;
        margin-bottom: 10px;
    }
    .nav-row { display: flex; flex-wrap: wrap; gap: 8px 18px; }
    .nav-row a { font-size: 13.5px; }
    .nav-chips { gap: 8px; }
    .nav-chip {
        background: var(--cream);
        border: 1px solid var(--line);
        border-radius: 20px;
        padding: 5px 13px;
        font-size: 12.5px !important;
        font-weight: 500;
        color: var(--forest-mid) !important;
    }
    .nav-chip:hover { background: var(--powder); color: var(--forest) !important; border-color: var(--powder-deep); text-decoration: none !important; }

    .chat-box {
        background: var(--cream);
        border: 1px solid var(--line);
        border-radius: 10px;
        padding: 16px;
        max-height: 320px;
        overflow-y: auto;
    }
    .bubble-human {
        background: var(--powder);
        color: var(--forest);
        padding: 9px 14px;
        border-radius: 12px 12px 3px 12px;
        margin: 7px 0;
        max-width: 75%;
        margin-left: auto;
        font-size: 14px;
    }
    .bubble-agent {
        background: var(--white);
        border: 1px solid var(--line);
        padding: 9px 14px;
        border-radius: 12px 12px 12px 3px;
        margin: 7px 0;
        max-width: 75%;
        font-size: 14px;
    }
    .chat-form { display: flex; gap: 10px; margin-top: 12px; }
    .chat-form input { flex: 1; }

    .kpi-row { display: flex; gap: 16px; flex-wrap: wrap; }
    .kpi-card {
        flex: 1;
        min-width: 140px;
        border: 1px solid var(--line);
        border-top: 3px solid var(--forest);
        border-radius: 10px;
        padding: 18px 16px;
        text-align: center;
        background: var(--cream);
    }
    .kpi-num { font-family: 'Fraunces', serif; font-size: 30px; font-weight: 600; color: var(--forest); }
    .kpi-label { color: var(--ink-soft); font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 2px; }

    table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    th {
        text-align: left; padding: 9px 8px; font-size: 11px; text-transform: uppercase;
        letter-spacing: 0.05em; color: var(--forest-mid); border-bottom: 2px solid var(--powder);
    }
    td { text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--line); font-size: 13px; }
    pre { background: var(--cream); border: 1px solid var(--line); padding: 12px; border-radius: 6px; overflow-x: auto; font-family: 'IBM Plex Mono', monospace; font-size: 12px; }

    .diff-old { background: #FBEEE9; }
    .diff-new { background: #EAF6EF; }

    .agent-row { display: flex; align-items: center; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--line); }
    .agent-row input[type=text] { flex: 1; padding: 7px 10px; }

    /* Ledger-stamp status badges — the recurring "verdict" motif */
    .stamp {
        display: inline-block; font-family: 'IBM Plex Mono', monospace; font-size: 11px;
        text-transform: uppercase; letter-spacing: 0.06em; font-weight: 500;
        padding: 3px 9px; border-radius: 4px; border: 1.5px solid currentColor;
    }
    .stamp-accept { color: var(--forest-mid); }
    .stamp-critique { color: var(--warn); }

    .risk-dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; }
    .risk-low { background: var(--sage); }
    .risk-med { background: var(--powder-deep); }
    .risk-high { background: var(--danger); }

    .confidence-bar { display: inline-block; width: 60px; height: 6px; background: var(--line); border-radius: 3px; overflow: hidden; vertical-align: middle; }
    .confidence-fill { display: block; height: 100%; background: var(--forest-mid); }

    .timeline { position: relative; margin-top: 18px; padding-left: 26px; border-left: 2px solid var(--line); }
    .timeline-item { position: relative; margin-bottom: 22px; }
    .timeline-dot { position: absolute; left: -33px; top: 3px; width: 12px; height: 12px; border-radius: 50%; border: 2px solid var(--white); }
    .timeline-dot-default { background: var(--powder-deep); }
    .timeline-dot-ok { background: var(--sage); }
    .timeline-dot-warn { background: var(--warn); }
    .timeline-dot-danger { background: var(--danger); }
    .timeline-meta { font-size: 12px; color: var(--ink-soft); margin-bottom: 4px; }
    .timeline-content { font-size: 14px; color: var(--ink); background: var(--cream); border: 1px solid var(--line); border-radius: 7px; padding: 10px 14px; }
</style>
"""

# ---------------------------------------------------------------------------
# HOME
# ---------------------------------------------------------------------------
HOME_HTML = STYLE + HEADER + """
<div class="container">
    <span class="kicker">Home</span>
    <h1>{{ business_name }}</h1>
    <p>An agency of specialist agents running your business's day-to-day work, with a human expert as final approval before anything executes.</p>
    <p><b>Subscription tier:</b> {{ tier_label }}</p>
""" + NAV + """
</div>
"""

@app.route("/")
def home():
    config = load_client_config(CLIENT_ID)
    tier = config.get("subscription_tier", "full")
    tier_label = SUBSCRIPTION_TIERS.get(tier, {}).get("label", tier)
    return render_template_string(HOME_HTML, business_name=config["business_name"],
                                    tier_label=tier_label, agents=config["agents"])

# ---------------------------------------------------------------------------
# SETUP — pick agents, name them, set permissions, choose tier
# ---------------------------------------------------------------------------
SETUP_HTML = STYLE + HEADER + """
<div class="container">
    <span class="kicker">Configuration</span>
    <h1>{{ config.business_name }}</h1>
    <form method="post">
        <label><b>Business Name</b></label>
        <input class="input-text" type="text" name="business_name" value="{{ config.business_name }}" required>

        <label><b>Subscription Tier</b></label><br>
        <select name="subscription_tier" class="input-text">
            {% for key, tier in tiers.items() %}
            <option value="{{ key }}" {% if key == config.subscription_tier %}selected{% endif %}>{{ tier.label }}</option>
            {% endfor %}
        </select>
        <p style="color:#6a737d; font-size:13px;">Tier only pre-selects recommended agents below — no payment is processed here. Billing integration is a post-hackathon roadmap item.</p>

        <h3>Agents</h3>
        {% for domain, cfg in config.agents.items() %}
        <div class="agent-row">
            <input type="checkbox" name="enabled_{{ domain }}" {% if cfg.enabled %}checked{% endif %}>
            <span style="min-width:140px;">{{ domain }}</span>
            <input type="text" name="name_{{ domain }}" value="{{ cfg.custom_name }}" placeholder="Custom name">
            <input type="text" name="perms_{{ domain }}" value="{{ cfg.permissions|join(', ') }}" placeholder="permissions, comma-separated">
        </div>
        {% endfor %}

        {% if error %}<p style="color:#dc3545;"><b>{{ error }}</b></p>{% endif %}
        <br>
        <button type="submit" class="btn btn-publish">Save Configuration</button>
    </form>
""" + NAV + """
</div>
"""

@app.route("/setup", methods=["GET", "POST"])
def setup():
    config = load_client_config(CLIENT_ID)

    if request.method == "POST":
        new_config = json.loads(json.dumps(config))  # deep copy
        new_config["business_name"] = request.form.get("business_name", config["business_name"]).strip()
        new_config["subscription_tier"] = request.form.get("subscription_tier", config.get("subscription_tier", "full"))

        proposed_names = {}
        for domain in config["agents"]:
            proposed_names[domain] = request.form.get(f"name_{domain}", domain).strip() or domain

        # Validate no duplicate names before saving anything
        seen = set()
        for domain, name in proposed_names.items():
            if name.lower() in seen:
                return render_template_string(
                    SETUP_HTML, config=config, tiers=SUBSCRIPTION_TIERS,
                    error=f"Duplicate agent name detected: '{name}'. Each agent needs a unique name.",
                    agents=config["agents"]
                )
            seen.add(name.lower())

        for domain in config["agents"]:
            new_config["agents"][domain]["enabled"] = request.form.get(f"enabled_{domain}") is not None
            new_config["agents"][domain]["custom_name"] = proposed_names[domain]
            perms_raw = request.form.get(f"perms_{domain}", "")
            new_config["agents"][domain]["permissions"] = [p.strip() for p in perms_raw.split(",") if p.strip()]

        save_client_config(CLIENT_ID, new_config)
        return redirect(url_for("home"))

    return render_template_string(SETUP_HTML, config=config, tiers=SUBSCRIPTION_TIERS, error=None, agents=config["agents"])

# ---------------------------------------------------------------------------
# DASHBOARD — aggregate view across the whole system
# ---------------------------------------------------------------------------
DASHBOARD_HTML = STYLE + HEADER + """
<div class="container">
    <span class="kicker">Operations Overview</span>
    <h1>{{ business_name }}</h1>
    <div class="kpi-row">
        <div class="kpi-card"><div class="kpi-num">{{ total_tasks }}</div><div class="kpi-label">Total Tasks</div></div>
        <div class="kpi-card"><div class="kpi-num">{{ total_messages }}</div><div class="kpi-label">Messages Logged</div></div>
        <div class="kpi-card"><div class="kpi-num">{{ negotiation_rounds }}</div><div class="kpi-label">Negotiation Rounds</div></div>
        <div class="kpi-card"><div class="kpi-num">{{ escalations }}</div><div class="kpi-label">Escalations to Leadership</div></div>
    </div>

    <h3>Pending Approvals by Agent</h3>
    <table>
        <tr><th>Agent</th><th>Pending</th><th>Ready to Publish</th><th>Reviews Issued</th></tr>
        {% for row in per_agent %}
        <tr><td>{{ row[0] }}</td><td>{{ row[1] }}</td><td>{{ row[2] }}</td><td>{{ row[3] }}</td></tr>
        {% endfor %}
    </table>

    {% if comparison %}
    <h3>Baseline vs. Multi-Agent — Real Measured Results</h3>
    <table>
        <tr><th>Scenario</th><th>Baseline (s)</th><th>Multi-Agent (s)</th><th>Negotiation Rounds</th><th>Subtasks</th></tr>
        {% for row in comparison %}
        <tr>
            <td>{{ row.scenario }}</td>
            <td>{{ row.baseline_time_seconds }}</td>
            <td>{{ row.multi_agent_time_seconds }}</td>
            <td>{{ row.multi_agent_negotiation_rounds }}</td>
            <td>{{ row.multi_agent_subtasks }}</td>
        </tr>
        {% endfor %}
    </table>
    <p style="color:#6a737d; font-size:13px;">Generated by <code>run_comparison.py</code> — real timings from actual runs, not estimates.</p>
    {% endif %}

    <h3>Recent Activity</h3>
    <table>
        <tr><th>Time</th><th>From</th><th>To</th><th>Type</th><th>Task</th></tr>
        {% for row in recent %}
        <tr><td>{{ row[0] }}</td><td>{{ row[1] }}</td><td>{{ row[2] }}</td><td>{{ row[3] }}</td><td>{% if row[4] and row[4] not in ['chat'] %}<a href="/task/{{ row[4] }}">{{ row[4] }}</a>{% else %}—{% endif %}</td></tr>
        {% endfor %}
    </table>
""" + NAV + """
</div>
"""

@app.route("/dashboard")
def dashboard():
    config = load_client_config(CLIENT_ID)
    if not os.path.exists(DB_FILE):
        return "<h3>Database not initialized yet. Run main.py first.</h3>"

    conn = sqlite3.connect(DB_FILE)
    total_tasks = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    total_messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    negotiation_rounds = conn.execute("SELECT COUNT(*) FROM messages WHERE type='loop_iteration'").fetchone()[0]
    escalations = conn.execute("SELECT COUNT(*) FROM messages WHERE type='conflict_flag'").fetchone()[0]

    per_agent = []
    for domain, cfg in config["agents"].items():
        if not cfg["enabled"]:
            continue
        pending = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE assigned_to=? AND "
            "(status='pending_human_review' OR (status='assigned' AND file_target IS NOT NULL))",
            (domain,)
        ).fetchone()[0]
        ready = conn.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=? AND status='approved_for_execution'", (domain,)).fetchone()[0]
        reviews = conn.execute("SELECT COUNT(*) FROM messages WHERE from_agent=? AND type IN ('accept','critique')", (domain,)).fetchone()[0]
        per_agent.append((cfg["custom_name"], pending, ready, reviews))

    recent = conn.execute(
        "SELECT timestamp, from_agent, to_agent, type, task_id FROM messages ORDER BY id DESC LIMIT 20"
    ).fetchall()
    conn.close()

    recent_clean = [(str(r[0]).split("T")[-1][:8] if "T" in str(r[0]) else str(r[0])[:8], r[1], r[2], r[3], r[4]) for r in recent]

    comparison = None
    if os.path.exists("comparison_results.json"):
        try:
            with open("comparison_results.json") as f:
                comparison = json.load(f)
        except (json.JSONDecodeError, OSError):
            comparison = None

    return render_template_string(
        DASHBOARD_HTML, business_name=config["business_name"],
        total_tasks=total_tasks, total_messages=total_messages,
        negotiation_rounds=negotiation_rounds, escalations=escalations,
        per_agent=per_agent, recent=recent_clean, agents=config["agents"],
        comparison=comparison
    )

# ---------------------------------------------------------------------------
# INSIGHTS — durable business memory + on-demand predictions
# ---------------------------------------------------------------------------
INSIGHTS_HTML = STYLE + HEADER + """
<div class="container">
    <span class="kicker">Business Memory</span>
    <h1>{{ business_name }}</h1>
    <p>What the agents have learned from running your business over time. Not a static config — this grows with every resolved task.</p>

    <h3>Durable Insights</h3>
    {% if insights %}
        <ul>{% for row in insights %}<li>{{ row[0] }}</li>{% endfor %}</ul>
    {% else %}
        <p style="color:#6a737d;"><i>None yet — insights are distilled automatically every {{ consolidate_every }} resolved tasks. Keep running main.py.</i></p>
    {% endif %}

    <h3>Recent Raw Observations</h3>
    {% if observations %}
        <ul>{% for row in observations %}<li style="color:#6a737d; font-size:13px;">{{ row[0] }}</li>{% endfor %}</ul>
    {% else %}
        <p style="color:#6a737d;"><i>Nothing recorded yet — this fills in as tasks get resolved via the agent portals.</i></p>
    {% endif %}

    <h3>Predictions</h3>
    <form method="post" action="/insights/predict">
        <button type="submit" class="btn btn-publish">Generate Predictions Now</button>
    </form>
    {% if predictions %}
        <div class="task-card"><pre style="white-space:pre-wrap;">{{ predictions }}</pre></div>
    {% endif %}

    <h3>Knowledge Base — published documents</h3>
    {% if kb_files %}
        <table>
            <tr><th>File</th><th>Size</th></tr>
            {% for f in kb_files %}
            <tr><td>{{ f[0] }}</td><td>{{ f[1] }} bytes</td></tr>
            {% endfor %}
        </table>
        <p style="color:#6a737d; font-size:13px;">Every real document a human has approved and published through IT_Tech's file-edit workflow ends up here — a growing, auditable record of what the business has actually produced.</p>
    {% else %}
        <p style="color:#6a737d;"><i>Nothing published yet — request a file edit from the IT_Tech portal, then approve and publish it, and it'll appear here.</i></p>
    {% endif %}
""" + NAV + """
</div>
"""

@app.route("/insights", methods=["GET"])
def insights():
    config = load_client_config(CLIENT_ID)
    client_id = config["client_id"]
    if not os.path.exists(DB_FILE):
        return "<h3>Database not initialized yet. Run main.py first.</h3>"

    conn = sqlite3.connect(DB_FILE)
    insight_rows = conn.execute(
        "SELECT content FROM business_memory WHERE client_id=? AND category='insight' ORDER BY id DESC LIMIT 15",
        (client_id,)
    ).fetchall()
    observation_rows = conn.execute(
        "SELECT content FROM business_memory WHERE client_id=? AND category='observation' ORDER BY id DESC LIMIT 15",
        (client_id,)
    ).fetchall()
    conn.close()

    return render_template_string(
        INSIGHTS_HTML, business_name=config["business_name"],
        insights=insight_rows, observations=observation_rows,
        consolidate_every=business_memory.CONSOLIDATE_EVERY_N_TASKS,
        predictions=None, agents=config["agents"], kb_files=file_tools.list_workspace_files()
    )

@app.route("/insights/predict", methods=["POST"])
def insights_predict():
    config = load_client_config(CLIENT_ID)
    client_id = config["client_id"]
    predictions = business_memory.generate_predictions(client_id, config["business_name"])

    conn = sqlite3.connect(DB_FILE)
    insight_rows = conn.execute(
        "SELECT content FROM business_memory WHERE client_id=? AND category='insight' ORDER BY id DESC LIMIT 15",
        (client_id,)
    ).fetchall()
    observation_rows = conn.execute(
        "SELECT content FROM business_memory WHERE client_id=? AND category='observation' ORDER BY id DESC LIMIT 15",
        (client_id,)
    ).fetchall()
    conn.close()

    return render_template_string(
        INSIGHTS_HTML, business_name=config["business_name"],
        insights=insight_rows, observations=observation_rows,
        consolidate_every=business_memory.CONSOLIDATE_EVERY_N_TASKS,
        predictions=predictions, agents=config["agents"], kb_files=file_tools.list_workspace_files()
    )

# ---------------------------------------------------------------------------
# TASK TIMELINE — the full story of one task: goal -> proposal -> critique ->
# revision -> negotiation -> escalation -> human decision -> publish
# ---------------------------------------------------------------------------
TIMELINE_HTML = STYLE + HEADER + """
<div class="container">
    <span class="kicker">Task Timeline</span>
    <h1>{{ task_id }}</h1>
    <p><b>Assigned to:</b> {{ task[1] if task else '—' }} &nbsp;·&nbsp; <b>Status:</b> {{ task[4] if task else '—' }}</p>

    {% if summary %}
        <div class="task-card"><b>What happened:</b> {{ summary }}</div>
    {% endif %}

    {% if not events %}
        <p style="color:#6a737d;"><i>No activity logged yet for this task.</i></p>
    {% else %}
        <div class="timeline">
        {% for e in events %}
            <div class="timeline-item">
                <div class="timeline-dot
                    {% if e[3] == 'critique' %}timeline-dot-warn
                    {% elif e[3] in ['accept','published','approved_for_execution'] %}timeline-dot-ok
                    {% elif e[3] == 'conflict_flag' %}timeline-dot-danger
                    {% else %}timeline-dot-default{% endif %}"></div>
                <div class="timeline-body">
                    <div class="timeline-meta">
                        <b>{{ e[1] }}</b> → {{ e[2] }} &nbsp;·&nbsp; <span class="kicker" style="display:inline;">{{ e[3] }}</span>
                        {% if e[6] %}<span class="risk-dot risk-{{ 'high' if e[6]=='high' else ('low' if e[6]=='low' else 'med') }}" title="{{ e[6] }} risk"></span>{% endif %}
                        &nbsp;·&nbsp; {{ e[5].split('T')[-1][:8] if e[5] and 'T' in e[5] else e[5] }}
                    </div>
                    <div class="timeline-content">{{ e[4] }}</div>
                    {% if e[7] is not none %}<div class="confidence-bar"><span class="confidence-fill" style="width:{{ (e[7]*100)|int }}%;"></span></div>{% endif %}
                </div>
            </div>
        {% endfor %}
        </div>
    {% endif %}

    <p style="margin-top:28px;"><a href="/dashboard">&larr; Back to Dashboard</a></p>
""" + NAV + """
</div>
"""

@app.route("/task/<task_id>")
def task_timeline(task_id):
    config = load_client_config(CLIENT_ID)
    if not os.path.exists(DB_FILE):
        return "<h3>Database not initialized yet.</h3>"

    conn = sqlite3.connect(DB_FILE)
    task = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
    events = conn.execute(
        "SELECT id, from_agent, to_agent, type, content, timestamp, risk_level, confidence "
        "FROM messages WHERE task_id=? ORDER BY id ASC",
        (task_id,)
    ).fetchall()
    conn.close()

    summary = None
    if events:
        try:
            event_text = "\n".join(f"- {e[1]} -> {e[2]} [{e[3]}]: {e[4]}" for e in events)
            summary = qwen_request([
                {"role": "system", "content": (
                    "Summarize this task's event log in 2-3 plain-English sentences for a "
                    "busy business owner glancing at a dashboard. No preamble, no jargon, "
                    "just what happened and how it ended."
                )},
                {"role": "user", "content": event_text}
            ])
        except (ConnectionError, RuntimeError):
            summary = None  # non-fatal — the raw timeline below still tells the full story

    return render_template_string(TIMELINE_HTML, task_id=task_id, task=task, events=events, agents=config["agents"], summary=summary)

# ---------------------------------------------------------------------------
# AGENT PORTAL — pending approvals, publish queue, file-edit requests, chat
# ---------------------------------------------------------------------------
AGENT_HTML = STYLE + HEADER + """
<div class="container">
    <span class="kicker">Departmental Portal</span>
    <h1>{{ agent_name }}</h1>

    <h3>Review Activity — verdicts this agent has issued</h3>
    {% if review_activity %}
        <table>
            <tr><th>Task</th><th>Verdict</th><th>Risk</th><th>Reason</th><th>Time</th></tr>
            {% for row in review_activity %}
            <tr>
                <td><a href="/task/{{ row[0] }}">{{ row[0] }}</a></td>
                <td>{% if row[1] == 'critique' %}<span class="stamp stamp-critique">Critique</span>{% else %}<span class="stamp stamp-accept">Accept</span>{% endif %}</td>
                <td>{% if row[4] == 'high' %}<span class="risk-dot risk-high" title="High risk"></span>{% elif row[4] == 'low' %}<span class="risk-dot risk-low" title="Low risk"></span>{% else %}<span class="risk-dot risk-med" title="Medium risk"></span>{% endif %}</td>
                <td>{{ row[2] }}</td>
                <td>{{ row[3].split('T')[-1][:8] if 'T' in row[3] else row[3] }}</td>
            </tr>
            {% endfor %}
        </table>
        <p style="color:#6a737d; font-size:13px;">This agent reviews every proposal inline as part of the negotiation pipeline — it doesn't get its own approval queue the way proposing agents do. This is its actual activity log. Click a task ID to see its full story.</p>
    {% else %}
        <p style="color: #6a737d;"><i>No reviews issued yet. This fills in once <code>main.py</code> has run at least one task through the pipeline — this agent reviews every proposal automatically, it isn't something you trigger manually.</i></p>
    {% endif %}

    <h3>Pending Approvals</h3>
    {% if pending %}
        {% for task in pending %}
        <div class="task-card">
            <p><b>Task Reference ID:</b> {{ task[0] }}</p>
            <p><b>Description:</b> {{ task[1] }}</p>
            <form method="post" action="/decide/{{ task[0] }}/{{ agent_name }}">
                <input type="text" name="comment" class="input-text" placeholder="Enter custom directive or modification remarks...">
                <button type="submit" name="decision" value="Approve" class="btn btn-approve">Authorize Action</button>
                <button type="submit" name="decision" value="Reject" class="btn btn-reject">Issue Critique</button>
            </form>
        </div>
        {% endfor %}
    {% else %}
        <p style="color: #6a737d;"><i>No items pending your review right now.</i></p>
    {% endif %}

    <h3>Approved — Ready to Publish</h3>
    {% if ready_to_publish %}
        {% for task in ready_to_publish %}
        <div class="publish-card">
            <p><b>Task Reference ID:</b> {{ task[0] }}</p>
            <p><b>Description:</b> {{ task[1] }}</p>
            {% if task[2] %}
                <p><b>File target:</b> <code>{{ task[2] }}</code> (writing to disk happens only on publish)</p>
            {% endif %}
            <p style="color:#0066cc;"><i>Approved internally. Nothing external happens until you publish it.</i></p>
            <form method="post" action="/publish/{{ task[0] }}/{{ agent_name }}">
                <button type="submit" class="btn btn-publish">Publish / Execute</button>
            </form>
        </div>
        {% endfor %}
    {% else %}
        <p style="color: #6a737d;"><i>Nothing approved and waiting to publish.</i></p>
    {% endif %}

    {% if agent_name == "IT_Tech" %}
    <h3>💻 Request a File Edit (sandboxed to client_workspace/)</h3>
    <form method="post" action="/request_file_edit">
        <input type="text" name="relative_path" class="input-text" placeholder="e.g. notes/pricing.txt" required>
        <input type="text" name="instruction" class="input-text" placeholder="What should change?" required>
        <button type="submit" class="btn btn-publish">Ask IT_Tech to Draft This Edit</button>
    </form>
    {% endif %}

    <h3>💬 Chat with {{ agent_name }}</h3>
    <div class="chat-box">
        {% for msg in chat_thread %}
            {% if msg[0] == 'human_chat' %}
                <div class="bubble-human">{{ msg[1] }}</div>
            {% else %}
                <div class="bubble-agent"><b>{{ agent_name }}:</b> {{ msg[1] }}</div>
            {% endif %}
        {% endfor %}
    </div>
    <form method="post" action="/chat/{{ agent_name }}" class="chat-form">
        <input type="text" name="message" placeholder="Message {{ agent_name }}..." required>
        <button type="submit" class="btn btn-publish">Send</button>
    </form>
""" + NAV + """
</div>
"""

@app.route("/agent/<agent_name>")
def agent_view(agent_name):
    if not os.path.exists(DB_FILE):
        return "<h3>Database ledger not initialized yet. Run main.py first to seed records.</h3>"

    config = load_client_config(CLIENT_ID)
    conn = sqlite3.connect(DB_FILE)

    pending = conn.execute(
        "SELECT task_id, description FROM tasks WHERE assigned_to=? AND "
        "(status='pending_human_review' OR (status='assigned' AND file_target IS NOT NULL))",
        (agent_name,)
    ).fetchall()

    ready_to_publish = conn.execute(
        "SELECT task_id, description, file_target FROM tasks WHERE assigned_to=? AND status='approved_for_execution'",
        (agent_name,)
    ).fetchall()

    chat_thread = conn.execute(
        "SELECT type, content FROM messages WHERE type IN ('human_chat','agent_chat_reply') "
        "AND (from_agent=? OR to_agent=?) ORDER BY id ASC LIMIT 50",
        (agent_name, agent_name)
    ).fetchall()

    review_activity = conn.execute(
        "SELECT task_id, type, content, timestamp, risk_level FROM messages "
        "WHERE from_agent=? AND type IN ('accept','critique') ORDER BY id DESC LIMIT 20",
        (agent_name,)
    ).fetchall()

    conn.close()
    return render_template_string(
        AGENT_HTML, agent_name=agent_name, agents=config["agents"],
        pending=pending, ready_to_publish=ready_to_publish, chat_thread=chat_thread,
        review_activity=review_activity
    )

@app.route("/decide/<task_id>/<agent_name>", methods=["POST"])
def decide(task_id, agent_name):
    decision = request.form.get("decision")
    comment = request.form.get("comment", "")

    status = "approved_for_execution" if decision == "Approve" else "rejected"
    update_task_status(task_id, status)

    log_message(
        task_id=task_id, from_agent=f"Human_{agent_name}", to_agent=agent_name,
        msg_type="human_decision", content=f"{decision} issued: {comment}",
        constraints=["human_verification"], confidence=1.0, resolution_level=1
    )
    return redirect(url_for("agent_view", agent_name=agent_name))

@app.route("/publish/<task_id>/<agent_name>", methods=["POST"])
def publish(task_id, agent_name):
    task = get_task(task_id)

    # If this task carries a proposed file edit, this is the one and only place
    # it's ever written to disk — after approval, and only now, on publish.
    if task and task.get("file_target"):
        try:
            written_path = file_tools.apply_file_edit(task["file_target"], task["file_content"] or "")
            log_message(
                task_id=task_id, from_agent=f"Human_{agent_name}", to_agent="system",
                msg_type="file_written", content=f"Wrote {written_path}",
                constraints=["publish_gate", "file_edit_sandbox"], confidence=1.0
            )
        except PermissionError as e:
            log_message(
                task_id=task_id, from_agent=f"Human_{agent_name}", to_agent="system",
                msg_type="file_write_blocked", content=str(e),
                constraints=["publish_gate", "file_edit_sandbox"], confidence=1.0
            )
            update_task_status(task_id, "blocked")
            return f"<h3>❌ Blocked: {e}</h3><a href='/agent/{agent_name}'>Back</a>"

    update_task_status(task_id, "published")
    log_message(
        task_id=task_id, from_agent=f"Human_{agent_name}", to_agent="system",
        msg_type="published", content=f"Task {task_id} published/executed by {agent_name}'s human expert.",
        constraints=["publish_gate"], confidence=1.0, resolution_level=1
    )
    return redirect(url_for("agent_view", agent_name=agent_name))

@app.route("/request_file_edit", methods=["POST"])
def request_file_edit():
    relative_path = request.form.get("relative_path", "").strip()
    instruction = request.form.get("instruction", "").strip()
    if not relative_path or not instruction:
        return redirect(url_for("agent_view", agent_name="IT_Tech"))

    config = load_client_config(CLIENT_ID)
    task_id = f"file-{uuid.uuid4().hex[:8]}"
    result = agent_it.propose_file_edit(task_id, relative_path, instruction, config)

    if result.get("blocked"):
        return f"<h3>❌ {result['reason']}</h3><a href='/agent/IT_Tech'>Back</a>"
    return redirect(url_for("agent_view", agent_name="IT_Tech"))

@app.route("/chat/<agent_name>", methods=["POST"])
def chat(agent_name):
    message = request.form.get("message", "").strip()
    if not message:
        return redirect(url_for("agent_view", agent_name=agent_name))

    client_config = load_client_config(CLIENT_ID)
    biz_name = client_config["business_name"]
    agent_cfg = client_config["agents"].get(agent_name, {})
    can_propose = any(p in agent_cfg.get("permissions", []) for p in ("propose", "arbitrate"))

    log_message(
        task_id="chat", from_agent=f"Human_{agent_name}", to_agent=agent_name,
        msg_type="human_chat", content=message, constraints=["chat_thread"], confidence=1.0
    )

    # Bug #1 fix: pull real prior turns and actually send them back to the model.
    # Without this, every reply was generated from scratch with zero memory of
    # anything said before it.
    conn = sqlite3.connect(DB_FILE)
    history_rows = conn.execute(
        "SELECT type, content, from_agent FROM messages WHERE type IN ('human_chat','agent_chat_reply') "
        "AND (from_agent=? OR to_agent=?) ORDER BY id DESC LIMIT 10",
        (agent_name, agent_name)
    ).fetchall()
    conn.close()
    history_rows.reverse()
    history_messages = [
        {"role": "user" if row[0] == "human_chat" else "assistant", "content": row[1]}
        for row in history_rows
    ]

    # Bug #2 fix: a task-like request should actually become a task, not just get
    # talked about. Cheap one-word classification; defaults safely to plain chat
    # if it fails or if this agent can't propose anything anyway (Finance/IT_Tech).
    is_task = False
    if can_propose:
        try:
            verdict = qwen_request([
                {"role": "system", "content": (
                    "Reply with exactly one word: TASK if the message below is asking the "
                    "assistant to draft, create, do, or produce something actionable. "
                    "CHAT if it's a question, comment, or casual conversation."
                )},
                {"role": "user", "content": message}
            ])
            is_task = "TASK" in verdict.upper()
        except (ConnectionError, RuntimeError):
            is_task = False  # if classification fails, fall back to safe plain-chat behavior

    if is_task:
        from main import run_negotiation_pipeline
        import threading, uuid
        new_task_id = f"CHAT-{agent_name}-{uuid.uuid4().hex[:6]}"

        # run_negotiation_pipeline expects the task row to already exist — normally
        # the orchestrator creates it before ever calling this. Since chat is
        # bypassing the orchestrator, create it here first.
        conn = sqlite3.connect(DB_FILE)
        conn.execute(
            "INSERT OR REPLACE INTO tasks (task_id, assigned_to, description, depends_on, status) VALUES (?, ?, ?, ?, ?)",
            (new_task_id, agent_name, message, "[]", "assigned")
        )
        conn.commit()
        conn.close()

        threading.Thread(
            target=run_negotiation_pipeline,
            args=(new_task_id, agent_name, message, client_config),
            daemon=True
        ).start()
        reply = (
            f"On it — I've turned this into task {new_task_id} and it's going through the "
            f"same review process as everything else (Finance/IT will weigh in). You'll see "
            f"it appear in Pending Approvals or Review Activity in a moment."
        )
    else:
        client_id = client_config.get("client_id", "graub_ai")
        memory_block = business_memory.get_memory_context(client_id, domain=agent_name)
        system_prompt = (
            f"You are {agent_name}, a department agent at {biz_name}. "
            f"Reply briefly (2-3 sentences max), in a friendly, professional tone, "
            f"to this message from your human counterpart. You have no memory beyond "
            f"what's shown in this conversation and the business memory below — don't "
            f"claim to remember things that aren't there."
        )
        if memory_block:
            system_prompt = f"{system_prompt}\n\n{memory_block}"
        try:
            reply = qwen_request(
                [{"role": "system", "content": system_prompt}] + history_messages + [{"role": "user", "content": message}]
            )
        except Exception as e:
            reply = f"(Message received. Live reply unavailable right now: {e})"

    log_message(
        task_id="chat", from_agent=agent_name, to_agent=f"Human_{agent_name}",
        msg_type="agent_chat_reply", content=reply, constraints=["chat_thread"], confidence=1.0
    )
    return redirect(url_for("agent_view", agent_name=agent_name))

if __name__ == "__main__":
    # host 0.0.0.0 makes this reachable from other devices on the network (e.g. a
    # phone), which matters for "each expert reviews from their own device."
    app.run(host="0.0.0.0", port=5002, debug=False)
