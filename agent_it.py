import json
from config import qwen_request
from database import log_message, create_file_edit_task
import file_tools
import business_memory

def propose_file_edit(task_id, relative_path, instruction, client_config):
    """
    IT_Tech drafts a proposed change to a file in the sandboxed client_workspace
    folder. This function ONLY creates a pending task with the proposed content —
    it never writes to disk. The actual write happens later, via
    file_tools.apply_file_edit, called from web_ui.py's /publish route, and only
    after a human has approved and published this specific task.
    """
    agent_cfg = client_config["agents"]["IT_Tech"]
    agent_name = agent_cfg["custom_name"]
    biz_name = client_config["business_name"]

    if "file_edit" not in agent_cfg.get("permissions", []):
        msg = f"BLOCKED: Security Exception: Agent '{agent_name}' lacks 'file_edit' clearance."
        print(f" ❌ {msg}")
        return {"blocked": True, "reason": msg}

    current_content = file_tools.read_file(relative_path)
    print(f"\n[{agent_name}] Drafting proposed edit for '{relative_path}'...")

    system_prompt = (
        f"You are {agent_name}, the IT & Technology Agent for {biz_name}. "
        f"You are editing a file in the client's workspace on their own instruction. "
        f"Output ONLY the complete new file content — no explanations, no markdown "
        f"fences, no commentary. The full text you output will replace the file's "
        f"contents exactly as written."
    )
    user_prompt = (
        f"Current content of '{relative_path}':\n---\n{current_content}\n---\n\n"
        f"Instruction: {instruction}\n\n"
        f"Output the complete new file content only."
    )

    new_content = qwen_request([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ], json_mode=False)

    create_file_edit_task(
        task_id=task_id,
        assigned_to="IT_Tech",
        description=f"Proposed file edit for '{relative_path}': {instruction}",
        file_target=relative_path,
        file_content=new_content,
    )
    log_message(
        task_id, agent_name, "Human_IT_Tech", "file_edit_proposal",
        f"Proposed new content for '{relative_path}'. Awaiting human approval + publish before anything is written to disk.",
        ["file_edit_sandbox"], 0.9
    )
    print(f" -> Proposal created. Nothing written to disk yet — pending human approval at /agent/IT_Tech")
    return {"blocked": False, "task_id": task_id, "file_target": relative_path, "proposed_content": new_content}


def review_proposal(task_id, proposal_text, client_config):
    agent_name = client_config["agents"]["IT_Tech"]["custom_name"]
    max_pages = client_config["constraints"]["max_landing_pages"]
    biz_name = client_config["business_name"]
    client_id = client_config.get("client_id", "graub_ai")
    
    print(f"\n[{agent_name}] Reviewing technical feasibility for {task_id}...")
    
    system_prompt = (
        f"You are {agent_name}, the IT & Technology Agent for {biz_name}. You are a junior-level "
        f"assistant supporting the human IT expert — you handle first-pass technical review and "
        f"routine file/system work so they don't have to do it all themselves, but they hold final "
        f"authority and sign-off. Your objective is ensuring system security, "
        f"data privacy, and technical infrastructure feasibility. "
        f"Your hard constraint: Maximum technical capacity of {max_pages} active landing pages or simultaneous deployments. "
        f"Review the incoming proposal. If it demands overly complex systems architectures, unprotected data storage, "
        f"or more than {max_pages} landing pages, you MUST issue a 'critique' requesting simplification. "
        f"Also rate the overall technical/security risk as 'low', 'medium', or 'high' — even proposals you accept "
        f"can carry real risk worth flagging to the human. "
        f"Output your response strictly in this JSON format structure, with no wrapper brackets outside the main object:\n"
        f'{{"verdict": "accept" or "critique", "reason": "Your specific technical infrastructure objections", "risk_level": "low" or "medium" or "high"}}'
    )

    memory_block = business_memory.get_memory_context(client_id, domain="IT_Tech")
    if memory_block:
        system_prompt = f"{system_prompt}\n\n{memory_block}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Proposal to technically evaluate:\n{proposal_text}"}
    ]
    
    try:
        raw_content = qwen_request(messages, json_mode=True)
        result = json.loads(raw_content)
        
        # Protective normalization: Unpack list if returned as an array wrapper
        if isinstance(result, list) and len(result) > 0:
            result = result[0]
            
        # Ensure fallback keys exist to prevent dictionary mapping errors
        verdict = result.get("verdict", "accept")
        reason = result.get("reason", "Technical feasibility clearance provided by default mapping path.")
        risk_level = result.get("risk_level", "medium")
    except (ConnectionError, RuntimeError):
        raise
    except json.JSONDecodeError as e:
        verdict = "critique"
        reason = f"System validation failure reading IT structural response: {str(e)}"
        risk_level = "medium"
        
    log_message(task_id, "IT_Tech", "Marketing_Sales", verdict, reason, ["technical_feasibility"], risk_level=risk_level)
    return {"verdict": verdict, "reason": reason, "risk_level": risk_level}
