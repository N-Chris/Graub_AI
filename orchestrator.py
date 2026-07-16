import sqlite3
import json
from config import qwen_request, DB_FILE

def orchestrator_decompose(goal: str, client_config: dict):
    biz_name = client_config["business_name"]
    print(f"\n[Orchestrator] Decomposing strategic goal for {biz_name}: {goal}")
    
    # Dynamically extract runtime constraints to pass into the prompt context window
    constraints = client_config["constraints"]
    # Only domains that can actually PROPOSE or ARBITRATE something are assignable.
    # Finance and IT_Tech are reviewers — they audit every proposal inline as part of
    # the negotiation loop (see main.py), they never receive a task of their own.
    # Offering them here let the model occasionally assign a task straight to Finance/
    # IT_Tech, which then sat in their portal as an orphaned "pending approval" that
    # never went through review at all — confusing and wrong. This is the actual fix.
    active_domains = [
        domain for domain, data in client_config["agents"].items()
        if data.get("enabled", True) and any(p in data.get("permissions", []) for p in ("propose", "arbitrate"))
    ]
    domains_str = ", ".join([f"'{d}'" for d in active_domains])
    
    system_prompt = (
        f"You are the Orchestrator (Chief of Staff) of {biz_name}, an elite multi-agent enterprise. "
        f"Decompose the user's strategic goal into granular, operational subtasks. "
        f"You can ONLY assign tasks to these specific internal domain keys: {domains_str}. "
        f"CURRENT SME OPERATIONAL CONSTRAINT CRITERIA:\n"
        f"- Total Budget Ceiling: ${constraints.get('budget_ceiling')}\n"
        f"- Max Digital Deployments: {constraints.get('max_landing_pages')} pages\n"
        f"- Max Capacity Limit: {constraints.get('max_staff')} staff members\n"
        f"- Support Response Window: {constraints.get('sla_hours')} hours\n"
        f"Output an absolute raw JSON object matching this structure exactly, with no conversational fluff:\n"
        f'{{"subtasks": [{{"task_id": "T1", "domain": "Marketing_Sales", "description": "...", "depends_on": []}}]}}'
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": goal}
    ]
    
    try:
        raw_content = qwen_request(messages, json_mode=True)
        data = json.loads(raw_content)
    except (ConnectionError, RuntimeError) as e:
        # A genuine API/network failure, not a formatting hiccup. Continuing here would
        # silently run the rest of the pipeline on fabricated fallback content and look
        # like a successful demo when nothing actually worked. Stop loudly instead.
        print(f"❌ Orchestrator cannot reach Qwen Cloud: {e}")
        raise
    except json.JSONDecodeError as e:
        print(f"⚠️ Orchestrator Parsing Exception: Model returned malformed JSON ({e}). Using fallback single-task path.")
        data = {
            "subtasks": [
                {
                    "task_id": "T1", 
                    "domain": "Marketing_Sales", 
                    "description": f"Analyze and prepare initial launch roadmap for goal: {goal}", 
                    "depends_on": []
                }
            ]
        }
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    for subtask in data.get("subtasks", []):
        target_domain = subtask['domain'] if subtask['domain'] in active_domains else "Marketing_Sales"
        
        cursor.execute('''
            INSERT OR REPLACE INTO tasks (task_id, assigned_to, description, depends_on, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (subtask['task_id'], target_domain, subtask['description'], json.dumps(subtask.get('depends_on', [])), 'assigned'))
        print(f" -> Assigned {subtask['task_id']} to {target_domain}: {subtask['description']}")
        
    conn.commit()
    conn.close()
    return data.get("subtasks", [])
