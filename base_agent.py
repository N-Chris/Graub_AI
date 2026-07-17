import json
from config import qwen_request
from database import log_message
import business_memory

class BaseDomainAgent:
    def __init__(self, internal_id, default_prompt_template):
        self.internal_id = internal_id
        self.template = default_prompt_template

    def get_profile(self, client_config):
        """Extracts runtime custom names and configurations dynamically from config files."""
        agent_cfg = client_config["agents"].get(self.internal_id, {})
        custom_name = agent_cfg.get("custom_name", self.internal_id)
        permissions = agent_cfg.get("permissions", [])
        return custom_name, permissions

    def execute_proposal(self, task_id, task_description, client_config):
        custom_name, perms = self.get_profile(client_config)
        print(f"\n[{custom_name}] Generating structural proposal for {task_id}...")
        
        # Enforce permissions parameter gates programmatically before calling Qwen
        if "propose" not in perms:
            err_msg = f"Security Exception: Agent '{custom_name}' lacks 'propose' clearance."
            print(f" ❌ {err_msg}")
            return f"BLOCKED: {err_msg}"

        # Inject business parameters into prompt layouts at runtime
        system_identity = self.template.format(
            custom_name=custom_name,
            business_name=client_config["business_name"],
            **client_config["constraints"]
        )

        client_id = client_config.get("client_id", "graub_ai")
        memory_block = business_memory.get_memory_context(client_id, domain=self.internal_id)
        if memory_block:
            system_identity = f"{system_identity}\n\n{memory_block}"

        messages = [
            {"role": "system", "content": system_identity},
            {"role": "user", "content": f"Task Action Required: {task_description}"}
        ]
        
        proposal_text = qwen_request(messages, json_mode=False)
        log_message(task_id, custom_name, "All", "proposal", proposal_text, [f"{self.internal_id}_guidelines"], 0.9)
        return proposal_text

    def review_proposal(self, task_id, proposal_text, client_config):
        custom_name, perms = self.get_profile(client_config)
        print(f"\n[{custom_name}] Auditing proposal parameters for {task_id}...")
        
        if "review" not in perms:
            return {"verdict": "accept", "reason": "Skipped: Lacks explicit review permissions parameters."}

        system_identity = self.template.format(
            custom_name=custom_name,
            business_name=client_config["business_name"],
            **client_config["constraints"]
        )

        client_id = client_config.get("client_id", "graub_ai")
        memory_block = business_memory.get_memory_context(client_id, domain=self.internal_id)
        if memory_block:
            system_identity = f"{system_identity}\n\n{memory_block}"

        messages = [
            {"role": "system", "content": system_identity},
            {"role": "user", "content": f"Proposal to audit:\n{proposal_text}"}
        ]
        
        # Protective Try/Except loop wrapping to catch JSON parsing issues (Risk #2)
        try:
            raw_content = qwen_request(messages, json_mode=True)
            result = json.loads(raw_content)
        except (ConnectionError, RuntimeError) as e:
            print(f" ❌ {custom_name} cannot reach Qwen Cloud: {e}")
            raise
        except json.JSONDecodeError as e:
            print(f" ⚠️ Recovery Path: Model returned malformed JSON. Falling back to explicit structured critique.")
            result = {"verdict": "critique", "reason": f"System validation failure reading formatting string: {str(e)}"}
            
        log_message(task_id, custom_name, "All", result["verdict"], result["reason"], [f"{self.internal_id}_rule_check"], risk_level=result.get("risk_level", "medium"))
        return result

    def adapt_proposal(self, task_id, original_proposal, critique_reason, client_config):
        custom_name, _ = self.get_profile(client_config)
        print(f"\n[{custom_name}] Adapting asset parameters to satisfy critiques...")
        
        system_identity = self.template.format(
            custom_name=custom_name,
            business_name=client_config["business_name"],
            **client_config["constraints"]
        )

        messages = [
            {"role": "system", "content": f"{system_identity}\nModify your asset to completely resolve the objections raised, while protecting campaign viability."},
            {"role": "user", "content": f"Original Draft:\n{original_proposal}\n\nObjections Matrix:\n{critique_reason}"}
        ]
        
        revised_text = qwen_request(messages, json_mode=False)
        log_message(task_id, custom_name, "All", "revision", revised_text, [f"{self.internal_id}_revision"])
        return revised_text
