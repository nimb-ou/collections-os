# CollectOS

**Complete Collections Operating System for CV/CE Loan Portfolios**

Built over 15 sessions as a comprehensive, production-ready collections platform with ML models, AI voice bot, field PWA, and advanced analytics.

---

## Overview

CollectOS is an end-to-end collections operating system designed for commercial vehicle (CV) and construction equipment (CE) loan portfolios. It combines machine learning, AI-powered automation, field agent management, and advanced analytics to optimize collections performance.

### Key Features

- 🤖 **AI Voice Bot** - Automated voice collections using Ollama Qwen 2.5 7B
- 📊 **ML Risk Scoring** - Bounce and self-cure prediction with LightGBM
- 📱 **Field PWA** - Offline-first mobile app for 1,500+ field agents
- 📈 **Advanced Analytics** - Difficulty-adjusted scorecards, uplift analysis, interventions
- 🎯 **Smart Allocation** - OR-Tools optimization for agent workload balancing
- 📉 **Impact Measurement** - Causal inference for treatment effectiveness
- 🔍 **Real-time Monitoring** - Ops Console with live queue tracking
- 📊 **BI Dashboards** - Metabase OSS for portfolio insights

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Data Layer (PostgreSQL)                   │
│  • Dimensions: Customer, Account, Agent, Team, Geography         │
│  • Facts: Presentations, Payments, Calls, Visits, PTPs, SMS      │
│  • Mart: account_daily (partitioned, 36 monthly partitions)      │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────┼─────────────────────────────────┐
│                  Transformation Layer (dbt)                     │
│  • Staging models: Clean and standardize raw data               │
│  • Mart models: Portfolio monthly, Performance, Scorecards      │
│  • 41 data quality tests                                        │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────┼─────────────────────────────────┐
│                    ML & Strategy Layer                          │
│  • M1: Bounce Prediction (LightGBM + SHAP)                      │
│  • M2: Self-Cure Prediction (LightGBM + SHAP)                   │
│  • Treatment Strategy: Risk segmentation & channel selection    │
│  • Allocation Engine: OR-Tools capacity optimization            │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────┼─────────────────────────────────┐
│                     Execution Layer                             │
│  • Bot: AI voice collections (Whisper STT + Ollama + Piper TTS) │
│  • Field PWA: Offline-first mobile app (React + IndexedDB)      │
│  • API: FastAPI with JWT auth (40+ endpoints)                   │
│  • Ops Console: Streamlit internal tools                        │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────┼─────────────────────────────────┐
│                     Analytics Layer                             │
│  • Scorecards: Difficulty-adjusted performance metrics          │
│  • Impact: Uplift analysis with statistical significance        │
│  • Interventions: Rule-based sensors for escalations            │
│  • Daily Briefs: LLM-powered executive summaries                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- macOS (M-series or Intel)
- 16 GB RAM
- Docker (via Colima)
- Python 3.12+
- Node.js 20+
- PostgreSQL client (libpq)

### Installation

```bash
# 1. Clone repository
git clone https://github.com/nimb-ou/collections-os.git
cd collections-os

# 2. Install dependencies (macOS)
brew install colima docker docker-compose libpq node@20 ffmpeg ollama

# 3. Start container runtime
colima start --cpu 4 --memory 6 --disk 40

# 4. Pull AI model
brew services start ollama
ollama pull qwen2.5:7b-instruct-q4_K_M

# 5. Install Python packages
pip install -r requirements.txt

# 6. Create environment file
make env
# Edit .env with your settings

# 7. Start services
make up

# 8. Seed database (30k accounts, ~2 minutes)
make seed

# 9. Run end-to-end demo
make demo
```

### Access Points

After setup:

- **Metabase BI**: http://localhost:3000
- **Ops Console**: http://localhost:8000/console
- **Bot Tester**: http://localhost:8080
- **API Docs**: http://localhost:8000/docs
- **Database**: localhost:5432 (user: collectos, db: collectos)

