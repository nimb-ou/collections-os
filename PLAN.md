# CollectOS — End-to-End Collections Ecosystem for a CV/CE Bank Portfolio

**Master Plan & Single Source of Truth**
Created: 2026-07-19 · Owner: Nimit Jain · Built with Claude Code · License target: MIT (own code) + OSS components

---

## 0. HOW TO USE THIS FILE (read first, every session)

This file is the **complete context** for the project. The owner has **limited AI tokens**, so:

1. **Every future Claude Code session** starts with: *"Read PLAN.md §<relevant> and STATE.md, then do exactly Session N from §23. Update STATE.md and commit when done."* No re-exploration, no re-planning, no subagents unless a session says so.
2. `STATE.md` (created in Session 1) is the living status file: what is built, what works, what broke, what's next. Keep it under 100 lines. PLAN.md is append-only except the checkboxes in §23.
3. Model choice per session is listed in §23 (Haiku for scaffolding, Sonnet for logic/ML). Run `/model haiku` or `/model sonnet` accordingly.
4. This project lives at `~/Desktop/First_project/collections-os/`. It is its own git repo (Session 1 creates it). It is **not** part of ML_projects.

---

## 1. VISION & SCOPE

An **end-to-end, fully automated collections operating system** for a bank's **Commercial Vehicle (CV) & Construction Equipment (CE) loan portfolio**, covering the complete lifecycle:

- **Pre-due**: bounce-risk scoring → targeted reminders (AI voice bot + SMS-sim + human calls) before EMI presentation.
- **Post-due / post-bounce**: self-cure prediction → treatment waterfall (bot → telecaller → field) → PTP capture → payment tracking.
- **Allocation**: 3,00,000 due accounts/month intelligently distributed across ~300 telecallers and **1,500+ field agents (FOS)** by geography, capacity, language, skill, and risk.
- **Execution**: campaign manager, dialer queues, AI voice bot (local, free), field agent mobile app (PWA) with beat plans, visit & PTP capture.
- **Monitoring**: daily scorecards for agents → team leads → area managers → zonal heads; calling-impact measurement with control groups; bot QA.
- **Intelligence**: bounce model, self-cure model, roll-forward model, best-time-to-call, customer insight cards for collectors, portfolio early-warning, and an **interventions engine** that tells business teams what to act on, daily.
- **Ownership**: every account, every day, has exactly one owner, one treatment, and one next action — assigned automatically.

**Two deployment targets:**
1. **Mac (dev/demo)** — runs fully on the MacBook with a **synthetic bank** of 3,00,000 accounts and 24 months of history. Proves the entire system end-to-end. Zero real data.
2. **Office (Kotak)** — same Docker images on an on-prem VM, fed by real daily extracts through a thin adapter layer (§25). Nothing in the runtime calls any external/paid API, so it is deployable inside a bank network.

---

## 2. CURRENT ENVIRONMENT — VERIFIED 2026-07-19

### 2.1 What EXISTS on this Mac now (checked live)

| Item | Status | Notes |
|---|---|---|
| Hardware | **Apple M4, 16 GB RAM, 228 GB SSD (89 GB free)** | Enough. Memory budget in §22.3 must be respected. |
| macOS + zsh | ✓ | Darwin 25.5.0 |
| Homebrew | ✓ 5.1.11 | Package manager for everything below |
| Python | ✓ 3.12.11 (miniforge, `/opt/homebrew/Caskroom/miniforge/base`) | numpy, pandas, scikit-learn, matplotlib, jupyter, black, mypy, pytest installed |
| Node.js | ✓ v18.20.8 | OK for PWA; upgrade to 20 LTS in Session 0 (`brew install node@20`) |
| git + GitHub CLI | ✓ `gh` authenticated as **nimb-ou** | Can create the new repo |
| Claude Code | ✓ CLI on Mac; models Haiku/Sonnet/Opus/Fable available | **Build tool only — never a runtime dependency** (§3) |
| Docker / Colima | ✗ not installed | Session 0 installs **Colima** (OSS; avoids Docker Desktop enterprise licensing) |
| PostgreSQL | ✗ | via Docker compose (Session 0/1) |
| Ollama (local LLM) | ✗ | Session 0 (`brew install ollama`) |
| ffmpeg | ✗ | Session 0 (audio for voice bot) |
| Java | ✗ | Not needed (Metabase runs in Docker) |

### 2.2 Claude Code connectors currently available (mostly NOT needed)

- **Connected/usable now**: GitHub (`gh` as nimb-ou), HuggingFace MCP (user `nimitttt` — handy for pulling STT/TTS models), Google Drive/Gmail/Calendar connectors, browser automation, Canva.
- **Available but unauthorized** (Slack, Notion, Linear, BigQuery, etc.): **not required** for this project. Do not authorize anything for this build.
- **Rule**: the runtime system must never depend on any Claude connector. Connectors may only assist *building* (e.g., HF model downloads).

### 2.3 What must be INSTALLED on the Mac (Session 0 checklist — commands in §24)

Colima + docker CLI + docker-compose · PostgreSQL 16 (container) · Metabase (container) · Ollama + `qwen2.5:7b-instruct-q4_K_M` · ffmpeg · Python packages (FastAPI, SQLAlchemy, LightGBM, SHAP, Dagster, dbt-core, faster-whisper, piper-tts, streamlit, ortools) · Node 20.

### 2.4 What must be CONNECTED at the office for real end-to-end (each has a free dev substitute on Mac)

