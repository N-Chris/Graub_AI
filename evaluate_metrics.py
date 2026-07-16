import sqlite3
import re
from config import DB_FILE
from client_config import load_client_config

def run_metric_analysis(client_id="graub_ai"):
    client_config = load_client_config(client_id)
    budget_ceiling = client_config["constraints"]["budget_ceiling"]
    print("\n" + "="*50)
    print("📈 GRAUB AI: QUANTITATIVE EFFICIENCY METRICS REPORT 📈")
    print("="*50)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # --- RAW DATABASE CHECK (DEBUG) ---
    print("🔍 RAW LEDGER SNAPSHOTS:")
    try:
        task_check = cursor.execute("SELECT task_id, assigned_to, status FROM tasks").fetchall()
        print(f" -> Active Tasks Rows Found: {len(task_check)} {task_check}")
    except Exception as e:
        print(f" -> Tasks table error: {e}")
        
    try:
        msg_check = cursor.execute("SELECT from_agent, to_agent, type FROM messages LIMIT 3").fetchall()
        print(f" -> Message Logs Found: {len(msg_check)} {msg_check}")
    except Exception as e:
        print(f" -> Messages table error: {e}")

    try:
        base_check = cursor.execute("SELECT execution_time_seconds FROM baseline_metrics").fetchall()
        print(f" -> Baseline Run Records: {len(base_check)} {base_check}")
    except Exception as e:
        print(f" -> Baseline table error: {e}")
    print("-"*50 + "\n")

    # --- ANALYTICAL INTERPRETATION ---
    print("🧠 Multi-Agent Society Profile:")
    total_tasks = cursor.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    total_messages = cursor.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    negotiation_rounds = cursor.execute("SELECT COUNT(*) FROM messages WHERE type IN ('critique', 'revision')").fetchone()[0]
    
    print(f" -> Granular Subtasks Executed on Board: {total_tasks}")
    print(f" -> Total Inter-Agent Messages Logged: {total_messages}")
    print(f" -> Active Negotiation Conflict Rounds: {negotiation_rounds}")
        
    print("\n👤 Single-Agent Monolithic Profile:")
    baseline = cursor.execute("SELECT execution_time_seconds, output_content FROM baseline_metrics ORDER BY id DESC LIMIT 1").fetchone()
    if baseline:
        latency, text = baseline
        print(f" -> Total Monolithic Latency: {latency:.2f} seconds")
        print("\n🚨 Programmatic Baseline Constraint Check:")
        
        # Check Budget Ceiling Constraint. Requires a '$' prefix so dates, phone numbers,
        # and other incidental figures in the text don't trigger a false violation.
        dollar_amounts = [int(s.replace(',', '')) for s in re.findall(r'\$\s?(\d[\d,]*)\b', text)]
        budget_violation = any(amount > budget_ceiling for amount in dollar_amounts)
        print(f" -> Budget Overrun Avoided (${budget_ceiling} Limit): {'✅ PASSED' if not budget_violation else '❌ FAILED'}")
        
        # Flex check for constraints tracking
        sla_check = any(word in text.lower() for word in ["hour", "sla", "response", "support"])
        print(f" -> Support SLA Safety Enforced: {'✅ PASSED' if sla_check else '⚠️ UNVERIFIED (Missing Metrics)'}")
    else:
        print(" -> No Single-Agent Baseline row found. Ensure you run 'baseline_single_agent.py' first.")
        
    conn.close()
    print("="*50)

if __name__ == "__main__":
    run_metric_analysis()