---

## Project Structure

```
collections-os/
├── infra/
│   └── migrations/           # PostgreSQL migrations (10 files, 2500+ lines SQL)
├── synthgen/                 # Synthetic data generator
│   ├── config.py             # Product specs, archetype parameters
│   ├── geo_generator.py      # Indian geography (14 states, zones)
│   ├── customer_generator.py # Customer profiles with Faker
│   ├── portfolio_generator.py # Loan accounts with EMI schedules
│   ├── roster_generator.py   # Agent hierarchy (RCM → ACM → TL → FOS/TC)
│   ├── history_generator.py  # 24-month behavioral simulation
│   ├── db_loader.py          # PostgreSQL bulk loader
│   └── seed.py               # Main pipeline execution
├── dbt/
│   └── models/
│       ├── staging/          # 5 staging models + 33 tests
│       └── marts/            # 3 mart models + 8 tests
├── models_ml/
│   ├── train/                # LightGBM training pipeline
│   │   ├── m1_bounce.py      # Next-month bounce prediction
│   │   └── m2_selfcure.py    # Self-cure probability
│   └── inference/            # Batch scoring
├── strategy/
│   ├── treatment.py          # Risk segmentation & channel selection
│   └── allocation.py         # OR-Tools capacity optimization
├── api/
│   ├── main.py               # FastAPI application
│   ├── routes/               # 40+ endpoints
│   │   ├── accounts.py       # Account details, history
│   │   ├── agents.py         # Agent roster, assignments
│   │   ├── allocations.py    # Daily allocations
│   │   ├── beatplans.py      # Field beat plans
│   │   ├── dispositions.py   # Call/visit outcomes
│   │   ├── payments.py       # Payment capture
│   │   └── scorecards.py     # Performance metrics
│   └── auth.py               # JWT authentication
├── bot/
│   ├── core/                 # Voice bot engine
│   │   ├── stt.py            # Speech-to-text (Whisper)
│   │   ├── tts.py            # Text-to-speech (Piper)
│   │   ├── llm.py            # LLM dialogue (Ollama Qwen)
│   │   └── pipeline engine.py   # Call flow pipeline execution
│   ├── simulator/            # Automated testing
│   │   ├── personas.py       # 5 behavioral customer types
│   │   ├── persona_responses.py # LLM-driven responses
│   │   ├── simulator.py      # Bot-persona conversation
│   │   ├── batch_processor.py # Queue processing
│   │   ├── qa_rubric.py      # Compliance scoring
│   │   └── create_test_queue.py
│   └── web_tester/           # Browser-based bot interface
│       └── app_audio.py      # Streamlit audio UI
├── apps/
│   └── field_pwa/            # Field agent PWA
│       ├── package.json      # React 18, React Router, IndexedDB
│       └── README.md         # 6 screens, offline architecture
├── ops_console/              # Internal Streamlit tools
│   ├── app.py                # Main console
│   ├── pages/                # 6 pages
│   │   ├── 1_portfolio.py    # Portfolio overview
│   │   ├── 2_agents.py       # Agent roster
│   │   ├── 3_allocations.py  # Daily allocations
│   │   ├── 4_queues.py       # Call queues (live monitoring)
│   │   ├── 5_campaigns.py    # SMS campaigns
│   │   └── 6_beatplans.py    # Field beat plans
│   └── utils.py
├── insights/                 # Advanced analytics
│   ├── scorecards.py         # Difficulty-adjusted performance
│   ├── impact.py             # Uplift analysis (causal inference)
│   ├── interventions.py      # Rule-based escalation sensors
│   └── daily_brief.py        # LLM-powered executive summaries
├── scripts/
│   └── demo.py               # End-to-end demonstration
├── docker-compose.yml        # PostgreSQL 16 + Metabase
├── Makefile                  # 20+ targets (up/down/seed/daily/demo/test)
├── .env.example              # 100+ configuration parameters
├── STATE.md                  # Detailed build log (all 15 sessions)
├── PLAN.md                   # Original 15-session plan
└── README.md                 # This file
```

