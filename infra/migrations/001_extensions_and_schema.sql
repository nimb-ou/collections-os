-- Migration 001: Extensions and Schema Setup
-- CollectOS Database Initialization
-- Created: 2026-07-19

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text search
CREATE EXTENSION IF NOT EXISTS "btree_gin"; -- For multi-column indexes

-- Create custom types
CREATE TYPE bucket_type AS ENUM ('PRE_DUE', 'X', 'B1', 'B2', 'B3', 'NPA_90', 'NPA_120', 'NPA_150', 'NPA_180+');
CREATE TYPE channel_type AS ENUM ('BOT', 'TELECALLER', 'FIELD', 'SMS', 'EMAIL', 'SYSTEM');
CREATE TYPE disposition_type AS ENUM (
    'CONNECT_RPC',
    'CONNECT_TPC',
    'PTP',
    'PAID_CLAIM',
    'DISPUTE',
    'HARDSHIP',
    'NOT_INTERESTED',
    'WRONG_NO',
    'NO_ANSWER',
    'SWITCHED_OFF',
    'CALLBACK',
    'DNC_REQUEST',
    'LANG_SWITCH',
    'VISIT_MET',
    'VISIT_NOT_FOUND',
    'ADDRESS_ISSUE',
    'COLLECTED'
);
CREATE TYPE ptp_status_type AS ENUM ('OPEN', 'KEPT', 'BROKEN', 'PARTIAL', 'CANCELLED');
CREATE TYPE call_outcome_type AS ENUM ('CONNECTED', 'NO_ANSWER', 'BUSY', 'FAILED', 'DNC');
CREATE TYPE agent_role_type AS ENUM ('FOS', 'TC', 'TL', 'ACM', 'RCM', 'ADMIN');
CREATE TYPE user_role_type AS ENUM ('ADMIN', 'STRATEGY', 'TL', 'ACM', 'AGENT', 'AUDITOR');
CREATE TYPE campaign_type AS ENUM ('PRE_DUE', 'POST_BOUNCE', 'PTP_REMINDER', 'BROKEN_PTP', 'EARLY_BUCKET', 'FIELD_SUPPORT');
CREATE TYPE queue_status_type AS ENUM ('NEW', 'QUEUED', 'IN_CALL', 'DONE', 'SKIPPED');
CREATE TYPE intervention_severity AS ENUM ('INFO', 'WARNING', 'CRITICAL');
CREATE TYPE intervention_status AS ENUM ('OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'IGNORED');

-- Create utility function for timestamps
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create function to get current bucket from DPD
CREATE OR REPLACE FUNCTION dpd_to_bucket(dpd INTEGER)
RETURNS bucket_type AS $$
BEGIN
    RETURN CASE
        WHEN dpd < 0 THEN 'PRE_DUE'::bucket_type
        WHEN dpd = 0 THEN 'X'::bucket_type
        WHEN dpd BETWEEN 1 AND 30 THEN 'B1'::bucket_type
        WHEN dpd BETWEEN 31 AND 60 THEN 'B2'::bucket_type
        WHEN dpd BETWEEN 61 AND 90 THEN 'B3'::bucket_type
        WHEN dpd BETWEEN 91 AND 120 THEN 'NPA_90'::bucket_type
        WHEN dpd BETWEEN 121 AND 150 THEN 'NPA_120'::bucket_type
        WHEN dpd BETWEEN 151 AND 180 THEN 'NPA_150'::bucket_type
        ELSE 'NPA_180+'::bucket_type
    END;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Create comment table for self-documentation
COMMENT ON DATABASE collectos IS 'CollectOS - End-to-End Collections Operating System for CV/CE Portfolio';
