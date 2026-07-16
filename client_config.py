import json
import os

# Establishes an absolute path directory to securely store dynamic client JSON records
CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "client_configs")

# Reference only — used to pre-select recommended agents in the setup UI when a client
# picks a tier. Not enforced anywhere; actual billing/enforcement is a post-hackathon item.
SUBSCRIPTION_TIERS = {
    "starter": {
        "label": "Starter — 1 agent",
        "included_agents": ["Marketing_Sales"],
    },
    "growth": {
        "label": "Growth — core operations",
        "included_agents": ["Marketing_Sales", "Finance", "Operations", "Customer_Service"],
    },
    "full": {
        "label": "Full Agency — all 7 agents",
        "included_agents": ["Marketing_Sales", "Finance", "IT_Tech", "Operations", "HR", "Customer_Service", "Leadership"],
    },
}

# Master template defining agent domain layouts, custom parameters, and hard rules
DEFAULT_CONFIG = {
    "business_name": "Graub AI",
    "subscription_tier": "full",
    "agents": {
        "Marketing_Sales": {"custom_name": "Marketing_Sales", "enabled": True, "permissions": ["propose", "chat_human"]},
        "Finance": {"custom_name": "Finance", "enabled": True, "permissions": ["review", "chat_human"]},
        "IT_Tech": {"custom_name": "IT_Tech", "enabled": True, "permissions": ["review", "chat_human", "file_edit"]},
        "Operations": {"custom_name": "Operations", "enabled": True, "permissions": ["propose", "chat_human"]},
        "HR": {"custom_name": "HR", "enabled": True, "permissions": ["propose", "chat_human"]},
        "Customer_Service": {"custom_name": "Customer_Service", "enabled": True, "permissions": ["propose", "chat_human"]},
        "Leadership": {"custom_name": "Leadership", "enabled": True, "permissions": ["arbitrate", "chat_human"]},
    },
    "constraints": {
        "budget_ceiling": 5000,
        "max_landing_pages": 3,
        "max_staff": 2,
        "min_setup_days": 5,
        "sla_hours": 4
    }
}

def load_client_config(client_id: str) -> dict:
    """Loads a custom client workspace profile, or falls back gracefully to default
    settings. Backfills any top-level keys missing from an older saved config (e.g. if
    the schema gained a field like subscription_tier since that file was last written),
    so existing client configs don't break as the schema evolves."""
    path = os.path.join(CONFIG_DIR, f"{client_id}.json")
    if not os.path.exists(path):
        config = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    else:
        with open(path, "r") as f:
            config = json.load(f)
        for key, default_value in DEFAULT_CONFIG.items():
            if key not in config:
                config[key] = default_value
    # Embedded (not persisted to disk, just set on load) so any function already
    # holding client_config can look up client_id without a separate parameter —
    # used by business_memory.py to key memory per client.
    config["client_id"] = client_id
    return config

def save_client_config(client_id: str, config: dict):
    """Saves updated parameters into a clean, format-indented JSON record on disk."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(os.path.join(CONFIG_DIR, f"{client_id}.json"), "w") as f:
        json.dump(config, f, indent=2)

def validate_agent_name(config: dict, proposed_name: str) -> bool:
    """Enforces the strict hackathon rule: No duplicate names allowed within an organization."""
    existing_names = [a["custom_name"].lower() for a in config["agents"].values()]
    return proposed_name.lower() not in existing_names
