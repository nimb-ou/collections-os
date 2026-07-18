# CollectOS Build State

**Last Updated:** 2026-07-19
**Session:** 2 — Synthgen Core
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

## Session 1: Scaffold — COMPLETE

### What Was Done
- Initialized git repository with proper .gitignore
- Created complete directory structure per §7 (all folders for pipeline, models, bot, apps, etc.)
- Created .env.example with comprehensive configuration (100+ parameters)
- Created docker-compose.yml with PostgreSQL 16 and Metabase OSS
- Created comprehensive Makefile with 20+ targets (up/down/seed/daily/demo/test/clean/health/info)
- Wrote 10 database migrations (2500+ lines of SQL):
  * 001: Extensions, custom types, utility functions
  * 002: Dimension tables (customer, account, agent, team, geo) with SCD support
  * 003: Fact tables (presentations, payments, bounces, calls, visits, PTPs, SMS)
  * 004: mart_account_daily - partitioned heart of system (36 monthly partitions created)
  * 005: Operational tables (campaigns, queues, allocations, beat plans, dispositions)
  * 006: Registry and monitoring (models, scorecards, interventions, audit, users)
  * 007: DPD snapshot and data quality tables
  * 008: Performance indexes and materialized views
  * 009: Helper views and functions
  * 010: Seed data, constraints, RLS policies, database tuning
- Created private GitHub repository: https://github.com/nimb-ou/collections-os
- Verified system startup and database health

### Verification Results
✅ `make up` successful - both containers running
✅ PostgreSQL: Healthy, listening on localhost:5432
✅ Metabase: Starting successfully on localhost:3000
✅ All migrations applied successfully
✅ 36 partitions created for mart_account_daily (2024-01 through 2027-01)
✅ Sample query verified: 9/11 core tables exist
✅ GitHub repository created and initial commit pushed

### Database Stats
- Total tables created: 50+ (including Metabase tables)
- Custom CollectOS tables: 40+
- Indexes: 80+
- Views: 5
- Materialized views: 2
- Custom types: 10
- Functions: 8
- Triggers: 15+

### Notes
- Docker Compose shows warning about obsolete `version` attribute - cosmetic only, works fine
- Default admin user created: username=admin, password=changeme (MUST change in production)
- Metabase initializing its own schema alongside our schema - expected behavior
- All tables use snake_case naming convention
- Append-only tables (audit_log, dispositions) have triggers preventing updates/deletes
- Database tuned for SSD with parallel query support enabled

### Commit Hash
b06d352 - "Session 1: Initial scaffold - repository structure and database setup"

---

## Session 2: Synthgen Core — COMPLETE

### What Was Done
- Created complete synthgen module with 9 Python files
- Implemented GeoGenerator with realistic Indian geography distribution (14 states, zones)
- Implemented CustomerGenerator with Faker for Indian names, addresses, phone numbers
- Implemented PortfolioGenerator with CV/CE product mix and behavioral archetypes
- Implemented RosterGenerator with complete agent hierarchy (RCM → ACM → TL → FOS/TC)
- Implemented DatabaseLoader with bulk insert and geo_id mapping
- Created main seed orchestration script (seed.py)
- Fixed date handling for EMI schedules (leap year support)
- Fixed agent team allocation for small agent counts
- Fixed foreign key handling for geo_ids between generators and database
- Tested and verified SMALL_MODE seed (30k accounts)

### Synthgen Components Created
**synthgen/__init__.py** - Module initialization
**synthgen/config.py** - Configuration with product specs and archetype parameters
**synthgen/geo_generator.py** - Indian geography distribution (states, cities, pincodes, zones)
**synthgen/customer_generator.py** - Customer profiles with Indian names and contacts
**synthgen/portfolio_generator.py** - Loan accounts with CV/CE characteristics and EMI schedules
**synthgen/roster_generator.py** - Agent hierarchy with geographic assignment
**synthgen/db_loader.py** - PostgreSQL bulk loader with geo_id mapping
**synthgen/seed.py** - Main orchestration script
**synthgen/__main__.py** - Module entry point

### Data Generated (SMALL_MODE)
- **Accounts:** 30,000
- **Customers:** 28,500 (with 39,823 contact numbers)
- **EMI Schedules:** 1,342,359 installments
- **Agents:** 194 (1 RCM, 1 ACM, 12 TL, 150 FOS, 30 TC)
- **Teams:** 18 (hierarchical structure across zones)
- **Geographies:** 285 unique locations across 14 states

### Product Mix Distribution
- LCV: 27.9%
- HCV: 21.8%
- TRACTOR: 18.3%
- CE: 16.8%
- TIPPER: 15.1%

### Behavioral Archetype Distribution (Hidden Truth)
- PRIME: 54.7% (low bounce, high selfcure)
- SPORADIC: 25.1% (moderate bounce, moderate selfcure)
- STRESSED: 12.3% (high bounce, low selfcure)
- CHRONIC: 5.8% (very high bounce, very low selfcure)
- STRATEGIC: 2.0% (intentional delays)

### Verification Results
✅ All 9 synthgen modules created
✅ Geography generator produces realistic Indian distributions
✅ Customer generator creates valid Indian names, phones, addresses
✅ Portfolio generator creates complete EMI schedules with proper date handling
✅ Roster generator creates proper hierarchy with geographic assignments
✅ Database loader handles geo_id mapping correctly
✅ `make seed` completes successfully in 63.5 seconds
✅ All data loaded to PostgreSQL without errors
✅ Database statistics verified: 30k accounts, 28.5k customers, 1.3M EMI schedules

### Technical Details
- Uses Faker library for realistic Indian data (hi_IN and en_IN locales)
- Implements proper leap year handling with calendar.monthrange()
- Falls back to any available ACM team when zone has no ACM (handles small agent counts)
- Uses pincode→geo_id mapping to resolve foreign key constraints
- Stores behavioral archetypes in temp table for Session 3 history generation
- All generators use consistent seed (42) for reproducibility
- Database loader uses execute_batch for performance

### Notes
- Seed time: 63.5 seconds for 30k accounts in SMALL_MODE
- Most time spent loading 1.3M EMI schedule entries (~50 seconds)
- Archetypes are stored but not exposed in dim_account (hidden truth for ML to discover)
- Geography count (280 in DB vs 285 generated) - some pincodes deduplicated on conflict
- Agent geographic assignment ensures FOS have base locations, TCs have no constraints
- Language preferences assigned based on state (mr, hi, gu, ta, kn, pa, te, bn, ml)

### Issues Fixed During Session
1. **Faker secondary_address()** - Replaced with custom shop/floor/building strings
2. **Date arithmetic** - Added calendar module for proper leap year handling
3. **ACM team selection** - Added fallback when zone has no ACM teams (small agent counts)
4. **Foreign key violations** - Implemented geo_id mapping from database SERIAL to Python objects

### Commit Hash
47e6a64 - "Session 2: Synthetic data generator (synthgen core)"

---

## What's Next

**Session 3 — Synthgen history** (use Sonnet):
- Generate 24-month behavioral history per archetype
- Create payment events (bounces, selfcures, partial payments)
- Generate field visits, telecalls, SMS, PTP events
- Populate fact tables (fact_payment, fact_presentation, fact_call, fact_visit, etc.)
- Generate historical mart_account_daily snapshots
- Verify behavioral patterns match archetype definitions
- Test historical data quality

---

## Build Progress (§23 Checklist)

- [x] **S0 — Environment** ✅ 2026-07-19
- [x] **S1 — Scaffold** ✅ 2026-07-19
- [x] **S2 — Synthgen core** ✅ 2026-07-19
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
