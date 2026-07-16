"""
Quick standalone check that your .env key and network can actually reach Qwen Cloud.
Run this FIRST whenever something seems broken — it costs one tiny API call instead
of burning through a full main.py run (and your hackathon voucher) to find out your
connection is the problem.

Usage:
    python test_connection.py
"""
from config import qwen_request, ENDPOINT_URL, WORKSPACE_ID, MODEL_NAME

def main():
    print("=" * 55)
    print("Graub AI — Qwen Cloud Connectivity Test")
    print("=" * 55)
    print(f"Endpoint:    {ENDPOINT_URL}")
    print(f"Workspace:   {WORKSPACE_ID}")
    print(f"Model:       {MODEL_NAME}")
    print("-" * 55)

    try:
        reply = qwen_request([
            {"role": "system", "content": "Reply with exactly one short sentence."},
            {"role": "user", "content": "Say hello and confirm you can hear me."}
        ])
        print("✅ SUCCESS — Qwen Cloud responded:")
        print(f"   {reply}")
    except Exception as e:
        print("❌ FAILED — could not get a response from Qwen Cloud.")
        print(f"   {e}")
        print("\nCommon causes:")
        print("  1. DASHSCOPE_API_KEY missing/wrong in .env")
        print("  2. No internet connection, or a firewall/VPN blocking dashscope-intl.aliyuncs.com")
        print("  3. Voucher/credits exhausted on your Qwen Cloud account")
        print("\nFor a timeout specifically (connects but never responds), run:")
        print("  python network_diagnostic.py")
        print("It checks DNS, raw TCP, TLS, and the HTTP request as separate layers,")
        print("so you can see exactly where it's actually failing.")
        raise SystemExit(1)

if __name__ == "__main__":
    main()
