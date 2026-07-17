# Alibaba Cloud Deployment Proof

**Required for Devpost submission — this is a pass/fail requirement, refined mid-hackathon after some participants had to go back and re-add it.** Judges check this file directly.

## What's actually required (per the official Devpost update)
Two separate pieces of evidence — a terminal screenshot or a browser screenshot of the web app is **not** sufficient on its own for either of these:

1. **A code file link** showing your project genuinely calls a recognized Qwen Cloud base URL. Ours: [`config.py`](https://github.com/N-Chris/Graub_AI/blob/main/config.py) — `ENDPOINT_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"`.
2. **A screenshot of the Alibaba Cloud Workbench/ECS console itself** — the "My Resources" overview showing your instance in a **Running** state (region, instance count, status). Not a terminal window, not the web app in a browser — the actual Alibaba Cloud console page. Log into the ECS console, land on the Instances/Overview page, screenshot that.

## Instance Details
- **Service used:** Alibaba Cloud ECS (Elastic Compute Service)
- **Region:** _[fill in]_
- **Instance ID / public IP:** _[fill in]_

## Proof Link
`https://github.com/N-Chris/Graub_AI/blob/main/config.py` (or a commit-pinned permalink if you want it locked to a specific version)

## Steps Taken
1. `git clone https://github.com/N-Chris/Graub_AI.git`
2. `bash setup.sh` (or manual venv + `pip install -r requirements.txt`)
3. Created `.env` directly on the instance (never committed to git)
4. Ran `python main.py --client graub_ai` and `python web_ui.py` on the instance
5. Confirmed reachable at: _[fill in public URL/port]_

## Screenshot
_[attach the Alibaba Cloud ECS console screenshot here — see "What's actually required" above]_

