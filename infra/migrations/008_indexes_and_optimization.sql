-- Migration 008: Additional Indexes and Query Optimization
-- Performance indexes for common query patterns
-- Created: 2026-07-19

-- Composite indexes for common join patterns
CREATE INDEX idx_dim_account_customer_status ON dim_account(customer_id, status) WHERE status = 'ACTIVE';
CREATE INDEX idx_fct_calls_account_date_outcome ON fct_calls(account_id, DATE(call_start_time), outcome);
CREATE INDEX idx_fct_visits_account_date ON fct_visits(account_id, visit_date, disposition);

-- Covering index for allocation queries (includes frequently selected columns)
CREATE INDEX idx_allocations_agent_period_covering ON allocations(owner_agent_id, period_month)
    INCLUDE (account_id, difficulty_score);

-- Partial indexes for hot paths
CREATE INDEX idx_call_queue_pending_priority ON call_queue(scheduled_slot, priority_score DESC)
    WHERE status IN ('NEW', 'QUEUED') AND scheduled_slot >= CURRENT_TIMESTAMP;

CREATE INDEX idx_fct_ptp_broken ON fct_ptp(account_id, promise_date)
    WHERE status = 'BROKEN' AND promise_date >= CURRENT_DATE - INTERVAL '30 days';

-- GIN index for JSONB columns (for flexible querying of semi-structured data)
CREATE INDEX idx_scorecard_metrics_gin ON scorecard_daily USING gin(metrics);
CREATE INDEX idx_campaign_cadence_gin ON campaigns USING gin(cadence_rules);
CREATE INDEX idx_intervention_evidence_gin ON interventions USING gin(evidence_data);

-- Text search indexes
CREATE INDEX idx_dim_customer_name_search ON dim_customer USING gin(to_tsvector('english', name));
CREATE INDEX idx_interventions_description_search ON interventions USING gin(to_tsvector('english', description || ' ' || COALESCE(title, '')));

-- Statistics for query planner
ALTER TABLE mart_account_daily ALTER COLUMN date SET STATISTICS 1000;
ALTER TABLE mart_account_daily ALTER COLUMN account_id SET STATISTICS 1000;
ALTER TABLE fct_calls ALTER COLUMN call_start_time SET STATISTICS 500;
ALTER TABLE allocations ALTER COLUMN period_month SET STATISTICS 500;

-- Materialized view for performance dashboard (refreshed hourly)
CREATE MATERIALIZED VIEW mv_portfolio_summary AS
SELECT
    date,
    bucket,
    COUNT(*) as account_count,
    SUM(overdue_amt) as total_overdue,
    SUM(pos) as total_pos,
    COUNT(CASE WHEN has_open_ptp THEN 1 END) as ptp_count,
    AVG(bounce_p) as avg_bounce_p,
    AVG(selfcure_p) as avg_selfcure_p
FROM mart_account_daily
WHERE date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY date, bucket;

CREATE UNIQUE INDEX idx_mv_portfolio_summary ON mv_portfolio_summary(date, bucket);

-- Materialized view for agent workload
CREATE MATERIALIZED VIEW mv_agent_workload AS
SELECT
    owner_agent_id,
    date,
    COUNT(*) as account_count,
    COUNT(CASE WHEN bucket = 'B1' THEN 1 END) as b1_count,
    COUNT(CASE WHEN bucket = 'B2' THEN 1 END) as b2_count,
    COUNT(CASE WHEN bucket = 'B3' THEN 1 END) as b3_count,
    SUM(overdue_amt) as total_dues,
    AVG(difficulty_score) as avg_difficulty,
    COUNT(CASE WHEN has_open_ptp THEN 1 END) as ptp_count
FROM mart_account_daily
WHERE owner_agent_id IS NOT NULL
  AND date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY owner_agent_id, date;

CREATE UNIQUE INDEX idx_mv_agent_workload ON mv_agent_workload(owner_agent_id, date);

-- Function to refresh materialized views
CREATE OR REPLACE FUNCTION refresh_materialized_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_portfolio_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_agent_workload;
END;
$$ LANGUAGE plpgsql;

COMMENT ON MATERIALIZED VIEW mv_portfolio_summary IS 'Portfolio KPIs by date and bucket - refresh hourly';
COMMENT ON MATERIALIZED VIEW mv_agent_workload IS 'Agent workload metrics - refresh hourly';
