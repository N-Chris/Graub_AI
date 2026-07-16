import sys
import json
from client_config import DEFAULT_CONFIG, save_client_config, validate_agent_name

def run_onboarding():
    print("\n" + "="*50)
    print("🚀 GRAUB AI: CLIENT ONBOARDING ENGINE")
    print("="*50)
    
    # 1. Capture and format company profile name
    biz_name = input("Enter your Business Name: ").strip()
    if not biz_name:
        print("❌ Business name cannot be empty. Aborting.")
        sys.exit(1)
        
    # Deep copy — DEFAULT_CONFIG.copy() is shallow, and its nested agent dicts would
    # otherwise be shared by reference, so naming one client's agents would silently
    # corrupt the shared default for every client onboarded afterward.
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    config["business_name"] = biz_name

    # 1b. Subscription tier selection (data model only — billing is a post-hackathon item)
    from client_config import SUBSCRIPTION_TIERS
    print("\n💳 Choose a subscription tier (this only pre-selects recommended agents below —")
    print("   no payment is processed; billing integration is planned post-hackathon):\n")
    for key, tier in SUBSCRIPTION_TIERS.items():
        print(f"  [{key}] {tier['label']}")
    tier_choice = input("Tier (press Enter for 'full'): ").strip().lower() or "full"
    if tier_choice not in SUBSCRIPTION_TIERS:
        print(f"Unrecognized tier '{tier_choice}', defaulting to 'full'.")
        tier_choice = "full"
    config["subscription_tier"] = tier_choice
    recommended = SUBSCRIPTION_TIERS[tier_choice]["included_agents"]
    for domain in config["agents"]:
        config["agents"][domain]["enabled"] = domain in recommended
    
    # 2. Sequential Custom Naming Wizard with Duplicate Prevention
    print("\n✍️  Name Your Agent Fleet. (No two agents can share the same name.)\n")
    for domain in config["agents"]:
        if not config["agents"][domain]["enabled"]:
            print(f" -> Skipping '{domain}': not included in the '{tier_choice}' tier.")
            continue
        current_default = config["agents"][domain]["custom_name"]
        while True:
            prompt_msg = f"Assign custom name for '{domain}' agent (Press Enter for '{current_default}'): "
            chosen_name = input(prompt_msg).strip()
            
            # If user hits Enter, fall back gracefully to the standard internal key string
            if not chosen_name:
                chosen_name = current_default
                
            # Temporarily clear the agent's name block so it doesn't collide with its own check
            config["agents"][domain]["custom_name"] = ""
            
            if validate_agent_name(config, chosen_name):
                config["agents"][domain]["custom_name"] = chosen_name
                print(f" -> Success: Bound domain '{domain}' to name '{chosen_name}'\n")
                break
            else:
                print(f"❌ Error: '{chosen_name}' is already claimed by another agent. Choose a unique name.")
                
    # 3. Dynamic Runtime Permissions Binding Wizard
    print("\n🔑 Set Functional Permissions Per Agent")
    print("Options (comma-separated): propose, review, arbitrate, chat_human, publish\n")
    for domain in config["agents"]:
        if not config["agents"][domain]["enabled"]:
            continue
        agent_name = config["agents"][domain]["custom_name"]
        current_perms = ", ".join(config["agents"][domain]["permissions"])
        
        prompt_perms = f"Set permissions for {agent_name} (Press Enter for baseline [{current_perms}]): "
        user_perms = input(prompt_perms).strip()
        
        if user_perms:
            config["agents"][domain]["permissions"] = [p.strip() for p in user_perms.split(",") if p.strip()]
            
    # 4. Serialize to Multi-Tenant Storage Directory
    client_id = biz_name.lower().replace(" ", "_")
    save_client_config(client_id, config)
    
    print("\n" + "="*50)
    print(f"✅ Onboarding Complete for Client Workspace Profile: {client_id}")
    print(f"📄 Settings saved securely inside client_configs/{client_id}.json")
    print(f"👉 Target System Execution Command: python main.py --client {client_id}")
    print("="*50 + "\n")
    return client_id

if __name__ == "__main__":
    run_onboarding()
