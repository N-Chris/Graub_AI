import os
import re
import time
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("DASHSCOPE_API_KEY")

if not api_key:
    raise ValueError("Missing DASHSCOPE_API_KEY in .env file!")

# NOTE: Do not build the endpoint from WORKSPACE_ID as a subdomain (e.g.
# f"https://{WORKSPACE_ID}.ap-southeast-1.maas.aliyuncs.com/...") — that hostname
# pattern is for a dedicated MaaS throughput instance, which is a separate paid
# resource most accounts (including hackathon API-key/coupon accounts) don't have
# provisioned. That hostname will never resolve and fails with a DNS error, not an
# auth error, which is exactly what was happening here. The shared/pay-as-you-go
# compatible-mode endpoint below is what the hackathon's own instructions specify
# and what a standard DASHSCOPE_API_KEY actually has access to.
WORKSPACE_ID = "ws-bxw6vzcklfew64w6"
MODEL_NAME = "qwen3.7-plus"
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_society.db")

BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
ENDPOINT_URL = f"{BASE_URL}/chat/completions"

# Overridable via .env (QWEN_REQUEST_TIMEOUT=60) without touching code — useful if
# you're on a route where Qwen Cloud responds, just slowly, rather than not at all.
REQUEST_TIMEOUT_SECONDS = int(os.getenv("QWEN_REQUEST_TIMEOUT", "45"))
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2


def clean_json_string(raw_text: str) -> str:
    """Strips markdown code syntax out of LLM responses cleanly."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\n', '', text)
        text = re.sub(r'\n```$', '', text)
    return text.strip()


def qwen_request(messages, json_mode=False):
    """
    Executes a direct HTTP POST request to the Qwen Cloud (DashScope) compatible-mode
    endpoint. Retries on transient network errors; fails fast and loudly (rather than
    silently) on non-transient errors like auth or malformed requests, since silently
    swallowing those wastes debugging time later in the pipeline.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-WorkspaceId": WORKSPACE_ID,
    }

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        # qwen3.7-plus has extended "thinking" mode ON by default. In non-streaming
        # mode (which this is), the API sends nothing back until the ENTIRE hidden
        # reasoning phase finishes first — easily 30-60+ seconds on its own, on top
        # of normal network latency. None of these agent calls need deep reasoning;
        # they need fast, structured business proposals/reviews. Disabling this cut
        # response times dramatically and is also what Alibaba's own docs recommend
        # when using response_format/json_object (structured output + thinking mode
        # can conflict outright, not just add latency).
        "enable_thinking": False,
    }

    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(
                ENDPOINT_URL, json=payload, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS
            )

            if response.status_code == 401:
                # Auth errors will never succeed on retry — fail immediately with a clear message.
                raise RuntimeError(
                    f"Qwen Cloud Auth Error [401]: Check DASHSCOPE_API_KEY in .env. Response: {response.text}"
                )
            if response.status_code != 200:
                raise RuntimeError(f"Qwen Cloud Gateway Error [{response.status_code}]: {response.text}")

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return clean_json_string(content)

        except requests.exceptions.ConnectionError as e:
            last_error = e
            print(f"⚠️ Network connection failed (attempt {attempt}/{MAX_RETRIES}): {e}")
        except requests.exceptions.Timeout as e:
            last_error = e
            print(f"⚠️ Request timed out after {REQUEST_TIMEOUT_SECONDS}s (attempt {attempt}/{MAX_RETRIES})")
        except RuntimeError:
            # Auth/gateway errors — don't retry, surface immediately.
            raise
        except Exception as e:
            last_error = e
            print(f"⚠️ Unexpected error calling Qwen Cloud (attempt {attempt}/{MAX_RETRIES}): {e}")

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF_SECONDS)

    raise ConnectionError(
        f"Permanently failed to reach Qwen Cloud after {MAX_RETRIES} attempts. "
        f"Last error: {last_error}. Check your internet connection and that "
        f"{BASE_URL} is reachable (not blocked by a firewall/VPN)."
    )
