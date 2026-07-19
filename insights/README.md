# Insights Package - Session 14

**Purpose**: Scorecards, Impact Measurement, Interventions, and LLM Daily Briefs

## Overview

The insights package provides four critical analytical capabilities for CollectOS:

1. **Scorecards** - Difficulty-adjusted agent performance scoring
2. **Impact Measurement** - Uplift analysis and causal inference
3. **Interventions** - Rule-based sensors for intervention triggers
4. **Daily Briefs** - LLM-powered executive summaries

## 1. Scorecards (`scorecards.py`)

### Purpose
Calculate fair, difficulty-adjusted performance scorecards for agents, TLs, ACMs, and zones.

### Composite Score Formula (§5)
```
Composite Score =
  40% Resolution (difficulty-adjusted)
+ 25% Collection Efficiency (₹)
+ 15% PTP-kept Rate
+ 10% Activity Compliance
+ 10% Quality Metrics
```

### Difficulty Adjustment
Accounts with high bounce risk and low self-cure probability are harder to resolve. The scorecard adjusts expected resolution rates based on:
- `avg_selfcure_prob`: Higher = easier book
- `avg_bounce_risk`: Lower = easier book

```python
expected_resolution_rate = 0.30 + (selfcure_prob * 0.20) + ((1 - bounce_risk) * 0.15)
resolution_score = (actual_resolved / expected_resolved) * 100
```

### Usage
```python
from insights import calculate_daily_scorecards

# Calculate scorecards for today
scorecards = calculate_daily_scorecards()

# Top 5 performers printed automatically
# Saves to scorecard_daily table
```

```bash
# Command line
python -m insights.scorecards 2026-07-19
```

### Output
- Agent scorecards with ranks
- Component scores (resolution, efficiency, PTP, activity, quality)
- Difficulty index
- Saved to `scorecard_daily` table

---

## 2. Impact Measurement (`impact.py`)

### Purpose
Measure incremental impact of interventions using causal inference techniques:
- Propensity Score Matching
- Difference-in-Differences
- A/B Test Analysis

### Interventions Analyzed

#### Bot Call Uplift
Compares accounts that received bot calls vs no-contact control group.
- **Treatment**: Accounts with BOT call (CONNECT_RPC)
- **Control**: Similar accounts (matched by bucket) with no bot contact
- **Outcome**: Resolution rate within 7 days

#### Field Visit Uplift
Compares field visits to telecaller calls (both interventions, measuring incremental value).
- **Treatment**: Accounts with field visit
- **Control**: Accounts with telecaller call (no field visit)
- **Outcome**: Collection amount within 7 days

#### SMS Campaign Uplift
Requires A/B test design with control group.
- **Treatment**: Accounts in campaign treatment group
- **Control**: Accounts in campaign control group
- **Outcome**: Resolution within N days

### Metrics Reported
- Treatment/Control group sizes
- Treatment/Control outcomes
- Absolute uplift (percentage points)
- Relative uplift (% improvement)
- P-value (statistical significance)
- 95% Confidence interval
- Cost per treatment
- ROI (return on investment)

### Usage
```python
from insights import analyze_impact
from datetime import date, timedelta

# Analyze last 30 days
end_date = date.today()
start_date = end_date - timedelta(days=30)

results = analyze_impact(start_date, end_date)

# Returns list of UpliftResult objects
# Prints formatted report
```

```bash
# Command line
python -m insights.impact 2026-06-19 2026-07-19
```

### Example Output
```
IMPACT MEASUREMENT - UPLIFT ANALYSIS
================================================================================

Intervention: BOT_CALL
  Treatment Group: 1,234 accounts
  Control Group: 1,234 accounts
  Treatment Outcome: 28.50%
  Control Outcome: 22.30%
  Absolute Uplift: +6.20%
  Relative Uplift: +27.8%
  P-Value: 0.0012 ✓ Significant
  95% CI: (4.10%, 8.30%)
  Cost per Treatment: ₹5.00
  ROI: 1,240%
```

---

## 3. Interventions (`interventions.py`)