---

## Usage

### Daily Workflow

```bash
# Morning: Start services
make up

# Run daily pipeline (dbt transforms + ML scoring)
make daily

# Check portfolio status
psql -h localhost -U collectos -d collectos -c "
  SELECT bucket, COUNT(*), SUM(overdue_amt) FROM mart_account_daily
  WHERE date = CURRENT_DATE GROUP BY bucket ORDER BY bucket;"

# View allocations in Ops Console
# http://localhost:8000/console

# Process bot call queue
python -m bot.simulator.batch_processor

# Calculate scorecards
python -m insights.scorecards

# Detect interventions
python -m insights.interventions

# Generate daily brief
python -m insights.daily_brief
```

### ML Model Training

```bash
# Train bounce prediction model (M1)
python -m models_ml.train.m1_bounce

# Train self-cure prediction model (M2)
python -m models_ml.train.m2_selfcure

# Run batch inference
python -m models_ml.inference.batch_score --date 2026-07-19
```

### Bot Operations

```bash
# Test bot interactively
cd bot/web_tester
python app_audio.py
# Open http://localhost:8080

# Create test queue
python -m bot.simulator.create_test_queue

# Run batch simulation
python -m bot.simulator.batch_processor

# View QA scores
psql -h localhost -U collectos -d collectos -c "
  SELECT * FROM bot_qa ORDER BY created_at DESC LIMIT 10;"
```

### Analytics

```bash
# Calculate scorecards for specific date
python -m insights.scorecards 2026-07-19

# Run impact analysis (30-day window)
python -m insights.impact 2026-06-19 2026-07-19

# Detect interventions
python -m insights.interventions 2026-07-19

# Generate daily brief (with LLM)
python -m insights.daily_brief 2026-07-19

# Generate daily brief (without LLM, template)
python -m insights.daily_brief 2026-07-19 --no-llm
```

---

## Makefile Commands

```bash
make help          # Show all available commands
make env           # Create .env from template
make up            # Start all services (postgres + metabase)
make down          # Stop all services
make logs          # Tail logs from all services
make ps            # Show running containers
make db-shell      # Open psql shell

make seed          # Generate synthetic data (30k accounts in SMALL_MODE)
make daily         # Run daily pipeline (dbt run + dbt test)
make demo          # Run end-to-end demonstration
make test          # Run all tests (dbt + pytest)

make clean         # Clean temporary files and caches
make status        # Show status of services
make health        # Check health of all services
make info          # Show environment info
```

---

## Configuration

### Environment Variables (.env)

Key settings:

```bash
# Mode
SMALL_MODE=1                    # 1=30k accounts, 0=300k accounts

# Database
POSTGRES_USER=collectos
POSTGRES_PASSWORD=changeme
POSTGRES_DB=collectos
POSTGRES_PORT=5432

# API
API_HOST=0.0.0.0
API_PORT=8000
JWT_SECRET=your-secret-key-here

# Ollama (AI)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b-instruct-q4_K_M

# Metabase
METABASE_PORT=3000
```

See `.env.example` for all 100+ parameters.

---

## Key Concepts

### Behavioral Archetypes

CollectOS uses 5 hidden behavioral archetypes to simulate realistic portfolio behavior:

1. **PRIME** (55%): Low bounce, high self-cure - disciplined payers
2. **SPORADIC** (25%): Moderate bounce, moderate self-cure - inconsistent
3. **STRESSED** (12%): High bounce, low self-cure - financial hardship
4. **CHRONIC** (6%): Very high bounce, very low self-cure - persistent defaulters
5. **STRATEGIC** (2%): Intentional delays - can pay but won't

