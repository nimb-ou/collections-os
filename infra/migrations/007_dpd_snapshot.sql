-- Migration 007: DPD Snapshot Table
-- Daily input from bank: account state snapshot
-- Created: 2026-07-19

-- DPD Snapshot (daily feed from bank or synthgen)
CREATE TABLE in_dpd_snapshot (
    snapshot_id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL REFERENCES dim_account(account_id),
    snapshot_date DATE NOT NULL,
    dpd INTEGER NOT NULL,
    bucket bucket_type NOT NULL,
    overdue_amt DECIMAL(12, 2) DEFAULT 0,
    pos DECIMAL(12, 2) NOT NULL,  -- Principal Outstanding
    total_dues DECIMAL(12, 2) DEFAULT 0,
    emi_amt DECIMAL(10, 2) NOT NULL,
    -- Metadata
    source VARCHAR(50) DEFAULT 'CBS',  -- CBS, synthgen, manual
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, snapshot_date)
);

CREATE INDEX idx_in_dpd_snapshot_date ON in_dpd_snapshot(snapshot_date);
CREATE INDEX idx_in_dpd_snapshot_account_date ON in_dpd_snapshot(account_id, snapshot_date);
CREATE INDEX idx_in_dpd_snapshot_bucket ON in_dpd_snapshot(snapshot_date, bucket);
CREATE INDEX idx_in_dpd_snapshot_dpd ON in_dpd_snapshot(snapshot_date, dpd);

-- Landing tables for bank extracts (to be validated before loading to canonical schema)
CREATE TABLE landing_account_master (
    raw_data JSONB NOT NULL,
    file_name VARCHAR(500),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE landing_customer_master (
    raw_data JSONB NOT NULL,
    file_name VARCHAR(500),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE landing_presentations (
    raw_data JSONB NOT NULL,
    file_name VARCHAR(500),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE landing_payments (
    raw_data JSONB NOT NULL,
    file_name VARCHAR(500),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE landing_dpd_snapshot (
    raw_data JSONB NOT NULL,
    file_name VARCHAR(500),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Data quality check results
CREATE TABLE dq_check_results (
    check_id SERIAL PRIMARY KEY,
    check_name VARCHAR(200) NOT NULL,
    check_type VARCHAR(50) NOT NULL,  -- row_count, null_check, range_check, uniqueness, drift, etc.
    table_name VARCHAR(100) NOT NULL,
    check_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL,  -- PASS, WARN, FAIL
    expected_value VARCHAR(200),
    actual_value VARCHAR(200),
    threshold VARCHAR(100),
    details JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dq_check_results_date ON dq_check_results(check_date);
CREATE INDEX idx_dq_check_results_status ON dq_check_results(status) WHERE status IN ('WARN', 'FAIL');
CREATE INDEX idx_dq_check_results_table ON dq_check_results(table_name, check_date);

COMMENT ON TABLE in_dpd_snapshot IS 'Daily account state snapshot from bank CBS or synthgen';
COMMENT ON TABLE dq_check_results IS 'Data quality validation results - pipeline blocks on FAIL';
