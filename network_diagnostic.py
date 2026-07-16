"""
Run this when test_connection.py times out. A timeout just means "no response
within N seconds" — it doesn't say whether the problem is DNS, the network path,
a firewall, or antivirus SSL interception. This checks each layer separately, in
order, so the FIRST one that fails tells you exactly where to focus.

Usage:
    python network_diagnostic.py
"""
import os
import socket
import ssl
import time

HOST = "dashscope-intl.aliyuncs.com"
PORT = 443


def check_proxy_env():
    print("[0/4] Checking for proxy environment variables...")
    proxy_vars = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY"]
    found = {k: v for k, v in os.environ.items() if k in proxy_vars}
    if found:
        print(f"   ⚠️ Found proxy settings: {found}")
        print("   -> requests uses these automatically. If you're not intentionally")
        print("      using a proxy, an incorrect/stale one here is a common cause of")
        print("      exactly this kind of silent hang. Try: unset HTTPS_PROXY (bash) or")
        print("      $env:HTTPS_PROXY=''  (PowerShell), then re-run.")
    else:
        print("   ✅ No proxy environment variables set.")
    print()


def check_dns():
    print(f"[1/4] DNS resolution for {HOST}...")
    try:
        start = time.time()
        ip = socket.gethostbyname(HOST)
        print(f"   ✅ Resolved to {ip} in {time.time() - start:.2f}s")
        return True
    except socket.gaierror as e:
        print(f"   ❌ DNS resolution failed: {e}")
        print("   -> Your machine can't look up this address at all. Try a different")
        print("      network (e.g. phone hotspot) to check if it's this network specifically.")
        return False


def check_tcp():
    print(f"\n[2/4] Raw TCP connection to {HOST}:{PORT}...")
    try:
        start = time.time()
        sock = socket.create_connection((HOST, PORT), timeout=10)
        sock.close()
        print(f"   ✅ TCP connection opened in {time.time() - start:.2f}s")
        return True
    except (socket.timeout, OSError) as e:
        print(f"   ❌ TCP connection failed/timed out: {e}")
        print("   -> DNS works, but nothing answers on port 443. This is the classic")
        print("      signature of a firewall silently DROPPING packets rather than")
        print("      rejecting them outright — common with ISP-level filtering or")
        print("      traffic shaping on international routes. A VPN through a")
        print("      different region is the most reliable fix.")
        return False


def check_tls():
    print(f"\n[3/4] TLS handshake with {HOST}:{PORT}...")
    try:
        context = ssl.create_default_context()
        start = time.time()
        with socket.create_connection((HOST, PORT), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=HOST):
                print(f"   ✅ TLS handshake completed in {time.time() - start:.2f}s (certificate verified OK)")
        return True
    except ssl.SSLError as e:
        print(f"   ❌ TLS handshake failed: {e}")
        print("   -> TCP connects fine, but TLS fails. This usually means antivirus or")
        print("      corporate security software is doing HTTPS/SSL inspection and")
        print("      interfering. Try temporarily disabling it (HTTPS scanning specifically,")
        print("      not the whole antivirus) and re-run this script.")
        return False
    except (socket.timeout, OSError) as e:
        print(f"   ❌ TLS handshake timed out: {e}")
        return False


def check_http():
    print(f"\n[4/4] Full HTTPS request (what your app actually does)...")
    try:
        import requests
        start = time.time()
        r = requests.get(f"https://{HOST}/compatible-mode/v1", timeout=20)
        print(f"   ✅ Got HTTP {r.status_code} back in {time.time() - start:.2f}s — any response at all is a good sign")
        return True
    except requests.exceptions.ReadTimeout:
        print(f"   ❌ Connected and handshook fine, but no response body arrived within 20s.")
        print("   -> The connection opens, then goes quiet. Often this is deep packet")
        print("      inspection or traffic shaping on the route to this specific provider —")
        print("      the handshake gets through but the actual data gets throttled or")
        print("      dropped. A VPN (routing through a different country) is the most")
        print("      reliable workaround for local development.")
        return False
    except Exception as e:
        print(f"   ❌ Request failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Graub AI — Layered Network Diagnostic")
    print("=" * 60)
    check_proxy_env()
    if not check_dns():
        raise SystemExit(1)
    if not check_tcp():
        raise SystemExit(1)
    if not check_tls():
        raise SystemExit(1)
    check_http()
    print("\n" + "=" * 60)
    print("Diagnostic complete — the notes above the first ❌ tell you where to focus.")
    print("If everything above passed, the issue may just be intermittent latency;")
    print("try raising QWEN_REQUEST_TIMEOUT in your .env (e.g. to 90) and re-running.")
    print("=" * 60)
