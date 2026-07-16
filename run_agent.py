"""
Run any single domain agent standalone, as its own independent assistant — proves
each Graub AI agent is a wholesome, self-contained assistant that can help a business
with day-to-day work in its domain, not just a cog that only functions inside the
full multi-agent negotiation pipeline.

Usage:
    python run_agent.py --client graub_ai --agent Finance --task "Review this ad spend: $2000 on Google Ads for a spring sale"
    python run_agent.py --client graub_ai --agent Marketing_Sales --task "Draft a launch announcement for our new product line"
    python run_agent.py --client graub_ai --agent HR --task "Draft a job posting for a part-time customer support role"

Each agent still respects its configured permissions (client_configs/<client>.json) —
an agent without the relevant permission will refuse, same as it would inside the
full pipeline.
"""
import argparse
import sys

from client_config import load_client_config
from database import init_db

import agent_marketing_sales
import agent_finance
import agent_it
import agent_operations
import agent_hr
import agent_customer_service
import agent_leadership

# mode "generate": agent drafts something new from a task description
# mode "review": agent audits a proposal/piece of text you hand it
# mode "execute": agent (base-class agents) drafts/reviews depending on its own permissions
AGENT_MODULES = {
    "Marketing_Sales": ("generate", agent_marketing_sales),
    "Finance": ("review", agent_finance),
    "IT_Tech": ("review", agent_it),
    "Operations": ("execute", agent_operations),
    "HR": ("execute", agent_hr),
    "Customer_Service": ("execute", agent_customer_service),
    "Leadership": ("execute", agent_leadership),
}


def run_single_agent(agent_key: str, task_text: str, client_config: dict):
    if agent_key not in AGENT_MODULES:
        print(f"Unknown agent '{agent_key}'. Choose from: {list(AGENT_MODULES.keys())}")
        sys.exit(1)

    agent_cfg = client_config["agents"].get(agent_key)
    if not agent_cfg or not agent_cfg.get("enabled", True):
        print(f"'{agent_key}' is not enabled for this client's current subscription tier.")
        sys.exit(1)

    mode, module = AGENT_MODULES[agent_key]
    task_id = f"standalone-{agent_key}"

    print(f"\n=== Running {agent_cfg['custom_name']} ({agent_key}) standalone ===\n")

    if mode == "generate":
        result = module.generate_proposal(task_id, task_text, client_config)
    elif mode == "review":
        result = module.review_proposal(task_id, task_text, client_config)
    else:  # execute
        result = module.agent.execute_proposal(task_id, task_text, client_config)

    print("\n--- AGENT OUTPUT ---\n")
    print(result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a single Graub AI agent standalone, as its own assistant.")
    parser.add_argument("--client", type=str, default="graub_ai", help="ID slug of target client config file")
    parser.add_argument("--agent", type=str, required=True, choices=list(AGENT_MODULES.keys()))
    parser.add_argument("--task", type=str, required=True, help="The task, question, or content for the agent to work on")
    args = parser.parse_args()

    config = load_client_config(args.client)
    init_db()
    run_single_agent(args.agent, args.task, config)