These archetypes are hidden from the ML models, which must discover patterns independently.

### Difficulty-Adjusted Scorecards

Agent performance scored on 5 components, adjusted for book difficulty:

```
Composite Score =
  40% × Resolution (difficulty-adjusted)
+ 25% × Collection Efficiency (₹)
+ 15% × PTP-kept Rate
+ 10% × Activity Compliance
+ 10% × Quality Metrics
```

Difficulty adjustment:
```python
expected_resolution = 0.30 + (selfcure_prob × 0.20) + ((1 - bounce_risk) × 0.15)
resolution_score = (actual_resolved / expected_resolved) × 100
```

### Intervention Sensors

6 rule-based sensors detect accounts needing escalation:

1. **Broken PTP Streak**: 3+ broken PTPs → TL Call
2. **High Value Stuck**: ₹50K+, 30+ DPD, no payment → ACM Escalation
3. **Dispute Escalation**: 2+ disputes → Hardship Review
4. **Self-Cure Risk**: Low selfcure_p, high bounce_p → Field Urgent
5. **Legal Trigger**: 90+ DPD, ₹100K+ → Legal Notice
6. **Settlement Opportunity**: 60+ DPD, partial payments → Settlement Offer

---

## Technical Stack

### Data & Analytics
- **PostgreSQL 16**: Primary database with partitioning, JSONB, full-text search
- **dbt**: Data transformation and quality testing
- **Metabase OSS**: BI dashboards and reporting

### ML & AI
- **LightGBM**: Gradient boosting for bounce/selfcure prediction
- **SHAP**: Model explainability
- **Ollama**: Local LLM inference (Qwen 2.5 7B)
- **Whisper**: Speech-to-text (faster-whisper)
- **Piper**: Text-to-speech

### Application
- **FastAPI**: RESTful API with async support
- **Streamlit**: Internal ops console
- **React 18**: Field PWA frontend
- **JWT**: Authentication
- **OR-Tools**: Optimization

### Infrastructure
- **Docker Compose**: Service pipeline execution
- **Colima**: Container runtime (Docker Desktop alternative)
- **Python 3.12**: Core language
- **Node.js 20**: Frontend tooling

---

## Database Schema Highlights

### Core Tables

**Dimensions** (SCD Type 2):
- `dim_customer`: Customer profiles
- `dim_account`: Loan accounts with product details
- `dim_agent`: Agent roster with hierarchy
- `dim_team`: Team structure
- `dim_geography`: Indian states, cities, zones

**Facts** (append-only):
- `fct_presentations`: Monthly EMI presentations
- `fct_payments`: Actual payments
- `fct_bounces`: NACH bounces
- `fct_calls`: Telecaller + bot calls
- `fct_visits`: Field agent visits
- `fct_ptp`: Promise-to-Pay records
- `fct_sms`: SMS campaign tracking

**Mart** (partitioned by month):
- `mart_account_daily`: Daily account snapshot with ML scores (36 partitions)

**Operational**:
- `call_queue`: Bot call queue with priority scoring
- `allocations`: Daily agent assignments
- `beatplans`: Field visit routes
- `dispositions`: Call/visit outcomes
- `campaigns`: SMS campaign management

**Analytics**:
- `scorecard_daily`: Agent performance metrics
- `interventions`: Escalation triggers
- `daily_briefs`: LLM-generated summaries
- `bot_qa`: Bot quality assessment

---

## Performance

### Scale Targets
- **Accounts**: 30k (SMALL_MODE) or 300k (FULL_MODE)
- **Daily mart updates**: 30k rows (partitioned)
- **Bot throughput**: 1,200 calls/hour (with queue)
- **API latency**: < 200ms p95
- **ML scoring**: < 5 minutes for 30k accounts

### Optimization
- Partitioned mart_account_daily (monthly, 36 partitions)
- Indexed foreign keys and lookups
- Materialized views for hot queries
- dbt incremental models
- Connection pooling (pgbouncer recommended for production)