| Real-world dependency | Office (Kotak) source | Mac dev substitute (free) |
|---|---|---|
| Daily account/DPD data | Core banking extract (SFTP CSV / read-only DB view) | **Synthetic bank generator** (§10) |
| Customer master + contacts | CRM extract | Synthetic |
| EMI schedule, presentations, bounces | Loan management system extract | Synthetic |
| Payments feed | Payments/CBS extract | Synthetic + manual "mark paid" in ops console |
| Outbound telephony (PSTN) | Bank's dialer (Ameyo/Genesys/etc.) or SIP trunk via FreeSWITCH | **Browser-mic bot tester + call simulator** (no real calls; §16) |
| SMS | Bank's SMS gateway vendor | `sms_outbox` table + log viewer |
| Email reports | Corporate SMTP | Local file / Mailpit container |
| Agent identity/SSO | Active Directory / SSO | Local JWT users with roles |
| UPI payment links | Bank payment gateway | Fake link + manual settlement |

**Honest statement**: real phone calls and real SMS can never be free. The *software* is 100% free/OSS and call-ready; the *telecom pipe* is provided by the bank at the office. On the Mac, calls are exercised through a browser microphone and an automated call simulator, which is sufficient to prove every component.

---

## 3. HARD RULES (non-negotiable)

1. **Free/OSS only.** Every runtime component: PostgreSQL, Dagster, dbt-core, FastAPI, LightGBM, OR-Tools, Ollama (+Apache-2.0 models), faster-whisper, Piper/AI4Bharat TTS, Metabase OSS, Streamlit, React/Vite, FreeSWITCH (office). No paid tiers, no cloud APIs in runtime.
2. **Local-first / private-by-design.** At runtime, **no data leaves the machine/network**. All AI (LLM, STT, TTS, ML) runs locally. This is what makes it bank-deployable.
3. **Claude = builder, not runtime.** The finished system runs with Claude Code switched off.
4. **No real customer data on the personal Mac. Ever.** Mac = synthetic only. Real data only inside bank infrastructure after bank approval (§25). Do not connect personal Claude/cloud tools to office data.
5. **Compliance built-in** (§22.4): RBI contact-hour windows (08:00–19:00) enforced in code, recording disclosure in every bot script, no-harassment script guardrails, DNC respect, append-only audit trail, role-based PII masking, DPDP-aligned purpose limitation.
6. **Plug-and-play boundary**: the only integration surface is the **data contract** (§8) — bank tables in, everything else automatic. A YAML mapping adapts any bank's column names to the canonical schema.
7. **One owner per account per day.** The system always knows who owns each account and what its next action is; nothing falls through.

---

## 4. DOMAIN PRIMER (context for all future sessions)

### 4.1 Portfolio
- Products: HCV, LCV/ICV, Tippers, Tractors, Excavators, Backhoe loaders, Cranes. Ticket sizes ₹4L–₹60L, tenures 24–60 months, monthly EMIs via NACH mandate presented on cycle dates (1st/5th/10th/15th).
- **Bounce** = NACH presentation fails (insufficient funds/mandate issues). CV/CE bounce rates typically 10–14%; strong seasonality (monsoon Jun–Sep stresses tippers/CE; harvest cycles help tractors).
- **DPD buckets**: Pre-due → X/Current (0 DPD, bounced but cycle not lapsed) → B1 (1–30) → B2 (31–60) → B3 (61–90) → NPA (90+). Deep buckets (150+) often go to agencies/legal (repo, SARFAESI/arbitration) — v1 tracks, doesn't manage legal.

### 4.2 Organization (assumed; configurable)
| Layer | Count | Span |
|---|---|---|
| Field agents (FOS) | 1,500 | 40–70 accounts/day beat |
| Field Team Leads | ~100 | 1:15 FOS |
| Area Collection Managers (ACM) | ~15 | 1:7 TLs |
| Zonal/Regional heads (RCM) | 4–5 | zones |
| Telecallers | ~300 | 200–250 dials, 60–80 connects/day |
| Telecalling TLs | ~20 | 1:15 |
| National Collections Head + strategy team | 1+ | consumes §20 |

### 4.3 Monthly volume math (drives all capacity design)
- 3,00,000 accounts with EMI due; ~10–14% bounce → **30–42k bounces/cycle**.
- **Pre-due**: score all 3L; bot-call top ~40% bounce-risk (~1.2L calls over 4 days ≈ 30k bot-calls/day), human-call top 5% (15k over 4 days ≈ 20/telecaller/day), SMS-sim to all.
- **Post-bounce day 0–2**: bot first-touch every bounce (30–40k over 2 days). Day 2–7: telecallers work non-cured high-risk (~15k) → ~60 connects/telecaller/day. Field gets: 30+ DPD, high-value, broken-PTP, non-contactable → 60–90k account-visits/month across 1,500 FOS ≈ 2–3 visits/FOS/day dedicated to this cohort plus BAU beat.
- Every number above is computed daily by the pipeline and visible in dashboards.

---

## 5. KPI DICTIONARY (canonical definitions — dashboards must use these exactly)

| KPI | Definition |
|---|---|
| Demand base | Accounts (and ₹ EMI amount) due in cycle |
| Bounce % | Bounced presentations ÷ presentations |
| Resolution % | Accounts that cleared current-cycle dues ÷ demand base (by bucket: X-res, B1-res…) |
| Collection efficiency % | ₹ collected ÷ ₹ demanded (also overdue-CE incl. arrears) |
| Roll-forward % | Bucket Bn accounts moving to Bn+1 at month-end ÷ Bn start |
| Roll-back / Normalization % | Accounts moving to a lower bucket / to current |
| Stabilization % | Staying in same bucket |
| Flow X→1 | Current accounts entering B1 |
| RPC % | Right-party contacts ÷ connected calls |
| PTP rate / PTP-kept % | PTPs ÷ RPCs; PTPs paid on promise date ÷ PTPs matured |
| Attempt intensity | Attempts per account per cycle (by channel) |
| Visit strike rate | Visits resulting in collection/PTP ÷ visits |
| Bot containment % | Bot calls fully handled (no human) ÷ bot connects |
| Uplift | KPI delta of treated vs matched holdout control (§19.3) |
| Agent score | Composite: difficulty-adjusted resolution 40% + ₹ efficiency 25% + PTP-kept 15% + activity compliance 10% + quality 10% |

