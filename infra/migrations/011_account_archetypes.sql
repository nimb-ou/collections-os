-- Migration 011: Account Archetypes (Hidden Truth)
-- Stores behavioral archetypes for synthetic accounts
-- Separate from dim_account to maintain "hidden truth" that ML must rediscover
-- Created: 2026-07-19

CREATE TABLE IF NOT EXISTS account_archetypes (
    account_id VARCHAR(50) PRIMARY KEY REFERENCES dim_account(account_id),
    archetype VARCHAR(20) NOT NULL CHECK (archetype IN ('PRIME', 'SPORADIC', 'STRESSED', 'CHRONIC', 'STRATEGIC')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_account_archetypes_archetype ON account_archetypes(archetype);

COMMENT ON TABLE account_archetypes IS 'Hidden truth: behavioral archetypes for synthetic accounts - not exposed in dim_account';