---

## Testing

### Data Quality (dbt)
```bash
make test
# Runs 41 dbt tests:
# - Not null constraints (15 tests)
# - Unique keys (8 tests)
# - Relationships (12 tests)
# - Accepted values (6 tests)
```

### Bot Quality (QA Rubric)
Automated scoring:
- **Compliance** (40%): Regulatory adherence, prohibited language
- **Quality** (35%): Empathy, clarity, resolution
- **Script** (25%): Greeting, verification, ask, close

Pass threshold: 70+

### Unit Tests (pytest)
```bash
pytest quality/ -v
# Tests for:
# - Synthgen generators
# - ML model inference
# - API endpoints
# - Allocation logic
```

---

## Development

### Adding New Features

1. **Database changes**: Add migration in `infra/migrations/012_*.sql`
2. **API endpoints**: Add route in `api/routes/`
3. **dbt models**: Add in `dbt/models/marts/`
4. **ML models**: Add in `models_ml/train/`
5. **Bot capabilities**: Extend `bot/core/pipeline engine.py`

### Code Style

```bash
make format        # Auto-format with black
make lint          # Run black + mypy checks
```

---

## Troubleshooting

### Database Connection Issues
```bash
# Check if postgres is running
make ps

# Check logs
make logs-postgres

# Restart services
make restart
```

### Bot Not Connecting
```bash
# Check Ollama service
brew services list | grep ollama

# Restart Ollama
brew services restart ollama

# Test model
ollama run qwen2.5:7b-instruct-q4_K_M "Hello"
```

### Memory Issues
```bash
# Switch to SMALL_MODE in .env
SMALL_MODE=1

# Restart colima with more memory
colima stop
colima start --cpu 4 --memory 8 --disk 40
```

### Seed Fails
```bash
# Clean and retry
make down-volumes
make up
make seed
```

---

## Documentation

- **STATE.md**: Detailed build log for all 15 sessions (1,770 lines)
- **PLAN.md**: Original 15-session plan
- **insights/README.md**: Scorecards, impact, interventions, briefs (750 lines)
- **bot/simulator/README.md**: Bot simulator architecture (450 lines)
- **apps/field_pwa/README.md**: Field PWA specification (750 lines)
- **API Docs**: http://localhost:8000/docs (interactive Swagger UI)

---

## License

Open source. Built as demonstration of production-grade collections system architecture.

---

## Credits

**Built by**: Claude Code + Human collaboration
**Sessions**: 15 (S0 through S15)
**Duration**: 1 day (2026-07-19)
**Lines of Code**: ~12,000+ (excluding tests, docs, migrations)
**GitHub**: https://github.com/nimb-ou/collections-os

---

## Roadmap

### Phase 2 (Post v1.0)
- [ ] Real-time dashboards (WebSockets)
- [ ] Mobile app deployment (PWA → App Store)
- [ ] Advanced ML models (deep learning for dialogue)
- [ ] Multi-lender support (white-label)
- [ ] Payment gateway integration (Razorpay, PhonePe)
- [ ] WhatsApp Business API integration
- [ ] Voice biometrics for customer verification
- [ ] Regulatory compliance automation (RBI guidelines)

### Phase 3 (Future)
- [ ] Multi-language support (12+ Indian languages)
- [ ] Computer vision for document verification
- [ ] Predictive routing (optimal agent matching)
- [ ] Real-time fraud detection
- [ ] Customer segmentation (clustering)
- [ ] A/B testing framework
- [ ] Multi-cloud deployment (AWS/GCP/Azure)

---

## Contact

For questions, issues, or contributions, please open an issue on GitHub:
https://github.com/nimb-ou/collections-os/issues

---

**CollectOS** - Complete Collections Operating System
*Built for scale. Designed for impact. Open for all.*
