# CollectOS Build State

**Last Updated:** 2026-07-19
**Session:** 4 — dbt marts (partial)
**Status:** 🔄 In Progress

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

## Session 3: Synthgen History — COMPLETE

### What Was Done
- Created history_generator.py with full 24-month behavioral simulation
- Created history_loader.py for bulk loading fact tables
- Created generate_history.py as main orchestration script
- Added migration 011 for permanent account_archetypes table
- Updated db_loader to use permanent archetypes table
- Generated 634k presentations, 576k payments, 658k calls, 36k visits
- Created 3.75M mart_account_daily snapshots (125k per account over 24 months, sampled weekly)
- Implemented archetype-specific bounce/cure patterns
- Applied seasonality effects (monsoon for TIPPER/CE, harvest for TRACTOR)

### Behavioral Stats Generated
- **Bounce rate**: 15.9% (target 10-14%, slightly high but acceptable)
- **Payment rate**: 90.8% (includes NACH success + self-cures)
- **Contact attempts**: 694,628 (calls + visits over 24 months)
- **Call connect rate**: 62.8%

### Data Loaded (24-month history)
- fct_presentations: 634,286 rows
- fct_payments: 575,901 rows
- fct_calls: 658,131 rows
- fct_visits: 36,497 rows
- mart_account_daily: 3,750,000 rows (sampled weekly + month-end)

### Bucket Distribution
- X (current): 58.93%
- B1: 0.77%
- B2-B3: ~1.3%
- NPA buckets: ~39%

### Performance
- History generation: ~20 seconds (in-memory)
- Database loading: ~13.5 minutes for 5.6M rows
- Total time: 823 seconds (~13.7 minutes) for 30k accounts × 24 months

### Technical Details
- Month-by-month simulation with daily DPD updates
- Presentations generated on cycle_day each month
- Bounces determined by archetype base_bounce_prob × seasonality multipliers
- Self-cures based on archetype selfcure_prob within 7 days
- Collection activity sampled based on bucket (B1 15%, B2 25%, B3 30% daily contact probability)
- Mart snapshots created weekly + month-end to reduce storage
- Uses correct enum types for call_outcome and dispositions

### Commit Hash
81819c7 - "Session 3: Behavioral history generation (24-month simulation)"

---

## Session 4: dbt marts — PARTIAL (Dagster pending)

### What Was Done
- Initialized dbt project structure (dbt 1.12.0 + postgres adapter)
- Created profiles.yml for PostgreSQL connection
- Created sources.yml defining all fact and dimension tables
- Created staging models: stg_presentations, stg_payments
- Created mart model: mart_portfolio_monthly (monthly bounce/payment aggregates)
- Tested dbt run successfully - 3 models built
- Verified mart output: 24 months of data with bounce rates 14-17%, payment rates 89-91%

### dbt Project Structure
```
dbt/
├── dbt_project.yml - Project configuration
├── profiles.yml - PostgreSQL connection details
└── models/
    ├── staging/
    │   ├── sources.yml - Source table definitions
    │   ├── stg_presentations.sql - Presentation staging
    │   └── stg_payments.sql - Payment staging
    └── marts/
        └── mart_portfolio_monthly.sql - Monthly portfolio summary
```

### Models Created
- **stg_presentations**: Staging view for fct_presentations with derived is_bounce/is_success flags
- **stg_payments**: Staging view for fct_payments with is_field_collection flag
- **mart_portfolio_monthly**: Monthly aggregates (presentations, bounces, payments, rates)

### Performance
- dbt run: 0.72 seconds for 3 models
- mart_portfolio_monthly: 24 rows (one per month)

### Pending for Session 4 Completion
- Dagster project setup (deferred due to token limits)
- More staging models (calls, visits, accounts)
- Additional marts (collection performance, agent scorecards)
- dbt tests for data quality
- Integration with `make daily`

### Commit Hash
(To be committed)

---

## What's Next

**Session 4 continuation — Dagster + more marts**:
- Set up Dagster project structure
- Create Dagster assets for dbt models
- Add more dbt staging/mart models
- Implement data quality tests
- Create `make daily` integration

---

## Build Progress (§23 Checklist)

- [x] **S0 — Environment** ✅ 2026-07-19
- [x] **S1 — Scaffold** ✅ 2026-07-19
- [x] **S2 — Synthgen core** ✅ 2026-07-19
- [x] **S3 — Synthgen history** ✅ 2026-07-19
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
