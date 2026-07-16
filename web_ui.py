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
    <p><a href="/">🏠 Home</a> | <a href="/setup">⚙️ Setup</a> | <a href="/dashboard">📊 Dashboard</a> | <a href="/insights">🧠 Insights</a></p>
    <p><b>🏢 Agent Portals:</b><br>
        {% for domain, cfg in agents.items() %}
            {% if cfg.enabled %}<a href="/agent/{{ domain }}">{{ cfg.custom_name }}</a>{% if not loop.last %} | {% endif %}{% endif %}
        {% endfor %}
    </p>
</div>
"""

STYLE = """
<style>
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f4f6f9; margin: 0; padding: 20px; }
    .container { max-width: 900px; margin: auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
    h1 { color: #1d1d1f; border-bottom: 2px solid #eaeaea; padding-bottom: 10px; }
    h3 { margin-top: 30px; }
    .task-card { border: 1px solid #e1e4e8; padding: 20px; margin: 15px 0; border-radius: 6px; background: #fafbfc; }
    .publish-card { border: 1px solid #b7e4c7; padding: 20px; margin: 15px 0; border-radius: 6px; background: #f0fdf4; }
    .file-card { border: 1px solid #ffd591; padding: 20px; margin: 15px 0; border-radius: 6px; background: #fffbe6; }
    .btn { padding: 10px 20px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; margin-right: 10px; }
    .btn-approve { background: #28a745; color: white; }
    .btn-reject { background: #dc3545; color: white; }
    .btn-publish { background: #0066cc; color: white; }
    .input-text { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ced4da; border-radius: 4px; box-sizing: border-box; }
    .nav-links { margin-top: 20px; font-size: 14px; background: #f0f2f5; padding: 12px; border-radius: 6px; }
    .chat-box { background: #e5ddd5; border-radius: 8px; padding: 15px; max-height: 300px; overflow-y: auto; }
    .bubble-human { background: #dcf8c6; padding: 8px 12px; border-radius: 8px; margin: 6px 0; max-width: 75%; margin-left: auto; }
    .bubble-agent { background: #ffffff; padding: 8px 12px; border-radius: 8px; margin: 6px 0; max-width: 75%; }
    .chat-form { display: flex; gap: 10px; margin-top: 10px; }
    .chat-form input { flex: 1; }
    .kpi-row { display: flex; gap: 20px; flex-wrap: wrap; }
    .kpi-card { flex: 1; min-width: 140px; border: 1px solid #e1e4e8; border-radius: 8px; padding: 16px; text-align: center; background: #fafbfc; }
    .kpi-num { font-size: 28px; font-weight: bold; color: #0066cc; }
    .kpi-label { color: #6a737d; font-size: 13px; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    th, td { text-align: left; padding: 8px; border-bottom: 1px solid #eee; font-size: 13px; }
    pre { background: #f6f8fa; padding: 10px; border-radius: 4px; overflow-x: auto; font-size: 12px; }
    .diff-old { background: #ffeef0; }
    .diff-new { background: #e6ffed; }
    .agent-row { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid #eee; }
    .agent-row input[type=text] { flex: 1; padding: 6px; }
</style>
"""

# ---------------------------------------------------------------------------
# HOME
# ---------------------------------------------------------------------------
HOME_HTML = STYLE + """
<div class="container">
    <h1>🧠 Graub AI — {{ business_name }}</h1>
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
SETUP_HTML = STYLE + """
<div class="container">
    <h1>⚙️ Setup — {{ config.business_name }}</h1>
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
DASHBOARD_HTML = STYLE + """
<div class="container">
    <h1>📊 Dashboard — {{ business_name }}</h1>
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

    <h3>Recent Activity</h3>
    <table>
        <tr><th>Time</th><th>From</th><th>To</th><th>Type</th></tr>
        {% for row in recent %}
        <tr><td>{{ row[0] }}</td><td>{{ row[1] }}</td><td>{{ row[2] }}</td><td>{{ row[3] }}</td></tr>
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
        "SELECT timestamp, from_agent, to_agent, type FROM messages ORDER BY id DESC LIMIT 20"
    ).fetchall()
    conn.close()

    recent_clean = [(str(r[0]).split("T")[-1][:8] if "T" in str(r[0]) else str(r[0])[:8], r[1], r[2], r[3]) for r in recent]

    return render_template_string(
        DASHBOARD_HTML, business_name=config["business_name"],
        total_tasks=total_tasks, total_messages=total_messages,
        negotiation_rounds=negotiation_rounds, escalations=escalations,
        per_agent=per_agent, recent=recent_clean, agents=config["agents"]
    )

# ---------------------------------------------------------------------------
# INSIGHTS — durable business memory + on-demand predictions
# ---------------------------------------------------------------------------
INSIGHTS_HTML = STYLE + """
<div class="container">
    <h1>🧠 Insights — {{ business_name }}</h1>
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

    <h3>🔮 Predictions</h3>
    <form method="post" action="/insights/predict">
        <button type="submit" class="btn btn-publish">Generate Predictions Now</button>
    </form>
    {% if predictions %}
        <div class="task-card"><pre style="white-space:pre-wrap;">{{ predictions }}</pre></div>
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
        predictions=None, agents=config["agents"]
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
        predictions=predictions, agents=config["agents"]
    )

# ---------------------------------------------------------------------------
# AGENT PORTAL — pending approvals, publish queue, file-edit requests, chat
# ---------------------------------------------------------------------------
AGENT_HTML = STYLE + """
<div class="container">
    <h1>🧠 {{ agent_name }} Departmental Portal</h1>

    <h3>🔍 Review Activity (verdicts this agent has issued)</h3>
    {% if review_activity %}
        <table>
            <tr><th>Task</th><th>Verdict</th><th>Reason</th><th>Time</th></tr>
            {% for row in review_activity %}
            <tr>
                <td>{{ row[0] }}</td>
                <td>{% if row[1] == 'critique' %}⚠️ Critique{% else %}✅ Accept{% endif %}</td>
                <td>{{ row[2] }}</td>
                <td>{{ row[3].split('T')[-1][:8] if 'T' in row[3] else row[3] }}</td>
            </tr>
            {% endfor %}
        </table>
        <p style="color:#6a737d; font-size:13px;">This agent reviews every proposal inline as part of the negotiation pipeline — it doesn't get its own approval queue the way proposing agents do. This is its actual activity log.</p>
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
        "SELECT task_id, type, content, timestamp FROM messages "
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

    log_message(
        task_id="chat", from_agent=f"Human_{agent_name}", to_agent=agent_name,
        msg_type="human_chat", content=message, constraints=["chat_thread"], confidence=1.0
    )

    try:
        reply = qwen_request([
            {"role": "system", "content": (
                f"You are {agent_name}, a department agent at {biz_name}. "
                f"Reply briefly (2-3 sentences max), in a friendly, professional tone, "
                f"to this message from your human counterpart."
            )},
            {"role": "user", "content": message}
        ])
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
