"""
Seeds a realistic demo dataset in one command: runs several real scenarios through
the actual pipeline (uses your real Qwen Cloud key — this costs real API calls),
auto-approves most of them so the Dashboard/Insights/Knowledge Base have genuine
history to show, and deliberately leaves ONE task pending so you have something
live to approve on camera instead of starting from a blank slate.

Usage:
    python seed_demo.py --client graub_ai
"""
import argparse
import threading
import time
import sqlite3

from client_config import load_client_config
from database import init_db, DB_FILE
from orchestrator import orchestrator_decompose
from main import run_negotiation_pipeline

DEMO_GOALS = [
    "Launch a small local pop-up promotion with a $1200 budget.",
    "Hire one part-time customer support contractor.",
    "Draft a customer retention email campaign, budget $900.",
]


def auto_approve_loop(stop_event, leave_pending):
    """Publishes any task that reaches pending_human_review, except the one
    task_id we're deliberately leaving open for a live demo."""
    while not stop_event.is_set():
        time.sleep(1)
        conn = sqlite3.connect(DB_FILE)
        rows = conn.execute("SELECT task_id FROM tasks WHERE status='pending_human_review'").fetchall()
        for (task_id,) in rows:
            if task_id == leave_pending["id"]:
                continue
            conn.execute("UPDATE tasks SET status='published' WHERE task_id=?", (task_id,))
        conn.commit()
        conn.close()


def main(client_id):
    config = load_client_config(client_id)
    init_db()

    leave_pending = {"id": None}
    stop_event = threading.Event()
    approver = threading.Thread(target=auto_approve_loop, args=(stop_event, leave_pending), daemon=True)
    approver.start()

    all_tasks = []
    for i, goal in enumerate(DEMO_GOALS):
        print(f"\n### Decomposing scenario {i + 1}/{len(DEMO_GOALS)}: {goal}")
        subtasks = orchestrator_decompose(goal, config)
        executable = [t for t in subtasks if t["domain"] not in ["Finance", "IT_Tech"]]
        all_tasks.extend(executable)

    for idx, task in enumerate(all_tasks):
        is_last = idx == len(all_tasks) - 1
        print(f"\n### Running task {idx + 1}/{len(all_tasks)}: {task['task_id']} ({task['domain']})")
        if is_last:
            leave_pending["id"] = task["task_id"]
        th = threading.Thread(
            target=run_negotiation_pipeline,
            args=(task["task_id"], task["domain"], task["description"], config),
            daemon=True
        )
        th.start()
        if is_last:
            time.sleep(5)  # give it time to actually reach pending_human_review before we exit
        else:
            th.join(timeout=90)

    stop_event.set()
    print("\n" + "=" * 60)
    print(f"Done. Task {leave_pending['id']} is deliberately left pending for a live demo.")
    print("Check /dashboard to confirm, then approve + publish it on camera.")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed a realistic demo dataset")
    parser.add_argument("--client", default="graub_ai")
    args = parser.parse_args()
    main(args.client)
