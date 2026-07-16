"""
Quick diagnostic for a stuck human_gate() polling loop.

Run this from the SAME terminal/folder you run main.py from, and separately
from wherever you run web_ui.py. If the printed database path is different
between the two, that's the bug: they're reading/writing two different
databases and can never see each other's updates, no matter what you click.

If the path matches in both, this also prints every task's current status —
so you can see directly whether the specific task_id main.py is waiting on
(e.g. "T2") has actually been changed away from 'assigned' / 'pending_human_review'.

Usage:
    python check_db.py
"""
import os
from database import DB_FILE

print("=" * 60)
print("Database file in use by THIS process:")
print(f"  {DB_FILE}")
print(f"  Exists: {os.path.exists(DB_FILE)}")
print("=" * 60)

if not os.path.exists(DB_FILE):
    print("No database file here yet — run main.py first.")
    raise SystemExit(0)

import sqlite3
conn = sqlite3.connect(DB_FILE)
rows = conn.execute("SELECT task_id, assigned_to, status FROM tasks ORDER BY task_id").fetchall()
conn.close()

if not rows:
    print("Database exists but has no tasks in it yet.")
else:
    print(f"\n{'Task ID':<18}{'Assigned To':<20}{'Status'}")
    print("-" * 60)
    waiting_on_human = []
    for task_id, assigned_to, status in rows:
        print(f"{task_id:<18}{assigned_to:<20}{status}")
        if status in ("assigned", "pending_human_review"):
            waiting_on_human.append((task_id, assigned_to))

    print("-" * 60)
    if waiting_on_human:
        print("\nStill waiting on a human decision:")
        for task_id, assigned_to in waiting_on_human:
            print(f"  -> {task_id} needs action at: http://127.0.0.1:5002/agent/{assigned_to}")
    else:
        print("\nEverything has a final status — nothing should be stuck polling right now.")
        print("If main.py is still stuck, it's very likely reading a DIFFERENT database")
        print("file than this one — compare the path printed above against what you get")
        print("running this same script from your main.py terminal/folder.")
