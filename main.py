import argparse
import sys
import os
import json
from client_config import load_client_config
from database import init_db, log_message, update_task_status
from orchestrator import orchestrator_decompose
import business_memory

# Core agent engines
import agent_marketing_sales
import agent_finance
import agent_it

# Base-derived agents
import agent_operations
import agent_hr
import agent_customer_service
import agent_leadership

MAX_ROUNDS = 2

import time
import sqlite3
from database import init_db, log_message, update_task_status, DB_FILE

def human_gate(task_id, proposal_content, is_escalated=False, resolution_level=1):
    print("\n" + "="*50)
    if is_escalated:
        print(f"🚨 ALERT: CONFLICT ESCALATION FOR TASK {task_id} 🚨")
        # Bounded negotiation failed to resolve within MAX_ROUNDS. Mirror this task
        # into the Leadership queue so a human authority can arbitrate, in addition
        # to the originating domain expert's own review.
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        escalation_id = f"{task_id}-ESC"
        cursor.execute('''
            INSERT OR REPLACE INTO tasks (task_id, assigned_to, description, depends_on, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            escalation_id, "Leadership",
            f"ARBITRATION NEEDED for {task_id}: Finance/IT and the originating agent could not "
            f"reach agreement within {MAX_ROUNDS} negotiation rounds.\n\nUnresolved proposal:\n{proposal_content}",
            json.dumps([task_id]), "assigned"
        ))
        conn.commit()
        conn.close()
        log_message(
            task_id=task_id, from_agent="Orchestrator", to_agent="Leadership",
            msg_type="conflict_flag",
            content=f"Escalated to Leadership for arbitration after {MAX_ROUNDS} unresolved negotiation rounds.",
            constraints=["escalation_chain"], confidence=0.7, resolution_level=2
        )
    else:
        print(f"⏳ PENDING HUMAN EXPERT AUTHENTICATION FOR TASK {task_id} (Level {resolution_level}) ⏳")
    print("="*50)
    print(" -> Forwarding proposal layout package straight to the web portal...")
    
    # 1. Update task board status to alert the web dashboard panel
    update_task_status(task_id, "pending_human_review")
    
    # 2. Automated Polling Thread: Sleep until the user submits a verdict via web_ui.py
    print(" -> System sleeping. Waiting for human input on http://127.0.0.1:5002 ...")
    
    while True:
        time.sleep(3) # Query the database state every 3 seconds
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        current_status = cursor.execute("SELECT status FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        
        # Check if the text matches a decision submitted via the web dashboard fields
        if current_status and current_status[0] not in ["assigned", "pending_human_review"]:
            final_verdict = current_status[0]
            print(f"\n[System] Human verdict intercepted via Web UI! New Status: {final_verdict.upper()}")
            conn.close()
            break
        conn.close()

def run_negotiation_pipeline(task_id, assigned_domain, description, client_config):
    """Executes multi-tenant bounded negotiation checking runtime constraints and permissions."""
    agent_cfg = client_config["agents"].get(assigned_domain, {})
    custom_name = agent_cfg.get("custom_name", assigned_domain)
    permissions = agent_cfg.get("permissions", [])
    
    print(f"\n=== PROCESSING TASK: {task_id} FOR DOMAIN: {assigned_domain} ({custom_name}) ===")
    
    # STRICT DAY 1 SECURITY CHECK: Verify execution clearances
    if "propose" not in permissions:
        print(f" ❌ Security Exception: Agent '{custom_name}' lacks 'propose' clearance parameters.")
        return

    # Dispatch task to appropriate domain layout engine passing runtime settings
    if assigned_domain == "Marketing_Sales":
        proposal = agent_marketing_sales.generate_proposal(task_id, description, client_config)
    elif assigned_domain == "Operations":
        proposal = agent_operations.agent.execute_proposal(task_id, description, client_config)
    elif assigned_domain == "HR":
        proposal = agent_hr.agent.execute_proposal(task_id, description, client_config)
    elif assigned_domain == "Customer_Service":
        proposal = agent_customer_service.agent.execute_proposal(task_id, description, client_config)
    elif assigned_domain == "Leadership":
        proposal = agent_leadership.agent.execute_proposal(task_id, description, client_config)
    else:
        return 

    # Initialize negotiation tracking variables
    resolved = False
    negotiation_round = 0

    # Bounded negotiation loop: Finance and IT audit every proposal in parallel,
    # regardless of which domain generated it, since budget and technical feasibility
    # are cross-cutting hard constraints. Capped at MAX_ROUNDS per the protocol.
    while negotiation_round < MAX_ROUNDS and not resolved:
        finance_result = agent_finance.review_proposal(task_id, proposal, client_config)
        it_result = agent_it.review_proposal(task_id, proposal, client_config)

        critiques = []
        if finance_result["verdict"] == "critique":
            critiques.append(f"[Finance] {finance_result['reason']}")
        if it_result["verdict"] == "critique":
            critiques.append(f"[IT_Tech] {it_result['reason']}")

        if not critiques:
            resolved = True
            print(f" ✅ Round {negotiation_round + 1}: Finance and IT both ACCEPT. Proposal resolved.")
            break

        combined_critique = "\n".join(critiques)
        print(f" ⚠️ Round {negotiation_round + 1}: Critique received:\n{combined_critique}")

        # Route the critique back to the originating agent to revise
        if assigned_domain == "Marketing_Sales":
            proposal = agent_marketing_sales.revise_proposal(task_id, proposal, combined_critique, client_config)
        elif assigned_domain in ["Operations", "HR", "Customer_Service", "Leadership"]:
            agent_obj = getattr(sys.modules[f"agent_{assigned_domain.lower()}"], "agent")
            proposal = agent_obj.adapt_proposal(task_id, proposal, combined_critique, client_config)

        # Log the round outcome to the ledger
        log_message(
            task_id=task_id,
            from_agent="Orchestrator",
            to_agent=assigned_domain,
            msg_type="loop_iteration",
            content=f"Negotiation round {negotiation_round + 1} completed. Critiques: {combined_critique}",
            constraints=["multi_stage_alignment"],
            confidence=0.8,
            resolution_level=1
        )

        negotiation_round += 1

    # Route to the human gate. If not resolved within MAX_ROUNDS, this also mirrors
    # the task into the Leadership queue for arbitration (see human_gate).
    human_gate(task_id, proposal, is_escalated=not resolved, resolution_level=(1 if resolved else 2))

    # Learning step: turn this resolved task into a durable memory observation, and
    # periodically distill recent observations into a few compact insights. Both are
    # best-effort — a memory hiccup should never take down the actual pipeline.
    client_id = client_config.get("client_id", "graub_ai")
    try:
        conn = sqlite3.connect(DB_FILE)
        final_status = conn.execute("SELECT status FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        conn.close()
        if final_status:
            business_memory.record_task_outcome(client_id, task_id, assigned_domain, description, final_status[0])
            business_memory.consolidate_if_needed(client_id)
    except Exception as e:
        print(f" ⚠️ Business memory update skipped (non-fatal): {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Graub AI Multi-Tenant Coordinator Engine")
    parser.add_argument("--client", type=str, default="graub_ai", help="ID slug of target client config file")
    parser.add_argument("--goal", type=str, default=None, help="Custom business goal to decompose. Uses a default demo goal if omitted.")
    parser.add_argument("--max-tasks", type=int, default=None, help="Cap the number of subtasks processed (default: process all assigned subtasks).")
    args = parser.parse_args()
    
    # Load dynamic tenant configuration profiles from disk
    config = load_client_config(args.client)
    
    # Initialize fresh runtime ledger tables
    init_db()
    
    goal_scenario = args.goal or "Incorporate a quick local pop-up store, hire 1 contractor, and list a campaign with $1500 operational cost."
    subtasks = orchestrator_decompose(goal_scenario, config)
    
    # Filter for active functional domain task assignments. Finance/IT_Tech are reviewers,
    # not proposers, so they never receive a directly assigned task of their own.
    executable_tasks = [t for t in subtasks if t['domain'] not in ['Finance', 'IT_Tech']]
    
    tasks_to_run = executable_tasks[:args.max_tasks] if args.max_tasks else executable_tasks
    for task in tasks_to_run:
        run_negotiation_pipeline(task['task_id'], task['domain'], task['description'], config)
