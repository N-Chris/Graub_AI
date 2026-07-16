import sqlite3
import json
from datetime import datetime
from config import DB_FILE

def init_db():
    """Initializes a completely fresh relational message board and audit log schema."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Task Board Table Matrix
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            assigned_to TEXT,
            description TEXT,
            depends_on TEXT,
            status TEXT,
            file_target TEXT,
            file_content TEXT
        )
    ''')
    # Backfill columns for databases created before this schema version existed.
    existing_cols = [row[1] for row in cursor.execute("PRAGMA table_info(tasks)").fetchall()]
    if "file_target" not in existing_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN file_target TEXT")
    if "file_content" not in existing_cols:
        cursor.execute("ALTER TABLE tasks ADD COLUMN file_content TEXT")
    
    # Message / Communication Log Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            from_agent TEXT,
            to_agent TEXT,
            type TEXT,
            content TEXT,
            constraints_referenced TEXT,
            confidence REAL,
            timestamp TEXT,
            resolution_level INTEGER DEFAULT 1
        )
    ''')

    # Business Memory Table — durable, growing institutional knowledge per client.
    # 'observation' rows are cheap, automatic, one-line facts logged after every
    # resolved task (no LLM call). 'insight' rows are periodically distilled from
    # recent observations via a single Qwen call, replacing many raw rows with a
    # few compact, reusable lessons. 'prediction' rows are on-demand forward-looking
    # suggestions a human explicitly asked for. See business_memory.py.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS business_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT,
            domain TEXT,
            category TEXT,
            content TEXT,
            source_task_id TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def log_message(task_id, from_agent, to_agent, msg_type, content, constraints=None, confidence=1.0, resolution_level=1):
    """Securely writes interaction frames into our local relational audit log file."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO messages (task_id, from_agent, to_agent, type, content, constraints_referenced, confidence, timestamp, resolution_level)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (task_id, from_agent, str(to_agent), msg_type, content, json.dumps(constraints or []), confidence, datetime.utcnow().isoformat(), resolution_level))
    conn.commit()
    conn.close()

def update_task_status(task_id, status):
    """Modifies the active status tracking state inside our task blackboard schema."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = ? WHERE task_id = ?", (status, task_id))
    conn.commit()
    conn.close()

def create_file_edit_task(task_id, assigned_to, description, file_target, file_content):
    """Creates a task carrying a proposed file edit. Nothing is written to disk here —
    this only records the proposal on the task board. Writing only happens via
    file_tools.apply_file_edit, called from web_ui.py's /publish route after a human
    has approved and published the task."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO tasks (task_id, assigned_to, description, depends_on, status, file_target, file_content)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (task_id, assigned_to, description, json.dumps([]), "assigned", file_target, file_content))
    conn.commit()
    conn.close()

def get_task(task_id):
    """Fetches a single task row as a dict, or None if it doesn't exist."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    row = cursor.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None
