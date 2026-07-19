# Devpost Submission Checklist — Graub AI (Track 3: Agent Society)

- [ ] Public GitHub repo, MIT license visible in the repo's "About" section (not just present as a file)
- [ ] All local files pushed — confirm nothing is sitting uncommitted (`git status`)
- [x] `docs/DEPLOYMENT.md` filled in with a real Alibaba Cloud proof link
- [ ] Architecture diagram renders correctly on GitHub (Mermaid block in README.md)
- [ ] Demo video recorded, ≤3 minutes, uploaded publicly (YouTube/Vimeo)
- [ ] Demo video shows: goal input → decomposition → a real Finance/IT critique → revision → resolution or escalation → human approval → publish step
- [x] `run_comparison.py` executed at least once; `comparison_results.json` committed and numbers in `docs/PROJECT_DESCRIPTION.md`
- [x] Written project description explicitly names **Track 3: Agent Society** (`docs/PROJECT_DESCRIPTION.md`)
- [ ] No API keys anywhere in git history (`git log --all --full-history -- .env`)
- [ ] `.venv/` excluded from the repo (check `.gitignore` covers it, or it will bloat the repo significantly)