---

## 6. ARCHITECTURE

```mermaid
flowchart LR
  subgraph IN[Bank Inputs / SynthGen]
    A[Daily extracts:\naccounts, customers, EMI,\npresentations, payments]
  end
  subgraph DATA[PostgreSQL 16]
    B[landing → staging → marts\n(dbt-core models)]
    C[mart_account_daily\n(partitioned)]
  end
  subgraph BRAIN[Intelligence – Python]
    D[ML scoring:\nbounce · self-cure · roll ·\nbest-time · propensity]
    E[Treatment engine]
    F[Allocation engine\n(rules + OR-Tools)]
  end
  subgraph OPS[Execution]
    G[Campaigns & queues]
    H[AI Voice Bot\nfaster-whisper + Ollama + Piper]
    I[Telecaller console]
    J[Field PWA\n(React, offline)]
    K[sms_outbox / dialer adapter]
  end
  subgraph WATCH[Monitoring & Insight]
    L[Metabase dashboards]
    M[Scorecards daily]
    N[Interventions engine\n+ LLM daily brief]
  end
  A-->B-->C-->D-->E-->F-->G
  G-->H & I & J & K
  H & I & J -->|dispositions, PTPs, payments| C
  C-->L & M & N
  O[Dagster orchestrator] -.schedules.-> B & D & E & F & G & M & N
  P[FastAPI backend + JWT roles] --- G & H & I & J & M
```

### 6.1 Stack decisions (final — do not relitigate in build sessions)

| Concern | Choice | Why |
|---|---|---|
| Database | **PostgreSQL 16** (Docker) | Free, handles 100M+ row partitioned tables easily |
| Transformations | **dbt-core + dbt-postgres** | Free, tested SQL lineage, enterprise-credible |
| Orchestration | **Dagster OSS** | Free, asset-based, great UI for demos; cron fallback |
| ML | **LightGBM + scikit-learn + SHAP** | Free, fast on CPU, explainable |
| Optimization | **Google OR-Tools** | Free allocation solver |
| API | **FastAPI + Uvicorn**, JWT auth | Free, async, OpenAPI docs |
| LLM | **Ollama** + `qwen2.5:7b-instruct-q4_K_M` (Apache-2.0) | Local, free, good Hinglish; llama3.1:8b alternate |
| STT | **faster-whisper** small/medium int8 | Local, free, strong Hindi/English |
| TTS | **Piper** (en/hi voices) + **AI4Bharat Indic Parler-TTS** (better Hindi, heavier) with **prompt-bank hybrid** (§16.3) | Free, local |
| BI | **Metabase OSS** (Docker) | Free, self-serve for supervisors |
| Ops console | **Streamlit** | Fastest to build; internal tool |
| Field app | **React + Vite PWA** (installable, offline queue) | Free, no app-store friction |
| Telephony (office only) | **FreeSWITCH/Asterisk** + bank SIP, or file/API handoff to bank's existing dialer | OSS; Mac uses simulator |
| Containers | **Colima** + docker CLI + compose | Fully OSS (Docker Desktop licensing avoided) |

---

## 7. REPO LAYOUT

```
collections-os/
├── PLAN.md                  # this file (source of truth)
├── STATE.md                 # living build status (Session 1 creates)
├── Makefile                 # make up / seed / daily / demo / test / down
├── docker-compose.yml       # postgres, metabase, (mailpit)
├── .env.example             # all config; SMALL_MODE=1 → 30k accounts
├── infra/migrations/        # numbered .sql DDL (§9)
├── data_contracts/          # §8: input specs + mapping.yaml + validator
├── synthgen/                # §10 synthetic bank generator
├── dbt/                     # staging + marts models & tests
├── pipeline/                # Dagster assets & schedules (§11)
├── models_ml/               # train/, score/, registry/ (§12)
├── strategy/                # treatment.py, allocation.py, capacity.yaml (§13–14)
├── campaigns/               # queue builder, cadence rules (§15)
├── api/                     # FastAPI app (§21)
├── bot/                     # voice bot: flows/, stt.py, tts.py, brain.py, simulator/, web_tester/ (§16)
├── apps/ops_console/        # Streamlit (§18)
├── apps/field_pwa/          # React PWA (§17)
├── bi/                      # Metabase bootstrap + dashboard SQL (§19)
├── insights/                # interventions rules + LLM brief (§20)
├── quality/                 # pytest + data-quality checks
└── docs/                    # runbooks, office deployment, demo script
```

---

## 8. DATA CONTRACT (the plug-and-play boundary)

Bank supplies (CSV/parquet daily to `landing/`, or DB link at office). Adapter `data_contracts/mapping.yaml` maps bank column names → canonical. `validator.py` blocks the pipeline with a clear report if contract is violated.

