# Alibaba Cloud Deployment Proof

**Required for Devpost submission.** Fill this in once deployed — judges check this file.

## Instance Details
- **Service used:** Alibaba Cloud ECS (Elastic Compute Service)
- **Region:** _[fill in]_
- **Instance ID / public IP:** _[fill in]_

## Proof Link
Link to the exact code file/commit running on the instance:
_[fill in GitHub permalink, e.g. https://github.com/N-Chris/Graub_AI/blob/<commit-sha>/main.py]_

## Steps Taken
1. `git clone https://github.com/N-Chris/Graub_AI.git`
2. `pip install -r requirements.txt`
3. Copied `.env` onto the instance manually via `scp` (never committed to git)
4. Ran `python main.py --client graub_ai` and `python web_ui.py` on the instance
5. Confirmed reachable at: _[fill in public URL/port]_

## Screenshot
_[attach a screenshot of the running instance / terminal output here]_
