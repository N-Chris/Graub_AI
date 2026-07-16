from config import qwen_request
from database import log_message
import business_memory

def generate_proposal(task_id, description, client_config):
    agent_cfg = client_config["agents"]["Marketing_Sales"]
    agent_name = agent_cfg["custom_name"]
    biz_name = client_config["business_name"]
    client_id = client_config.get("client_id", "graub_ai")
    
    print(f"\n[{agent_name}] Generating growth and revenue proposal for {task_id}...")
    
    if "propose" not in agent_cfg["permissions"]:
        return f"BLOCKED: Security Exception: Agent '{agent_name}' lacks 'propose' clearance."

    system_prompt = (
        f"You are {agent_name}, the Marketing & Sales Agent for {biz_name}. You are a junior-level "
        f"assistant supporting the human Marketing expert — you handle first-pass campaign drafting "
        f"so they don't have to start from a blank page, but they hold final authority and sign-off. "
        f"Your objective is dual-focused: "
        f"aggressive brand exposure and high sales conversion/revenue generation. "
        f"Constraint: You always push for bold campaigns and premium sales pricing, but you must explicitly "
        f"state your budget estimate, expected user acquisition, and projected revenue/ROI using a '$' symbol. "
        f"Output your proposal clearly detailing the campaign action items, pricing model, estimated cost, and conversion funnel."
    )

    memory_block = business_memory.get_memory_context(client_id, domain="Marketing_Sales")
    if memory_block:
        system_prompt = f"{system_prompt}\n\n{memory_block}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Task: {description}"}
    ]
    
    proposal_text = qwen_request(messages, json_mode=False)
    log_message(task_id, "Marketing_Sales", "Finance", "proposal", proposal_text, ["brand_guidelines", "revenue_targets"], 0.9)
    return proposal_text

def revise_proposal(task_id, original_proposal, critique_reason, client_config):
    agent_name = client_config["agents"]["Marketing_Sales"]["custom_name"]
    biz_name = client_config["business_name"]
    
    print(f"\n[{agent_name}] Modifying sales campaign due to incoming critique...")
    system_prompt = (
        f"You are {agent_name}, the Marketing & Sales Agent for {biz_name}. Finance has critiqued your proposal. "
        f"Revise your growth campaign and sales pricing model to optimize cost and maximize short-term conversion. "
        f"Explicitly cut high-risk budget components to satisfy Finance while protecting core revenue viability, stating all costs with a '$'."
    )
    
    user_input = f"Original Proposal:\n{original_proposal}\n\nCritique Feed:\n{critique_reason}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]
    
    revised_text = qwen_request(messages, json_mode=False)
    log_message(task_id, "Marketing_Sales", "Finance", "revision", revised_text, ["brand_guidelines", "cost_efficiency"])
    return revised_text