| # | Input table | Grain | Key fields (canonical) |
|---|---|---|---|
| 1 | `in_account_master` | account | account_id, customer_id, product_type, asset_desc, disbursal_date, disbursal_amt, tenure_m, roi, emi_amt, cycle_day, branch, state, city, pincode, status |
| 2 | `in_customer_master` | customer | customer_id, name, dob, segment (FTB/SRTO/MRTO/LRTO/captive), lang_pref, addr, pincode, geo_lat/lon (opt) |
| 3 | `in_contacts` | customer×phone | phone, type, is_primary, dnc_flag, last_verified |
| 4 | `in_emi_schedule` | account×installment | inst_no, due_date, emi_amt, principal, interest |
| 5 | `in_presentations` | presentation | account_id, present_date, amount, status(S/B), bounce_reason |
| 6 | `in_payments` | payment txn | account_id, pay_date, amount, mode, alloc_to_inst |
| 7 | `in_dpd_snapshot` (daily) | account×day | date, dpd, bucket, overdue_amt, pos, total_dues |
| 8 | `in_agent_roster` | agent | agent_id, name, role(FOS/TC/TL/ACM/RCM), team_id, supervisor_id, base_pincode, langs, capacity_override, active |
| 9 | `in_call_logs` (optional hist) | call | for backtesting models |
| 10 | `in_visit_logs` (optional hist) | visit | for backtesting |

History requirement: ≥18–24 months of 4,5,6,7 for model training (synthetic provides 24).

---

## 9. CANONICAL DB SCHEMA (PostgreSQL; migrations in `infra/migrations/`)

- **Dims**: `dim_customer`, `dim_account`, `dim_agent` (SCD-lite with `valid_from/to`), `dim_team`, `dim_geo` (pincode→city/state/zone).
- **Facts**: `fct_presentations`, `fct_payments`, `fct_bounces`, `fct_calls` (channel=bot/human; disposition codes §15.4), `fct_visits`, `fct_ptp` (ptp_id, account, made_by, channel, promise_date, amount, status open/kept/broken/partial), `fct_sms`.
- **`mart_account_daily`** — heart of system. One row/account/day: date, dpd, bucket, overdue_amt, pos, dues, emi_amt, cycle_day, **scores** (bounce_p, selfcure_p, rollfwd_p, propensity, best_slot), **treatment_code**, **owner_agent_id**, ptp_open flag, last_contact, next_action, next_action_date. **Partitioned by month.** Dev retention: 13 months (~118M rows full-scale; ~30 GB).
- **Ops tables**: `campaigns`, `campaign_targets`, `call_queue` (status new→queued→in_call→done; priority; slot), `beat_plan` (agent×date×ordered stops), `allocations` (account×month×owner + reason), `dispositions` (append-only), `interventions`, `scorecard_daily` (entity_type agent/tl/acm/zone × date × metrics jsonb), `sms_outbox`, `payment_links`, `audit_log` (append-only), `users` (roles: admin/strategy/tl/acm/agent/auditor).
- **Registry**: `model_registry` (model, version, trained_on, auc, psi, path), `score_history` (for drift).

Naming: snake_case; every table has `created_at`; no deletes on facts (soft-flag only).

---

## 10. SYNTHETIC BANK GENERATOR (`synthgen/`) — makes the Mac a full bank

Parameterized by `.env` (`N_ACCOUNTS=300000`, `SMALL_MODE=1` → 30k for fast iteration; `HISTORY_MONTHS=24`; `SEED=42`).

