-- Migration 004: mart_account_daily (Heart of the System)
-- One row per account per day with DPD, scores, treatment, owner
-- Partitioned by month for performance
-- Created: 2026-07-19

-- Main mart table (partitioned by month)
CREATE TABLE mart_account_daily (
    account_id VARCHAR(50) NOT NULL,
    date DATE NOT NULL,

    -- Account state
    dpd INTEGER NOT NULL,
    bucket bucket_type NOT NULL,
    overdue_amt DECIMAL(12, 2) DEFAULT 0,
    pos DECIMAL(12, 2) NOT NULL,  -- Principal Outstanding
    total_dues DECIMAL(12, 2) DEFAULT 0,
    emi_amt DECIMAL(10, 2) NOT NULL,
    cycle_day INTEGER NOT NULL,

    -- Scores (from ML models)
    bounce_p DECIMAL(5, 4),  -- Probability of next EMI bouncing
    selfcure_p DECIMAL(5, 4),  -- Probability of self-cure in 7 days
    rollfwd_p DECIMAL(5, 4),  -- Probability of rolling to next bucket
    propensity_p DECIMAL(5, 4),  -- Probability of any payment in 30 days (for deep buckets)
    best_call_slot VARCHAR(20),  -- Best 2-hour slot for calling (HH:00-HH:00)
    difficulty_score DECIMAL(5, 4),  -- Expected resolution difficulty (for agent scorecards)

    -- Treatment
    treatment_code VARCHAR(50),  -- Assigned treatment from strategy engine

    -- Ownership
    owner_agent_id VARCHAR(50),  -- Assigned owner for the day
    owner_channel channel_type,  -- BOT, TELECALLER, FIELD
    allocation_reason VARCHAR(200),  -- Why this account was allocated to this agent

    -- Flags
    has_open_ptp BOOLEAN DEFAULT false,
    is_dnc BOOLEAN DEFAULT false,
    is_suppressed BOOLEAN DEFAULT false,  -- High selfcure_p, suppress for N days

    -- Activity tracking
    last_contact_date DATE,
    last_contact_channel channel_type,
    last_payment_date DATE,
    last_payment_amt DECIMAL(10, 2),
    attempts_this_cycle INTEGER DEFAULT 0,  -- Contact attempts in current cycle

    -- Next action
    next_action VARCHAR(100),
    next_action_date DATE,
    priority_score DECIMAL(8, 2),  -- For queue ordering

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (account_id, date)
) PARTITION BY RANGE (date);

-- Create monthly partitions for past 13 months + current + next month
-- This will be automated by a maintenance script, but we'll create initial ones
-- Starting from 2024-01-01 for historical synthetic data

DO $$
DECLARE
    start_date DATE := '2024-01-01';
    end_date DATE := '2027-01-01';  -- Future partitions
    partition_date DATE;
    partition_name TEXT;
    partition_start DATE;
    partition_end DATE;
BEGIN
    partition_date := DATE_TRUNC('month', start_date);

    WHILE partition_date < end_date LOOP
        partition_name := 'mart_account_daily_' || TO_CHAR(partition_date, 'YYYY_MM');
        partition_start := partition_date;
        partition_end := partition_date + INTERVAL '1 month';

        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF mart_account_daily FOR VALUES FROM (%L) TO (%L)',
            partition_name,
            partition_start,
            partition_end
        );

        partition_date := partition_date + INTERVAL '1 month';
    END LOOP;
END $$;

-- Indexes on partitioned table
CREATE INDEX idx_mart_account_daily_date ON mart_account_daily(date);
CREATE INDEX idx_mart_account_daily_bucket ON mart_account_daily(bucket);
CREATE INDEX idx_mart_account_daily_dpd ON mart_account_daily(dpd);
CREATE INDEX idx_mart_account_daily_owner ON mart_account_daily(owner_agent_id, date) WHERE owner_agent_id IS NOT NULL;
CREATE INDEX idx_mart_account_daily_treatment ON mart_account_daily(treatment_code);
CREATE INDEX idx_mart_account_daily_ptp ON mart_account_daily(account_id, date) WHERE has_open_ptp = true;
CREATE INDEX idx_mart_account_daily_next_action ON mart_account_daily(next_action_date) WHERE next_action_date IS NOT NULL;
CREATE INDEX idx_mart_account_daily_priority ON mart_account_daily(date, priority_score DESC) WHERE next_action_date IS NOT NULL;

-- Composite index for allocation queries
CREATE INDEX idx_mart_account_daily_alloc ON mart_account_daily(date, bucket, owner_agent_id);

-- BRIN index for date ranges (efficient for time-series queries)
CREATE INDEX idx_mart_account_daily_date_brin ON mart_account_daily USING BRIN(date);

-- Trigger for updated_at
CREATE TRIGGER update_mart_account_daily_updated_at
    BEFORE UPDATE ON mart_account_daily
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- View for today's active accounts
CREATE OR REPLACE VIEW v_accounts_today AS
SELECT
    m.*,
    a.customer_id,
    a.product_type,
    a.geo_id,
    c.name as customer_name,
    c.lang_pref
FROM mart_account_daily m
JOIN dim_account a ON m.account_id = a.account_id
JOIN dim_customer c ON a.customer_id = c.customer_id
WHERE m.date = CURRENT_DATE
  AND a.status = 'ACTIVE';

-- View for orphan accounts (no owner assigned)
CREATE OR REPLACE VIEW v_orphan_accounts AS
SELECT
    account_id,
    date,
    dpd,
    bucket,
    overdue_amt,
    treatment_code
FROM mart_account_daily
WHERE owner_agent_id IS NULL
  AND date = CURRENT_DATE
  AND bucket NOT IN ('PRE_DUE', 'X')
  AND NOT is_suppressed;

COMMENT ON TABLE mart_account_daily IS 'Heart of CollectOS: one row per account per day with state, scores, treatment, and ownership';
COMMENT ON VIEW v_orphan_accounts IS 'Accounts requiring allocation - QC check for complete ownership';
