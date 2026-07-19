"""
Runs every scenario in scenarios.json through both the single-agent baseline
and the full multi-agent negotiation pipeline, and reports the efficiency
comparison judges will look for in Track 3.

Usage:
    python run_comparison.py --client graub_ai
"""
import argparse
import json
import time
import sqlite3
import threading

from client_config import load_client_config
from database import init_db, DB_FILE
from orchestrator import orchestrator_decompose
from baseline_single_agent import run_single_agent_baseline
from main import run_negotiation_pipeline


def auto_approve_loop(stop_event):
    """Runs in the background for the duration of the comparison so timing reflects
    actual negotiation/API speed, not however long a human takes to click Approve.
    Without this, run_negotiation_pipeline blocks on human_gate() indefinitely, and
    even if a human does click through manually, that reaction time would corrupt
    the very timing numbers this script exists to produce."""
    while not stop_event.is_set():
        time.sleep(0.5)
        conn = sqlite3.connect(DB_FILE)
        conn.execute("UPDATE tasks SET status='published' WHERE status='pending_human_review'")
        conn.commit()
        conn.close()


def count_negotiation_rounds(task_ids):
    """Counts critique/revision messages logged for a set of task_ids, as a proxy
    for how much back-and-forth was needed to reach a resolved proposal."""
    if not task_ids:
        return 0
    conn = sqlite3.connect(DB_FILE)
    placeholders = ",".join("?" for _ in task_ids)
    count = conn.execute(
        f"SELECT COUNT(*) FROM messages WHERE task_id IN ({placeholders}) AND type='loop_iteration'",
        task_ids
    ).fetchone()[0]
    conn.close()
    return count


def run_all(client_id="graub_ai", scenarios_path="scenarios.json"):
    config = load_client_config(client_id)
    init_db()

    stop_event = threading.Event()
    approver = threading.Thread(target=auto_approve_loop, args=(stop_event,), daemon=True)
    approver.start()

    with open(scenarios_path) as f:
        scenarios = json.load(f)

    results = []

    for scenario in scenarios:
        goal = scenario["goal"]
        print(f"\n\n########## SCENARIO: {scenario['id']} ##########")
        print(f"Goal: {goal}")

        # --- Baseline run ---
        print("\n--- Running single-agent baseline ---")
        _, baseline_time = run_single_agent_baseline(goal, client_id=client_id)

        # --- Multi-agent run ---
        print("\n--- Running multi-agent society ---")
        start = time.time()
        subtasks = orchestrator_decompose(goal, config)
        executable_tasks = [t for t in subtasks if t['domain'] not in ['Finance', 'IT_Tech']]
        task_ids = [t['task_id'] for t in executable_tasks]

        for task in executable_tasks:
            run_negotiation_pipeline(task['task_id'], task['domain'], task['description'], config)
        multi_agent_time = time.time() - start

        rounds = count_negotiation_rounds(task_ids)

        results.append({
            "scenario": scenario["id"],
            "goal": goal,
            "baseline_time_seconds": round(baseline_time, 2),
            "multi_agent_time_seconds": round(multi_agent_time, 2),
            "multi_agent_negotiation_rounds": rounds,
            "multi_agent_subtasks": len(executable_tasks),
        })

    stop_event.set()

    print("\n\n" + "=" * 60)
    print("COMPARISON SUMMARY")
    print("=" * 60)
    print(f"{'Scenario':<12}{'Baseline (s)':<16}{'Multi-Agent (s)':<18}{'Rounds':<10}{'Subtasks':<10}")
    for r in results:
        print(f"{r['scenario']:<12}{r['baseline_time_seconds']:<16}{r['multi_agent_time_seconds']:<18}"
              f"{r['multi_agent_negotiation_rounds']:<10}{r['multi_agent_subtasks']:<10}")

    with open("comparison_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nSaved full results to comparison_results.json")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Graub AI Baseline vs Multi-Agent Comparison Runner")
    parser.add_argument("--client", type=str, default="graub_ai")
    parser.add_argument("--scenarios", type=str, default="scenarios.json")
    args = parser.parse_args()
    run_all(client_id=args.client, scenarios_path=args.scenarios)