1. **Portfolio**: product mix (HCV 22%, LCV 28%, Tipper 15%, Tractor 18%, CE 17%); ticket/tenure/ROI by product; disbursal dates spread over 5 years; cycle_day ∈ {1,5,10,15}; realistic Indian geo distribution (weighted states: UP/MH/RJ/MP/TN/GJ…, valid-format pincodes), names via `faker` (hi_IN/en_IN), phones, languages by state.
2. **Behavioral archetypes** (hidden truth the models must rediscover): prime 55% (bounce ~4%), sporadic 25% (~18%), stressed 12% (~35%), chronic 6% (~55%), strategic 2% (~65%, ignores contact). Seasonality multipliers: monsoon ×1.3 for tipper/CE bounce; harvest ×0.8 tractors (Oct–Nov, Mar–Apr); regional shocks (e.g., mining-ban district-months ×1.5) to give the interventions engine something to find.
3. **History simulation** (month by month, 24 months): presentations → bounce draw → within-month payment/cure draw → DPD/bucket evolution via archetype-specific monthly Markov transitions; contact effects (a simulated call/visit lifts cure prob — creates real uplift for models & §19.3); PTPs made/kept per archetype; generates `in_*` files exactly per §8 contract — **synthgen is also the contract's reference implementation**.
4. **Roster**: 1,500 FOS + 300 TCs + hierarchy per §4.2, geo-anchored to portfolio density.
5. **Daily delta mode**: after seeding, `synthgen --tick` simulates "today's" file drop (new presentations, payments, bounce outcomes influenced by yesterday's actual system actions — closing the loop so the demo shows cause→effect).

Acceptance: full-scale seed ≤ ~30 min on M4; aggregate bounce 10–14%; bucket distribution realistic (B1 ~6%, B2 ~2.5%, B3 ~1.5%, 90+ ~3% of book).

---

## 11. DAILY PIPELINE (Dagster; the heartbeat — `make daily` runs it all)

| Order | Asset/job | ~When (office) |
|---|---|---|
| 1 | Ingest landing files (or synth `--tick`) + contract validation + DQ checks (row counts, nulls, dupes, drift) | 06:00 |
| 2 | dbt build: staging → facts/dims → `mart_account_daily` (today's partition) | 06:30 |
| 3 | Score all due/overdue accounts (bounce, self-cure, roll, best-slot) — LightGBM batch, 3L rows in seconds | 07:00 |
| 4 | Treatment engine → `treatment_code` per account (§13) | 07:10 |
| 5 | Allocation engine → owners, `beat_plan`, capacity check (§14) | 07:20 |
| 6 | Campaign builder → `call_queue` (bot & human, slotted 08:00–19:00), `sms_outbox`, PTP-reminder queue | 07:30 |
| 7 | Intraday: bot runs queue (simulator on Mac), consoles capture dispositions/payments; queue re-prioritizes hourly (self-cured/paid accounts auto-dropped) | 08:00–19:00 |
| 8 | EOD: scorecards (§19.2), uplift refresh (§19.3), interventions + LLM daily brief (§20), next-day previews | 20:00 |
| 9 | Weekly: model monitoring (AUC/PSI); monthly: retrain + champion/challenger (§12.4) | — |

Idempotent per date; `make daily DATE=...` supports replay/backfill. On Mac, "a day" runs in minutes → can simulate a month in an evening.

---

## 12. ML MODELS (`models_ml/`; all LightGBM unless noted)

| Model | Predicts | Scored when | Target AUC | Key features |
|---|---|---|---|---|
| **M1 Bounce** | P(EMI presentation bounces) | Daily, D-7→D-1 pre-cycle | 0.78–0.85 | 3/6/12-mo bounce & payment-delay history, days-to-clear distribution, DPD trajectory, product, geo, seasonality, vintage, ticket, arrears |
| **M2 Self-cure** | P(pays within 7d with zero touch) | On bounce | 0.75+ | Historical self-cure, bounce reason, payday patterns, balance-to-EMI |
| **M3 Roll-forward** | P(bucket → next bucket at month-end) | Daily for B1–B3 | 0.75+ | Payments-to-demand ratio, contact outcomes, PTP history, macro-geo stress |
| **M4 Best-time-to-call** | Best 2h slot | Weekly | heuristic v1 (hist. connect-rate by slot), model v2 | connect logs |
| **M5 Deep propensity** | P(any payment in 30d), B3+/NPA | Weekly | 0.72+ | Long-horizon behavior, settlements — feeds agency/legal triage |
| **M6 Difficulty index** | Expected resolution of an allocation book (for fair scorecards §19.2) | Monthly | calibration | Book mix of scores |

Standards: time-based train/valid split (no leakage; features as-of scoring date), SHAP global+per-account (top-3 reasons stored → shown on collector insight cards), calibrated probabilities (isotonic), `model_registry` versioning, monthly PSI/AUC monitoring with auto-flag to §20, retrain monthly with champion/challenger. Training on 24-mo synthetic full-scale: minutes on M4.

---

## 13. TREATMENT STRATEGY ENGINE (`strategy/treatment.py`; rules in versioned YAML)

Deterministic, auditable matrix: **(bucket, risk band, value band, events)** → treatment path + cadence. Illustrative v1:

| Segment | Treatment |
|---|---|
| Pre-due, bounce_p < 0.10 | SMS D-3 only (cost-free base) |
| Pre-due, 0.10–0.35 | Bot call D-3 + SMS D-1 |
| Pre-due, > 0.35 | Bot D-4 + telecaller D-2 + SMS D-1; >0.6 & high-value → TL review list |
| Bounced, selfcure_p > 0.7 | **Suppress 5 days** (save capacity), SMS nudge only, auto-verify cure |
| Bounced, mid risk | Bot day-1 → if no PTP, telecaller day-2/3 → field if >₹25k dues & no contact by day-5 |
| Bounced, high risk / broken-PTP / non-contact | Telecaller day-1 + field within 72h, TL visibility |
| B2/B3 | Field-led with weekly telecaller support; PTP-centric cadence |
| 90+ | M5-ranked: field hard-collect vs settlement review vs legal/agency flag |
| Any PTP made | Freeze other touches; reminder D-1; on broken → escalate one level |

Guardrails encoded: max 2 calls + 1 visit attempt/day/account, contact only 08:00–19:00, DNC respected, 48h cool-off after RPC unless PTP event, script IDs mandatory per treatment (audit).

---

## 14. ALLOCATION ENGINE (`strategy/allocation.py`)

- **Monthly base allocation** (cycle start): assign every actionable account an owner. v1 greedy with hard/soft constraints; v2 OR-Tools CP-SAT.
  - Hard: geography (FOS pincode-cluster beats), capacity (FOS 40–70/day equiv., TC 200–250 dials/day from `capacity.yaml`), language match, role↔bucket eligibility.
  - Soft (weighted): agent skill-score on similar segments (from §19.2 history), continuity (same owner as last month if performing), fairness (difficulty index §12-M6 balanced across agents — enables honest scorecards), travel minimization (haversine within beat).
- **Daily re-balance**: absences → redistribute within team; new bounces → owner per treatment; TL manual override in ops console (logged with reason to `audit_log`).
- Outputs: `allocations` (+`alloc_reason` for transparency), `beat_plan` (ordered stops/day with account insight cards §17).

---

## 15. CAMPAIGNS & CALLING OPS (`campaigns/`)

1. **Campaign types**: PRE_DUE (D-4→D-1 waves), POST_BOUNCE (day-0→7), PTP_REMINDER (D-1), BROKEN_PTP, EARLY_BUCKET (B1), FIELD_SUPPORT (appointment setting).
2. **Queue builder** slots targets into `call_queue` honoring best-time (M4), 08:00–19:00, channel capacity, priority = expected-₹-recovery × urgency. Auto-drops paid/cured hourly.
3. **Control groups**: every campaign holds out a random 5% (stratified by risk) — enables true **uplift** measurement (§19.3). This is the "impact of calling" answer.
4. **Disposition taxonomy** (both bot & human; closed list): CONNECT_RPC, CONNECT_TPC, PTP(date,amt,mode), PAID_CLAIM, DISPUTE, HARDSHIP(reason), NOT_INTERESTED, WRONG_NO, NO_ANSWER, SWITCHED_OFF, CALLBACK(slot), DNC_REQUEST, LANG_SWITCH. Field adds: VISIT_MET / VISIT_NOT_FOUND / ADDRESS_ISSUE / COLLECTED(mode, ref).
5. **Telecaller console** (in ops console v1): next-call screen with customer insight card (dues, history sparkline, top-3 SHAP reasons, last dispositions, recommended script + PTP ask), one-click dispositions, PTP capture with validation.

---

## 16. AI VOICE BOT (`bot/`) — free, local, honest

### 16.1 Components
- **STT**: faster-whisper `small` int8 (upgrade `medium` if RAM allows) — streaming chunks, hi/en/Hinglish.
- **Brain**: finite-state dialog engine (deterministic, auditable) + Ollama qwen2.5-7B **only** for NLU slot-filling/intent within the active state (JSON-constrained). LLM never free-generates compliance-sensitive content.
- **TTS**: **prompt-bank hybrid** — all fixed script lines pre-rendered once per language/voice (Piper hi/en; optional AI4Bharat Parler for better Hindi); only dynamic slots (name, ₹ amount, dates) synthesized live and stitched with ffmpeg. → ~0.2s responses, tiny CPU per call, scales to 50+ concurrent lines on one office server, zero cost.
- **Flows (YAML)**: `pre_due_reminder`, `post_bounce_ptp`, `ptp_reminder`, `visit_confirm`. Skeleton: greet → identity verify (soft: confirm name/vehicle) → **recording disclosure** → purpose → listen/intent → negotiate within guardrails (max 2 asks, offer date window ≤7d, no threats — fixed phrasing) → capture PTP/dispute/hardship → UPI-link mention (sms_outbox) → close → write disposition + full transcript.
- **Escalation**: low ASR confidence ×2, anger/dispute/hardship intents, or user asks human → mark CALLBACK for telecaller (office: warm transfer via dialer).

### 16.2 Mac testing (no telephony, fully free)
- **Web tester**: FastAPI + WebSocket page — talk to the bot with the Mac mic end-to-end (STT→state→TTS) for live demos.
- **Call simulator**: replays the day's `call_queue` against *synthetic customer personas* (LLM-played, archetype-conditioned: cooperative/evasive/disputing/hardship) → produces realistic dispositions, PTPs, transcripts at volume → downstream analytics/scorecards light up without a single real call. Persona answer-probability calibrated to connect rates.
- **QA loop**: nightly sample 2% transcripts → local LLM rubric-scores (script adherence, disclosure present, tone) → `bot_qa` table → dashboard + intervention on failures.

### 16.3 Office path
FreeSWITCH (OSS) + bank SIP trunk (mod_audio_fork ↔ bot websocket), or simpler v1: push bot-eligible lists to the bank's existing dialer and ingest its disposition file — both supported by design (`bot/telephony_adapter.py` interface).

---

## 17. FIELD AGENT PWA (`apps/field_pwa/`; React+Vite, installable, Hindi/English UI)

Screens: **Login** (JWT) → **My Day** (beat plan: ordered stops, map links, priority badges, expected collection) → **Account card** (dues, EMI history sparkline, bounce reasons, PTP history, top-3 risk reasons in plain words, scripts/do's-don'ts, call buttons) → **Action capture** (visit disposition, ₹ collected + mode + receipt no., PTP with date/amount validation, geo-stamp + timestamp, optional photo) → **My scorecard** (rank in team, streaks) → **TL view** (team live progress, exception list).
Offline-first: IndexedDB queue, sync on network; conflict = server wins + flag. All writes → `dispositions`/`fct_visits`/`fct_ptp` via API. Mac testing: Safari/Chrome mobile-view + `npx serve` on LAN to a real phone.

---

## 18. OPS CONSOLE (`apps/ops_console/`; Streamlit; roles: strategy/TL/admin)

Pages: Command Center (today's demand, queue burn-down, live resolution vs target, bot/TC/field split) · Campaign Manager (create/pause, cadence editor, control-group %, preview counts) · Queue Monitor · Allocation Review (capacity heatmap, overrides with reason) · PTP Book (aging, due-today, broken) · Bot QA (transcripts, scores, listen to audio) · Payments (mark-paid for dev) · Model Health (AUC/PSI trends) · User/team admin.

---

## 19. DASHBOARDS & SCORECARDS (`bi/`; Metabase OSS auto-provisioned via API bootstrap script)

### 19.1 Dashboards
1. **Portfolio Command** — demand, bounce%, resolution% by bucket/product/zone (DoD/MoM), flows X→1, roll matrix, ₹ efficiency, NPA movement.
2. **Calling Ops** — attempts/connects/RPC/PTP by channel & campaign, slot heatmaps, bot containment, queue SLAs.
3. **Field Ops** — visits, strike rate, collections by mode, beat adherence, geo heatmap.
4. **Performance** — leaderboards agent/TL/ACM/zone (difficulty-adjusted), trends, bottom-decile watchlist.
5. **Impact** — uplift per campaign (treated vs control): bounce-rate delta (pre-due), cure-rate delta (post-due), ₹/call, ₹/visit.
6. **Risk & Early Warning** — score distributions, drift, geo/segment stress map, emerging-pocket list.

### 19.2 Scorecards (daily, `scorecard_daily`)
Agent composite per §5 with **difficulty adjustment**: actual resolution ÷ expected resolution given allocated book's score mix (M6) → fair comparison; TL/ACM/zone = weighted roll-ups + span metrics (coverage, override rate, QA). Published to PWA & Metabase; weekly PDF-style summary via LLM → `docs/briefs/`.

### 19.3 Impact measurement (the "does calling work?" answer)
Persistent 5% stratified holdouts per campaign type (§15.3) → daily diff-in-means with CIs on bounce/cure/₹; monthly readout auto-written into the business brief. Synthgen's built-in contact-effect (§10.3) guarantees the demo shows real, recoverable uplift.

### 19.4 Interventions engine (`insights/`)
Rule sensors over marts, e.g.: segment/geo roll-forward ↑ >2pp MoM · bounce spike in pocket (state×product) · agent < P10 for 2 weeks (difficulty-adjusted) · TL override-rate anomaly · PTP-kept crash on a campaign · model PSI breach · queue SLA miss · bot containment drop. Each fires an `interventions` row: severity, owner-role, evidence query, recommended action (playbook library), SLA, status (open→acked→resolved) — **assignment with ownership, not just a chart**. Daily **LLM Morning Brief** (qwen, from computed numbers only — no invented figures): "Top 5 things collections leadership should act on today", written to dashboard + `docs/briefs/YYYY-MM-DD.md`.

---

## 20. (merged into §19.4 above — interventions & insights)

## 21. API SURFACE (FastAPI `/api/v1`; JWT; OpenAPI auto-docs)

`auth/login` · `accounts/{id}` (card incl. reasons) · `accounts/{id}/history` · `queues/next?agent=` · `dispositions` POST (validated taxonomy) · `ptp` POST/GET (book) · `payments` POST (dev) · `beatplan/{agent}/{date}` · `scorecards/{entity}/{date}` · `campaigns` CRUD · `interventions` GET/PATCH · `bot/session` WS (web tester) · `admin/*`. Rate-limited; all mutations → `audit_log`.

## 22. NON-FUNCTIONALS

**22.1 Scale**: 3L accounts scoring <1 min; mart daily partition build <5 min (M4, full mode); Metabase queries on indexed marts <3s. Postgres partitioning + BRIN/date indexes; monthly partitions dropped past retention.
**22.2 Office runtime sizing** (docs/deployment): 16 vCPU/64 GB/1 TB VM handles data+ML+apps for 3L×daily; voice concurrency separate box — hybrid-TTS design ≈ 1 vCPU per live call → 32–64 vCPU for 30–50 lines (or one mid GPU).
**22.3 Mac 16 GB budget**: Postgres 2 GB cap, Metabase 1.5 GB, Ollama 7B-q4 ~5 GB (load on demand), whisper small ~1 GB. Never run PWA build + simulator + Metabase simultaneously in full mode; `SMALL_MODE=1` for daily dev.
**22.4 Security/compliance**: JWT + role-scoped PII masking (auditor sees masked); append-only `audit_log` & `dispositions`; contact-window/DNC enforced at queue level (cannot be bypassed by UI); recording-disclosure state mandatory in every flow; retention config; DPDP-aligned purpose tags on tables; model governance file per model (owner, version, monitoring) — makes the bank conversation easy.
**22.5 Quality**: pytest suites per module; dbt tests (uniqueness, accepted values, freshness); DQ gate blocks pipeline on contract breach; `make test` green = releasable; GitHub Actions CI (free tier) runs lint+tests on push.

---

## 23. BUILD ROADMAP — 15 scoped Claude Code sessions

> **Token strategy**: one session = one scope; start every session with the §0 opener; `/clear` between sessions; **Haiku** for scaffold/CRUD sessions (S0,S1,S8,S9 setup parts), **Sonnet** for logic-heavy (S2–S7,S10–S15); no subagents; commit at every green checkpoint; STATE.md updated at end. If a session overruns, stop at last green commit and note remainder in STATE.md.

- [ ] **S0 — Environment** (Haiku, ~30 min): run §24 installs; verify `docker ps`, `ollama run qwen2.5:7b-instruct-q4_K_M "hi"`, `psql` client; record versions in STATE.md.
- [ ] **S1 — Scaffold** (Haiku): git init + `gh repo create collections-os --private`; repo tree §7; docker-compose (postgres+metabase); Makefile; .env; migrations 001–010 (§9); `make up` green; create STATE.md.
- [ ] **S2 — Synthgen core** (Sonnet): §10.1–.2 + roster; contract writer + validator; SMALL_MODE seed loads to Postgres.
- [ ] **S3 — Synthgen history** (Sonnet): §10.3 24-mo simulation + `--tick`; full-scale seed benchmark; acceptance stats printed.
- [ ] **S4 — dbt marts + Dagster** (Sonnet): staging/facts/dims/`mart_account_daily`; dbt tests; Dagster assets steps 1–2; `make daily` (data part) idempotent.
- [ ] **S5 — Models** (Sonnet): M1–M3 (+M4 heuristic, M6): train, calibrate, SHAP, registry, batch scorer into mart; report AUCs in STATE.md.
- [ ] **S6 — Treatment + queues** (Sonnet): §13 YAML engine, §15 queue builder + control groups + disposition taxonomy + guardrails; pipeline steps 3–6 wired.
- [ ] **S7 — Allocation** (Sonnet): §14 v1 greedy + capacity + beat plans + daily rebalance; allocation-reason transparency.
- [ ] **S8 — API** (Haiku scaffold + Sonnet auth/logic): §21 endpoints + JWT roles + audit; pytest API suite.
- [ ] **S9 — BI bootstrap** (Haiku): Metabase API provisioning; dashboards 1–3 (§19.1) from `bi/*.sql`.
- [ ] **S10 — Ops console** (Sonnet): §18 pages incl. telecaller next-call screen; mark-paid dev flow.
- [ ] **S11 — Bot core** (Sonnet): STT/TTS wrappers, prompt-bank builder, state engine + `post_bounce_ptp` + `pre_due_reminder` flows, web mic tester working E2E.
- [ ] **S12 — Bot at volume** (Sonnet): §16.2 simulator + personas; run a full day's queue; dispositions/PTPs flow to marts; QA rubric job; dashboards 2 & 5 light up.
- [ ] **S13 — Field PWA** (Sonnet): §17 v1 (login→my day→account card→capture→sync); test from phone on LAN.
- [ ] **S14 — Scorecards + Impact + Interventions** (Sonnet): §19.2–19.4 incl. LLM brief; dashboards 4–6.
- [ ] **S15 — E2E demo + hardening** (Sonnet): `make demo` = seed → simulate 30 days (tick+daily+simulator loop) → all dashboards populated → live bot mic call → PWA capture → next-day scorecard reflects it; fix gaps; write `docs/demo_script.md`, `docs/deployment_office.md`; tag v1.0.

**Definition of done (v1)** = §27 acceptance list all green via `make demo`.

## 24. SETUP CHECKLIST (Session 0 — run once; ~15 min + downloads)

```bash
brew install colima docker docker-compose libpq node@20 ffmpeg ollama
colima start --cpu 4 --memory 6 --disk 40        # OSS container runtime
brew services start ollama && ollama pull qwen2.5:7b-instruct-q4_K_M
pip install fastapi "uvicorn[standard]" sqlalchemy psycopg2-binary alembic \
  lightgbm scikit-learn shap dagster dagster-webserver dbt-core dbt-postgres \
  faster-whisper piper-tts streamlit ortools faker pyjwt pytest httpx pyarrow
# repo bootstrap happens in Session 1 (docker compose up -d: postgres:16, metabase)
```

## 25. OFFICE (KOTAK) PATH — realistic sequence

1. **Never** connect office data to personal machine/cloud. Demo on Mac with synthetic (that's its purpose).
2. Pitch with `make demo` + this PLAN → sponsor: Collections strategy head; partners: analytics + IT security.
3. Ask IT for: an on-prem VM (§22.2), daily read-only extracts per §8 (SFTP CSV is enough), SMS-gateway API creds, dialer list-in/disposition-out spec, AD/SSO details, SMTP.
4. Deploy same compose images; fill `data_contracts/mapping.yaml` against their column names; run validator on first drop; backfill 18–24 mo history; retrain models on real data (expect different AUCs).
5. Security review pack is pre-written by design: OSS licenses list, no-egress architecture, audit log, PII masking, model governance files, RBI-guardrail code pointers.
6. Phase in: shadow mode (2 wk, system recommends/humans decide) → assisted (queues live, bot on pilot slice with control groups) → scaled (bot volume, full allocation) — uplift dashboard justifies each step.
7. Voice: v1 via their existing dialer file-handoff; v2 FreeSWITCH+SIP for the local bot.

## 26. HONEST LIMITATIONS

Real PSTN calls & SMS need bank telecom (software free; pipe isn't) · a 16 GB Mac demos everything but won't serve 1,500 concurrent users (that's the office VM's job; code is identical) · local 7B LLM < frontier models — mitigated by state-machine design (LLM only slot-fills) · open-source Hindi TTS is good-not-perfect (prompt-bank hybrid keeps fixed lines studio-consistent; AI4Bharat upgrade path) · Metabase OSS lacks row-level SSO perms (mitigate: role-scoped SQL views) · synthetic data proves plumbing & process, not real-world model lift — real AUCs come at office · legal/repo module out of v1 scope (flags only).

## 27. ACCEPTANCE TESTS (v1 done = all pass on Mac, full mode)

1. `make up && make seed` — 3,00,000 accounts, 24-mo history, stats within §10 ranges.
2. `make daily` — completes < 20 min full-scale; idempotent on re-run.
3. Every due account today has: scores + treatment + owner + next action (0 orphans — SQL check).
4. Queues respect 08:00–19:00, DNC, caps (property tests).
5. Bot web-tester: live mic call in Hinglish captures a valid PTP → visible in ops console + `fct_ptp` ≤ 5s.
6. Simulator day: ≥ 95% queue processed; dispositions distribution sane; dashboards 1–6 populated.
7. PWA on phone: field disposition + ₹ capture syncs offline→online; appears in TL view.
8. EOD: scorecards for all 1,800+ agents; leaderboard renders < 3s.
9. Uplift report shows synthetic contact-effect recovered with CIs excluding zero.
10. Interventions list ≥ 3 real findings (seeded shocks found); LLM brief cites only real computed numbers.
11. `make test` — all pytest + dbt tests green. 12. `make demo` chains 1→11 unattended.

## 28. GLOSSARY
DPD (days past due) · NACH (mandate-based debit) · PTP (promise to pay) · RPC/TPC (right/third-party contact) · FOS (field officer) · POS (principal outstanding) · SRTO/MRTO/LRTO (small/medium/large road transport operator) · X-bucket (0 DPD post-bounce) · Containment (bot resolves without human) · Beat (field agent's geographic daily route).

---
*End of PLAN.md — next step: open a fresh session in `collections-os/` and run Session 0 (§23/§24).*
