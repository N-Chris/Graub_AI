"""
A minimal JSON REST API exposing each agent as an independently callable service.
This is deliberately separate from web_ui.py (which serves humans HTML pages) —
this is the surface other software would integrate against in a real SaaS deployment.

Run alongside web_ui.py on a different port:
    python api.py

Example:
    curl http://localhost:5003/api/v1/agents?client_id=graub_ai

    curl -X POST http://localhost:5003/api/v1/agents/Finance/task \\
        -H "Content-Type: application/json" \\
        -d '{"client_id": "graub_ai", "description": "Ad spend proposal: $2000 on Google Ads."}'
"""
import time
from flask import Flask, jsonify, request
from client_config import load_client_config
from database import init_db

import agent_marketing_sales
import agent_finance
import agent_it
import agent_operations
import agent_hr
import agent_customer_service
import agent_leadership

app = Flask(__name__)

AGENT_DESCRIPTIONS = {
    "Marketing_Sales": "Drafts campaign copy, pricing proposals, and promo plans.",
    "Finance": "Audits proposals against your budget ceiling before they reach you.",
    "IT_Tech": "Reviews technical/deployment feasibility; can also draft sandboxed file edits.",
    "Operations": "Drafts staffing and logistics plans within your real capacity limits.",
    "HR": "Handles first-pass hiring, scheduling, and policy drafts.",
    "Customer_Service": "Designs support workflows that respect your SLA.",
    "Leadership": "Arbitrates when other agents disagree and can't resolve it themselves.",
}

# NOTE: intentionally not importing run_agent.py's dispatch table here — that one
# calls sys.exit() on error paths, which is correct for a CLI script but would kill
# a Flask worker process. This is a small, deliberately separate dispatch instead.
# mode "generate": drafts something new. "review": audits text handed to it.
# "execute": base-class agents, which draft or review depending on their own permissions.
AGENT_MODULES = {
    "Marketing_Sales": ("generate", agent_marketing_sales),
    "Finance": ("review", agent_finance),
    "IT_Tech": ("review", agent_it),
    "Operations": ("execute", agent_operations),
    "HR": ("execute", agent_hr),
    "Customer_Service": ("execute", agent_customer_service),
    "Leadership": ("execute", agent_leadership),
}


@app.route("/api/v1/agents")
def list_agents():
    client_id = request.args.get("client_id", "graub_ai")
    config = load_client_config(client_id)
    roster = [
        {
            "domain": domain,
            "custom_name": cfg["custom_name"],
            "enabled": cfg.get("enabled", True),
            "permissions": cfg["permissions"],
            "description": AGENT_DESCRIPTIONS.get(domain, ""),
        }
        for domain, cfg in config["agents"].items()
    ]
    return jsonify({"business_name": config["business_name"], "subscription_tier": config.get("subscription_tier"), "agents": roster})


@app.route("/api/v1/agents/<domain>/task", methods=["POST"])
def run_agent_task(domain):
    body = request.get_json(force=True, silent=True) or {}
    client_id = body.get("client_id", "graub_ai")
    description = body.get("description")

    if not description:
        return jsonify({"error": "Missing required field 'description'"}), 400
    if domain not in AGENT_MODULES:
        return jsonify({"error": f"Unknown agent domain '{domain}'. Valid: {list(AGENT_MODULES.keys())}"}), 404

    config = load_client_config(client_id)
    agent_cfg = config["agents"].get(domain)
    if not agent_cfg or not agent_cfg.get("enabled", True):
        return jsonify({"error": f"Agent '{domain}' is not enabled for client '{client_id}'"}), 403

    init_db()
    task_id = f"API-{domain}-{int(time.time())}"
    mode, module = AGENT_MODULES[domain]

    try:
        if mode == "generate":
            result = module.generate_proposal(task_id, description, config)
        elif mode == "review":
            result = module.review_proposal(task_id, description, config)
        else:
            result = module.agent.execute_proposal(task_id, description, config)
    except (ConnectionError, RuntimeError) as e:
        return jsonify({"error": f"Upstream Qwen Cloud error: {e}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"task_id": task_id, "domain": domain, "agent_name": agent_cfg["custom_name"], "result": result})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003, debug=False)
