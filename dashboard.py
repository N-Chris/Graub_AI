import tkinter as tk
from tkinter import ttk
import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_society.db")
CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "client_configs")

def get_available_clients():
    if not os.path.exists(CONFIG_DIR):
        return ["graub_ai"]
    files = [f.replace(".json", "") for f in os.listdir(CONFIG_DIR) if f.endswith(".json")]
    return files if files else ["graub_ai"]

def refresh_data():
    # Clear visual tables before refreshing to prevent duplicate UI rows
    for item in task_tree.get_children(): task_tree.delete(item)
    for item in tree_lvl1.get_children(): tree_lvl1.delete(item)
    for item in tree_lvl2.get_children(): tree_lvl2.delete(item)
    for item in tree_lvl3.get_children(): tree_lvl3.delete(item)
    
    selected_client = client_selector.get()
    lbl_profile.config(text=f"Active Profile: {selected_client.upper()}")
    
    if not os.path.exists(DB_FILE):
        lbl_status.config(text="Status: agent_society.db ledger file missing! Run main.py first.", fg="orange")
        root.after(2000, refresh_data)
        return
        
    lbl_status.config(text="Status: Connected Live to Multi-Tenant Ledger", fg="darkgreen")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 1. Populate the Live Task Board View
    try:
        cursor.execute("SELECT task_id, assigned_to, status FROM tasks")
        for row in cursor.fetchall():
            task_tree.insert("", "end", values=row)
    except: pass
    
    # 2. Populate Metrics Summary Cards safely
    try:
        table_check = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='baseline_metrics'").fetchone()
        if table_check:
            base = cursor.execute("SELECT execution_time_seconds FROM baseline_metrics ORDER BY id DESC LIMIT 1").fetchone()
            lbl_latency.config(text=f"{base[0]:.2f}s" if base else "0.00s")
        else:
            lbl_latency.config(text="Pending")
            
        msgs = cursor.execute("SELECT COUNT(*) FROM messages").fetchone()
        lbl_msg.config(text=str(msgs[0]) if msgs else "0")
    except: pass
    
    # 3. Separate Logs Dynamically by Resolution Level Parameters
    try:
        cursor.execute("SELECT timestamp, from_agent, to_agent, type, content, resolution_level FROM messages ORDER BY id DESC")
        for row in cursor.fetchall():
            clean_time = row[0].split("T")[-1][:8] if "T" in row[0] else row[0][:8]
            display_values = (clean_time, row[1], row[2], str(row[3]).upper(), row[4][:60] + "...")
            
            lvl = row[5]
            if lvl == 1:
                tree_lvl1.insert("", "end", values=display_values)
            elif lvl == 2:
                tree_lvl2.insert("", "end", values=display_values)
            elif lvl == 3:
                tree_lvl3.insert("", "end", values=display_values)
    except Exception as e:
        print(f"UI Filter Populating Error: {e}")
        
    conn.close()
    root.after(2000, refresh_data)

# Build native desktop OS window frame
root = tk.Tk()
root.title("Graub AI - Multi-Tenant Society Console")
root.geometry("1100x700")
root.configure(bg="#f5f5f7")

# Title Block Banner
tk.Label(root, text="🧠 Graub AI: Multi-Tenant Console", font=("Arial", 16, "bold"), bg="#f5f5f7", fg="#1d1d1f").pack(pady=5)
lbl_status = tk.Label(root, text="Status: Initializing...", font=("Arial", 10, "italic"), bg="#f5f5f7")
lbl_status.pack()

# Workspace Dropdown Selector Block
selector_frame = tk.Frame(root, bg="#f5f5f7")
selector_frame.pack(pady=5)
client_selector = ttk.Combobox(selector_frame, values=get_available_clients(), state="readonly", width=20)
client_selector.set(get_available_clients()[0])
client_selector.pack(side="left", padx=5)
lbl_profile = tk.Label(root, text="Active Profile: ...", font=("Arial", 10, "bold"), bg="#f5f5f7", fg="#515154")
lbl_profile.pack()

# Metrics Summary Panels
metric_frame = tk.Frame(root, bg="#f5f5f7")
metric_frame.pack(pady=5)
fa, fb = tk.Frame(metric_frame, bd=1, relief="solid", padx=20, pady=5, bg="white"), tk.Frame(metric_frame, bd=1, relief="solid", padx=20, pady=5, bg="white")
fa.pack(side="left", padx=10)
fb.pack(side="left", padx=10)
tk.Label(fa, text="Single-Agent Latency", font=("Arial", 9), bg="white", fg="#86868b").pack()
lbl_latency = tk.Label(fa, text="Pending", font=("Arial", 12, "bold"), bg="white", fg="#0066cc")
lbl_latency.pack()
tk.Label(fb, text="Society Messages Logged", font=("Arial", 9), bg="white", fg="#86868b").pack()
lbl_msg = tk.Label(fb, text="0", font=("Arial", 12, "bold"), bg="white", fg="#242426")
lbl_msg.pack()

# Live Blackboard Matrix Table View
tk.Label(root, text="📋 Live Multi-Agent Task Board Matrix:", font=("Arial", 11, "bold"), bg="#f5f5f7").pack(anchor="w", padx=15)
task_tree = ttk.Treeview(root, columns=("ID", "Domain Agent", "Status"), show="headings", height=4)
for col in ("ID", "Domain Agent", "Status"):
    task_tree.heading(col, text=col)
    task_tree.column(col, width=200, anchor="center")
task_tree.pack(fill="x", padx=15, pady=2)

# --- LEVEL-FILTERED TABS ARCHITECTURE ---
tk.Label(root, text="💬 Audit Logs Filtered By Conflict Intensity Level:", font=("Arial", 11, "bold"), bg="#f5f5f7").pack(anchor="w", padx=15, pady=5)
notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True, padx=15, pady=5)

# Setup 3 clean frames for our tabs
tab1 = ttk.Frame(notebook)
tab2 = ttk.Frame(notebook)
tab3 = ttk.Frame(notebook)

notebook.add(tab1, text=" 🟢 Level 1: Baseline Consensus ")
notebook.add(tab2, text=" 🟡 Level 2: Multi-Round Friction ")
notebook.add(tab3, text=" 🔴 Level 3: Governance Escalations ")

# Helper to build table frames inside each notebook view
def build_tree_layout(parent_frame):
    tree = ttk.Treeview(parent_frame, columns=("Time", "From", "To", "Verdict", "Summary Snippet"), show="headings")
    for col in ("Time", "From", "To", "Verdict", "Summary Snippet"):
        tree.heading(col, text=col)
    tree.column("Time", width=80, anchor="center")
    tree.column("From", width=120, anchor="center")
    tree.column("To", width=120, anchor="center")
    tree.column("Verdict", width=100, anchor="center")
    tree.column("Summary Snippet", width=450, anchor="w")
    tree.pack(fill="both", expand=True)
    return tree

tree_lvl1 = build_tree_layout(tab1)
tree_lvl2 = build_tree_layout(tab2)
tree_lvl3 = build_tree_layout(tab3)

refresh_data()
root.mainloop()
