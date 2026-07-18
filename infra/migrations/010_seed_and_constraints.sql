-- Migration 010: Seed Data and Final Constraints
-- Initial seed data for dimensions and validation constraints
-- Created: 2026-07-19

-- Seed initial zones and states (Indian geography)
INSERT INTO dim_geo (pincode, city, district, state, zone) VALUES
    ('110001', 'New Delhi', 'Central Delhi', 'Delhi', 'North'),
    ('400001', 'Mumbai', 'Mumbai City', 'Maharashtra', 'West'),
    ('560001', 'Bangalore', 'Bangalore Urban', 'Karnataka', 'South'),
    ('600001', 'Chennai', 'Chennai', 'Tamil Nadu', 'South'),
    ('700001', 'Kolkata', 'Kolkata', 'West Bengal', 'East'),
    ('500001', 'Hyderabad', 'Hyderabad', 'Telangana', 'South'),
    ('380001', 'Ahmedabad', 'Ahmedabad', 'Gujarat', 'West'),
    ('411001', 'Pune', 'Pune', 'Maharashtra', 'West'),
    ('302001', 'Jaipur', 'Jaipur', 'Rajasthan', 'North'),
    ('226001', 'Lucknow', 'Lucknow', 'Uttar Pradesh', 'North'),
    ('462001', 'Bhopal', 'Bhopal', 'Madhya Pradesh', 'Central'),
    ('800001', 'Patna', 'Patna', 'Bihar', 'East'),
    ('641001', 'Coimbatore', 'Coimbatore', 'Tamil Nadu', 'South'),
    ('160001', 'Chandigarh', 'Chandigarh', 'Chandigarh', 'North'),
    ('682001', 'Kochi', 'Ernakulam', 'Kerala', 'South')
ON CONFLICT (pincode) DO NOTHING;

-- Seed default admin user (password should be changed immediately)
INSERT INTO users (user_id, username, email, password_hash, role, active, created_by)
VALUES
    ('admin', 'admin', 'admin@collectos.local', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5oj2n9.ByOB4W', 'ADMIN', true, 'system'),
    ('system', 'system', 'system@collectos.local', NULL, 'ADMIN', true, 'system')
ON CONFLICT (user_id) DO NOTHING;
-- Note: Password for 'admin' is 'changeme' - MUST be changed in production

-- Seed default team (will be expanded by synthgen)
INSERT INTO dim_team (team_name, team_type, zone) VALUES
    ('Unassigned', 'MIXED', NULL),
    ('System', 'MIXED', NULL)
ON CONFLICT (team_name) DO NOTHING;

-- Additional constraints and validations
ALTER TABLE fct_presentations ADD CONSTRAINT chk_presentation_amount_positive
    CHECK (amount > 0);

ALTER TABLE fct_payments ADD CONSTRAINT chk_payment_amount_positive
    CHECK (amount > 0);

ALTER TABLE fct_ptp ADD CONSTRAINT chk_ptp_amount_positive
    CHECK (promise_amount > 0);

ALTER TABLE fct_ptp ADD CONSTRAINT chk_ptp_dates
    CHECK (promise_date >= DATE(created_at));

ALTER TABLE campaigns ADD CONSTRAINT chk_campaign_dates
    CHECK (end_date IS NULL OR end_date >= start_date);

ALTER TABLE call_queue ADD CONSTRAINT chk_queue_priority
    CHECK (priority_score >= 0);

ALTER TABLE beat_plan ADD CONSTRAINT chk_beat_sequence
    CHECK (sequence_no > 0);

ALTER TABLE mart_account_daily ADD CONSTRAINT chk_mart_amounts_positive
    CHECK (pos >= 0 AND emi_amt > 0);

ALTER TABLE scorecard_daily ADD CONSTRAINT chk_scorecard_performance
    CHECK (performance_score >= 0 AND performance_score <= 100);

-- Row Level Security setup (templates - to be enabled with proper policies)
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

-- Create RLS policy examples (to be customized per deployment)
CREATE POLICY user_own_record ON users
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id', true));

CREATE POLICY audit_read_only ON audit_log
    FOR SELECT
    TO PUBLIC
    USING (true);

-- Prevent updates/deletes on append-only tables
CREATE OR REPLACE FUNCTION prevent_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'This table is append-only. Updates and deletes are not allowed.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER prevent_audit_log_update
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION prevent_modification();

CREATE TRIGGER prevent_dispositions_update
    BEFORE UPDATE OR DELETE ON dispositions
    FOR EACH ROW EXECUTE FUNCTION prevent_modification();

-- Create a helper function to log changes to audit_log
CREATE OR REPLACE FUNCTION log_to_audit(
    p_table_name VARCHAR,
    p_record_id VARCHAR,
    p_operation VARCHAR,
    p_changed_by VARCHAR,
    p_change_reason VARCHAR DEFAULT NULL,
    p_old_values JSONB DEFAULT NULL,
    p_new_values JSONB DEFAULT NULL
)
RETURNS void AS $$
BEGIN
    INSERT INTO audit_log (table_name, record_id, operation, changed_by, change_reason, old_values, new_values)
    VALUES (p_table_name, p_record_id, p_operation, p_changed_by, p_change_reason, p_old_values, p_new_values);
END;
$$ LANGUAGE plpgsql;

-- Database configuration for optimal performance
ALTER DATABASE collectos SET random_page_cost = 1.1;  -- For SSD
ALTER DATABASE collectos SET effective_cache_size = '2GB';
ALTER DATABASE collectos SET shared_buffers = '512MB';
ALTER DATABASE collectos SET work_mem = '50MB';
ALTER DATABASE collectos SET maintenance_work_mem = '256MB';
ALTER DATABASE collectos SET effective_io_concurrency = 200;

-- Enable parallel query execution
ALTER DATABASE collectos SET max_parallel_workers_per_gather = 2;
ALTER DATABASE collectos SET max_parallel_workers = 4;

-- Autovacuum tuning for high-write tables
ALTER TABLE fct_calls SET (autovacuum_vacuum_scale_factor = 0.05);
ALTER TABLE fct_visits SET (autovacuum_vacuum_scale_factor = 0.05);
ALTER TABLE dispositions SET (autovacuum_vacuum_scale_factor = 0.05);
ALTER TABLE call_queue SET (autovacuum_vacuum_scale_factor = 0.02);

-- Grant appropriate permissions
GRANT USAGE ON SCHEMA public TO collectos;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO collectos;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO collectos;

-- Create read-only role for BI tools
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'collectos_readonly') THEN
        CREATE ROLE collectos_readonly WITH LOGIN PASSWORD 'readonly_password';
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO collectos_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO collectos_readonly;

-- Ensure future tables are also accessible
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO collectos_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO collectos;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO collectos;

-- Analyze all tables for query planner
ANALYZE;

-- Final validation query
DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_type = 'BASE TABLE';

    RAISE NOTICE 'CollectOS database initialized successfully with % tables', table_count;
    RAISE NOTICE 'Default admin user: username=admin, password=changeme (CHANGE THIS!)';
    RAISE NOTICE 'Database ready for synthgen seed (Session 2-3)';
END $$;

COMMENT ON DATABASE collectos IS 'CollectOS v1.0 - End-to-End Collections Operating System | Schema initialized 2026-07-19';
