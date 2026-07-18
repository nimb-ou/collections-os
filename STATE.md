# CollectOS Build State

**Last Updated:** 2026-07-19
**Session:** 0 — Environment Setup
**Status:** ✅ Complete

---

## Session 0: Environment Setup — COMPLETE

### What Was Done
- Installed all required brew packages (colima, docker, docker-compose, libpq, node@20, ffmpeg, ollama)
- Started colima container runtime with 4 CPU, 6GB RAM, 40GB disk
- Started ollama service and pulled qwen2.5:7b-instruct-q4_K_M model (4.7GB)
- Installed all required Python packages
- Verified all installations

### Installed Versions

**Container Runtime:**
- Colima: 0.10.3 (OSS Docker Desktop replacement)
- Docker Client: v29.6.2
- Docker Server: v29.5.2
- Docker Compose: 5.3.1

**Database Client:**
- PostgreSQL client (libpq): 18.4

**Node.js:**
- Node.js: v18.20.8 (nvm-managed, shadowing brew node@20)
- npm: 10.8.2

**Media Processing:**
- ffmpeg: 8.1.2

**AI/ML:**
- Ollama: 0.32.1 (running as brew service)
- Qwen Model: qwen2.5:7b-instruct-q4_K_M (pulled successfully, tested working)

**Python Environment:**
- Python: 3.12.11 (miniforge)
- pip: 25.1.1

**Python Packages Installed:**
- fastapi (0.116.1)
- uvicorn[standard] (0.35.0)
- sqlalchemy (2.0.42)
- psycopg2-binary (2.9.12)
- alembic (1.18.5)
- lightgbm (4.6.0)
- scikit-learn (1.7.1)
- shap (0.51.0)
- dagster (1.13.14)
- dagster-webserver (1.13.14)
- dbt-core (1.12.0)
- dbt-postgres (1.11.0)
- faster-whisper (1.2.1)
- piper-tts (1.5.0)
- streamlit (1.48.0)
- ortools (9.15.6755)
- faker (40.31.0)
- pyjwt (2.10.1)
- pytest (9.1.1)
- httpx (0.28.1)
- pyarrow (21.0.0)

### Verification Results
✅ Docker: Running (colima VM active)
✅ Ollama: Working (responded to test query: "Hello! How can I assist you today?")
✅ PostgreSQL client: Available (psql 18.4)

### Notes
- Node.js v18.20.8 from nvm is shadowing brew-installed node@20. This is acceptable; can switch to brew version if needed via PATH adjustment.
- Colima configured with sufficient resources for development (4 CPU, 6GB RAM per §24).
- All services ready for Session 1 (repository scaffold and database setup).

---

## What's Next

**Session 1 — Scaffold** (use Haiku):
- Initialize git repository
- Create GitHub repo (private) via `gh repo create collections-os --private`
- Set up directory structure per §7
- Create docker-compose.yml (postgres:16 + metabase)
- Write Makefile (up/seed/daily/demo/test/down targets)
- Create .env.example
- Write database migrations 001-010 per §9
- Verify `make up` brings up containers
- Update this file with Session 1 completion status

---

## Build Progress (§23 Checklist)

- [x] **S0 — Environment** ✅ 2026-07-19
- [ ] S1 — Scaffold
- [ ] S2 — Synthgen core
- [ ] S3 — Synthgen history
- [ ] S4 — dbt marts + Dagster
- [ ] S5 — Models
- [ ] S6 — Treatment + queues
- [ ] S7 — Allocation
- [ ] S8 — API
- [ ] S9 — BI bootstrap
- [ ] S10 — Ops console
- [ ] S11 — Bot core
- [ ] S12 — Bot at volume
- [ ] S13 — Field PWA
- [ ] S14 — Scorecards + Impact + Interventions
- [ ] S15 — E2E demo + hardening

---

## Known Issues / Deviations

None. All §24 requirements met.

---

## Memory Budget Status (§22.3)

**M4 Mac — 16 GB Total:**
- Postgres: ~500 MB (will cap at 2 GB in docker-compose)
- Ollama service: ~500 MB idle (qwen 7B-q4 loads ~5 GB on inference)
- Colima VM: ~1.5 GB
- System + other: ~8 GB
- **Available for dev:** ~5.5 GB

**Strategy:** Use SMALL_MODE=1 (.env) for daily development to run 30k accounts instead of 300k. Full scale only for final testing.

---

End of STATE.md