### Purpose
Rule-based sensors that detect accounts needing special intervention and assign ownership.

### Intervention Types
1. **TL Call** - Team Lead personal call
2. **ACM Escalation** - Area Collection Manager intervention
3. **Field Urgent** - Urgent field visit
4. **Hardship Review** - Special hardship committee
5. **Legal Notice** - Legal notice preparation
6. **Settlement Offer** - Settlement negotiation

### Priority Levels
- **CRITICAL**: Within 24 hours
- **HIGH**: Within 3 days
- **MEDIUM**: Within 7 days
- **LOW**: Within 14 days

### Rule Sensors

#### 1. Broken PTP Streak
**Rule**: 3+ broken PTPs in last 30 days → TL Call (HIGH)
```python
triggers = engine.detect_broken_ptp_streak(date.today(), min_broken=3)
```

#### 2. High Value Stuck
**Rule**: ₹50K+ overdue, 30+ DPD, no payment in 14 days → ACM Escalation (CRITICAL)
```python
triggers = engine.detect_high_value_stuck(date.today())
```

#### 3. Dispute Escalation
**Rule**: 2+ dispute dispositions in 30 days → Hardship Review (HIGH)
```python
triggers = engine.detect_dispute_escalation(date.today(), min_disputes=2)
```

#### 4. Self-Cure Risk
**Rule**: Low selfcure_p (< 15%), high bounce_p (> 40%), B3 bucket → Field Urgent (CRITICAL)
```python
triggers = engine.detect_selfcure_risk(date.today())
```

#### 5. Legal Trigger
**Rule**: 90+ DPD, ₹100K+, no contact in 30 days → Legal Notice (MEDIUM)
```python
triggers = engine.detect_legal_trigger(date.today())
```

#### 6. Settlement Opportunity
**Rule**: 60+ DPD, 3+ partial payments, consistent pattern → Settlement Offer (MEDIUM)
```python
triggers = engine.detect_settlement_opportunity(date.today())
```

### Usage
```python
from insights import run_daily_interventions

# Run all sensors for today
triggers = run_daily_interventions()

# Prints report grouped by intervention type
# Saves to interventions table
```

```bash
# Command line
python -m insights.interventions 2026-07-19
```

### Output
```
INTERVENTION TRIGGERS - DAILY REPORT
====================================================================================================

TL_CALL (12 accounts)
----------------------------------------------------------------------------------------------------
  [HIGH] ACC12345
    Reason: Broken PTP streak: 4 broken promises in 30 days
    Assigned: TL_001
    Due By: 2026-07-22

ACM_ESCALATION (5 accounts)
----------------------------------------------------------------------------------------------------
  [CRITICAL] ACC67890
    Reason: High-value stuck: ₹125,000 overdue, 45 DPD, no payment 18 days
    Assigned: ACM_003
    Due By: 2026-07-20
```

---

## 4. Daily Briefs (`daily_brief.py`)

### Purpose
Generate natural language executive summaries using Ollama LLM (Qwen 2.5 7B).

### Sections
1. **Executive Summary** - 3-5 bullet point highlights
2. **Key Wins** - Achievements, top performers, positive trends
3. **Concerns** - Underperformance, risks, issues
4. **Recommendations** - 2-3 actionable insights

### Data Sources
- Collections metrics (total, accounts resolved, payments)
- Bot performance (calls, connection rate)
- Field performance (visits, success rate)
- PTP performance (made, kept, broken)
- Top teams and agents
- Portfolio health by bucket
- Day-over-day comparison

### Usage
```python
from insights import generate_daily_brief

# Generate brief for today (uses LLM)
brief = generate_daily_brief()

# Generate for specific date without LLM (template-based)
brief = generate_daily_brief(target_date=date(2026, 7, 19), use_llm=False)

# Prints formatted brief
# Saves to daily_briefs table
```

```bash
# Command line (with LLM)
python -m insights.daily_brief 2026-07-19

# Without LLM (template)
python -m insights.daily_brief 2026-07-19 --no-llm
```

