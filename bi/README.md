# CollectOS BI Module

Metabase dashboard provisioning and SQL analytics queries.

## Overview

This module contains:
- **SQL Queries**: Pre-built queries for 3 operational dashboards
- **Dashboard Config**: YAML configuration mapping queries to dashboard cards
- **Bootstrap Script**: Python script to auto-provision dashboards via Metabase API

## Dashboards

### 1. Portfolio Command
**Purpose**: Portfolio health monitoring and KPI tracking

**Metrics**:
- Portfolio summary by bucket (accounts, overdue, POS, avg DPD)
- Bounce rate trend (last 30 days)
- Resolution rate by bucket
- Collection efficiency (MTD)
- Portfolio breakdowns (product, zone)
- Roll matrix (bucket transitions)
- NPA movement trend

**Queries**: 8 (portfolio_command.sql)

### 2. Calling Ops
**Purpose**: Call center and telecaller performance

**Metrics**:
- Call metrics by channel (bot vs telecaller)
- Call volume trend
- Slot heatmap (best calling hours)
- Bot containment rate
- Agent productivity
- PTP performance (made vs kept)
- Disposition distribution
- Queue SLA compliance

**Queries**: 8 (calling_ops.sql)

### 3. Field Ops
**Purpose**: Field agent performance and geographic insights

**Metrics**:
- Visit summary (outcomes, collections)
- Strike rate trend (productive visits %)
- Collections by payment mode
- Agent productivity
- Beat plan adherence
- Geographic heatmap (zone performance)
- Visit disposition breakdown
- Collections vs expectations
- Top performing agents

**Queries**: 9 (field_ops.sql)

## Usage

### Prerequisites

1. **Metabase running**: `make up` (docker-compose starts Metabase on port 3000)
2. **Database connected**: Add PostgreSQL connection in Metabase UI (first-time setup)
3. **Python dependencies**: `pip install pyyaml requests`

### Bootstrap Dashboards

```bash
# Set environment variables (optional)
export METABASE_URL=http://localhost:3000
export METABASE_USER=admin@collectos.local
export METABASE_PASSWORD=changeme

# Run bootstrap script
python -m bi.bootstrap

# Or with custom credentials
python bi/bootstrap.py
```

### Manual Setup (Alternative)

If bootstrap script fails, you can manually create dashboards:

1. Open Metabase: http://localhost:3000
2. Create new dashboard
3. Add SQL questions from `bi/queries/*.sql`
4. Arrange cards in grid layout per `bi/dashboards/config.yaml`

## Files

```
bi/
├── __init__.py
├── README.md (this file)
├── bootstrap.py - Metabase API provisioning script
├── dashboards/
│   └── config.yaml - Dashboard layout configuration
└── queries/
    ├── portfolio_command.sql - 8 portfolio metrics queries
    ├── calling_ops.sql - 8 calling/bot performance queries
    └── field_ops.sql - 9 field operations queries
```

## Query Structure

Each SQL file contains multiple queries separated by section comments:

```sql
-- Query 1: Query Name
-- Description
SELECT ...

-- Query 2: Another Query
-- Description
SELECT ...
```

The bootstrap script extracts queries by section number.

## Visualization Types

Dashboards use these visualization types:
- **table**: Detailed data tables
- **line**: Time series trends
- **bar**: Comparative metrics
- **scalar**: Single number KPIs
- **pie**: Percentage breakdowns

## Customization

### Add New Query

1. Add SQL to appropriate file (or create new file)
2. Update `bi/dashboards/config.yaml` with query reference
3. Run bootstrap script to update dashboard

### Modify Dashboard Layout

Edit `bi/dashboards/config.yaml`:
- `size.width`: Card width (1-12 columns)
- `size.height`: Card height (rows)
- Cards flow left-to-right, top-to-bottom

## Notes

- All queries use `mart_account_daily` and fact tables
- Queries are optimized with proper indexes
- Date filters use `CURRENT_DATE` for dynamic ranges
- Bootstrap script is idempotent (safe to re-run)

## Troubleshooting

**"Database not found"**:
- Manually add PostgreSQL connection in Metabase UI
- Host: `collectos-postgres`, Port: 5432, Database: `collectos`

**"Authentication failed"**:
- Check Metabase admin credentials
- Default: admin@collectos.local / changeme

**"Query timeout"**:
- Check database indexes (migrations 008)
- Reduce date range in query filters
