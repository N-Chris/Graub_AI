import json
import re
from config import qwen_request
from database import log_message
import business_memory

def review_proposal(task_id, proposal_text, client_config):
    ceiling = client_config["constraints"]["budget_ceiling"]
    agent_name = client_config["agents"]["Finance"]["custom_name"]
    biz_name = client_config["business_name"]
    client_id = client_config.get("client_id", "graub_ai")
    
    print(f"\n[{agent_name}] Reviewing proposal for {task_id}...")
    
    # Dollar-prefixed regex tracking to isolate budget overruns safely
    dollar_amounts = [int(s.replace(',', '')) for s in re.findall(r'\$\s?(\d[\d,]*)\b', proposal_text)]
    for amount in dollar_amounts:
        if amount > ceiling:
            reason = f"Programmatic Budget Overrun Exception: Detected an asset costing ${amount}, which violates our strict ${ceiling} ceiling."
            log_message(task_id, "Finance", "Marketing_Sales", "critique", reason, ["budget_ceiling"], risk_level="high")
            return {"verdict": "critique", "reason": reason, "risk_level": "high"}

    system_prompt = (
        f"You are {agent_name}, the Finance Agent for {biz_name}. You are a junior-level assistant "
        f"supporting the human Finance expert — you handle first-pass budget review so they don't "
        f"have to check every line item themselves, but they hold final authority and sign-off. "
        f"Your hard constraints are a strict maximum budget ceiling of ${ceiling} "
        f"and maintaining positive short-term cash flow. Review the incoming proposal. "
        f"If it looks expensive or fails to declare clear ROI tracking, you MUST issue a 'critique' requesting cost cutting. "
        f"Also rate the overall financial risk of this proposal as 'low', 'medium', or 'high' — even proposals you accept "
        f"can carry real risk worth flagging to the human. "
        f"Output your response strictly in this JSON format structure, with no wrapper brackets outside the main object:\n"
        f'{{"verdict": "accept" or "critique", "reason": "Your detailed evaluation metrics or objections", "risk_level": "low" or "medium" or "high"}}'
    )

    memory_block = business_memory.get_memory_context(client_id, domain="Finance")
    if memory_block:
        system_prompt = f"{system_prompt}\n\n{memory_block}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Proposal to review:\n{proposal_text}"}
    ]
    
    try:
        raw_content = qwen_request(messages, json_mode=True)
        result = json.loads(raw_content)
        
        if isinstance(result, list) and len(result) > 0:
            result = result[0]
            
        verdict = result.get("verdict", "accept")
        reason = result.get("reason", "Financial parameter confirmation cleared via consensus.")
        risk_level = result.get("risk_level", "medium")
    except (ConnectionError, RuntimeError):
        raise
    except json.JSONDecodeError as e:
        verdict = "critique"
        reason = f"System validation failure reading finance structural response: {str(e)}"
        risk_level = "medium"
        
    log_message(task_id, "Finance", "Marketing_Sales", verdict, reason, ["budget_ceiling"], risk_level=risk_level)
    return {"verdict": verdict, "reason": reason, "risk_level": risk_level}