### Example Output (LLM-generated)
```
# DAILY COLLECTIONS BRIEF
**Date:** July 19, 2026

## Executive Summary

- Strong collections day with ₹1.2M collected (+12% vs yesterday), driven by field visit success
- Bot connection rate improved to 32%, best performance this week
- PTP keep rate remains healthy at 68%, though 45 broken PTPs require follow-up
- North Zone leads with ₹450K collected, South Zone underperformed at ₹180K

## Key Wins

- Rajesh Kumar (FOS) collected ₹85,000 across 8 successful visits
- Team Alpha achieved 78% resolution rate, highest in portfolio
- Bot handled 1,200 calls with minimal human intervention

## Concerns

- South Zone collections dropped 22% vs yesterday - need to investigate
- 18 high-value accounts (₹50K+) with no payment in 14 days
- Field visit no-show rate at 15%, above 10% target

## Recommendations

1. ACM to personally review 18 high-value stuck accounts identified today
2. Analyze South Zone drop - consider TL calls for key accounts
3. Continue bot optimization - connection rate trending positively
```

---

## Database Schema

### Tables Used

#### `scorecard_daily`
```sql
CREATE TABLE scorecard_daily (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    entity_type VARCHAR(20) NOT NULL,  -- 'agent', 'tl', 'acm', 'zone'
    entity_id VARCHAR(50) NOT NULL,
    entity_name VARCHAR(200),
    metrics JSONB,  -- Full scorecard data
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP,
    UNIQUE (date, entity_type, entity_id)
);
```

#### `interventions`
```sql
CREATE TABLE interventions (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    intervention_type VARCHAR(50) NOT NULL,
    priority VARCHAR(20) NOT NULL,
    reason TEXT,
    assigned_to VARCHAR(50),
    triggered_at TIMESTAMP NOT NULL,
    due_by DATE NOT NULL,
    context JSONB,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, in_progress, completed, cancelled
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (account_id, intervention_type, triggered_at)
);
```

#### `daily_briefs`
```sql
CREATE TABLE daily_briefs (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    brief_text TEXT NOT NULL,
    generated_at TIMESTAMP DEFAULT NOW()
);
```

---

## Integration with Daily Workflow

### Morning (7:00 AM)
```bash
# Generate daily brief for yesterday
python -m insights.daily_brief $(date -d "yesterday" +%Y-%m-%d)
```

### Throughout Day
```bash
# Calculate scorecards (real-time)
python -m insights.scorecards

# Detect interventions (hourly)
python -m insights.interventions
```

### End of Day (9:00 PM)
```bash
# Run impact analysis (weekly)
python -m insights.impact $(date -d "7 days ago" +%Y-%m-%d) $(date +%Y-%m-%d)
```

---

## Requirements

### Python Packages
```
psycopg2-binary
requests
numpy
```

### External Services
- PostgreSQL 16+ (database)
- Ollama (for LLM daily briefs)
  - Model: `qwen2.5:7b`
  - Endpoint: `http://localhost:11434`

### Environment Variables
```bash
export POSTGRES_PASSWORD=your_password
```

---

## Testing

### Quick Test (all modules)
```bash
# Scorecards
python -m insights.scorecards 2026-07-19

# Impact
python -m insights.impact 2026-06-19 2026-07-19

# Interventions
python -m insights.interventions 2026-07-19

# Daily Brief (without LLM for speed)
python -m insights.daily_brief 2026-07-19 --no-llm
```

---

## Future Enhancements

1. **Scorecards**
   - Team-level aggregation
   - Multi-period trends (weekly, monthly)
   - Quality score integration with bot QA rubric

2. **Impact**
   - More sophisticated propensity score matching
   - Heterogeneous treatment effects (by segment)
   - Long-term impact tracking (30/60/90 day)

3. **Interventions**
   - ML-based intervention recommendation
   - Automatic reassignment based on workload
   - Intervention effectiveness tracking

4. **Daily Briefs**
   - Multi-day trend analysis
   - Predictive insights (forecasting)
   - Personalized briefs by role (TL, ACM, CEO)

---

## License

Part of CollectOS, built as open-source collections operating system.
