import time
import sqlite3
import os
from config import qwen_request, DB_FILE
from client_config import load_client_config

def init_baseline_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Baseline comparison log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS baseline_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal TEXT,
            output_content TEXT,
            execution_time_seconds REAL,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

def run_single_agent_baseline(goal: str, client_id: str = "graub_ai"):
    client_config = load_client_config(client_id)
    c = client_config["constraints"]
    biz_name = client_config["business_name"]

    print(f"\n[Baseline] Running Single-Agent execution for goal: {goal}")
    init_baseline_db()
    
    system_prompt = (
        f"You are a single monolithic AI business manager handling everything for {biz_name}. "
        "You must generate an all-inclusive operational breakdown covering Marketing, Sales, Finance, IT, "
        "Operations, HR, and Customer Service for the user's goal. "
        "CRITICAL HARD CONSTRAINTS TO COMPLY WITH:\n"
        f"1. Finance: Strict total budget ceiling of ${c['budget_ceiling']}.\n"
        f"2. IT/Tech: Maximum of {c['max_landing_pages']} landing pages / digital deployments.\n"
        f"3. Operations: Max {c['max_staff']} full-time staff, minimum {c['min_setup_days']} physical prep days.\n"
        f"4. Customer Service: Support reply SLA must be under {c['sla_hours']} hours.\n"
        "Output a massive paragraph breakdown covering your complete operational strategy. "
        "State every cost explicitly with a '$' prefix so amounts can be verified."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": goal}
    ]
    
    start_time = time.time()
    raw_response = qwen_request(messages, json_mode=False)
    elapsed_time = time.time() - start_time
    
    print(f"[Baseline] Monolithic Agent execution completed in {elapsed_time:.2f} seconds.")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO baseline_metrics (goal, output_content, execution_time_seconds, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (goal, raw_response, elapsed_time, time.asctime()))
    conn.commit()
    conn.close()
    return raw_response, elapsed_time

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Graub AI Single-Agent Baseline Runner")
    parser.add_argument("--client", type=str, default="graub_ai", help="ID slug of target client config file")
    parser.add_argument("--goal", type=str, default=None, help="Custom business goal. Uses the default demo goal if omitted.")
    args = parser.parse_args()

    test_goal = args.goal or "Incorporate a quick local pop-up store, hire 1 contractor, and list a campaign with $1500 operational cost."
    run_single_agent_baseline(test_goal, client_id=args.client)
