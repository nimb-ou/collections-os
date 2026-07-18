-- Migration 006: Registry, Monitoring, Scorecards, Interventions
-- Model registry, scorecards, interventions engine, audit log
-- Created: 2026-07-19

-- Model Registry (ML model versioning and monitoring)
CREATE TABLE model_registry (
    model_id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,  -- bounce, selfcure, rollfwd, etc.
    version VARCHAR(50) NOT NULL,
    model_type VARCHAR(50) NOT NULL,  -- lightgbm, sklearn, etc.
    trained_on DATE NOT NULL,
    training_rows INTEGER,
    training_duration_sec INTEGER,
    -- Metrics
    auc DECIMAL(5, 4),
    precision_at_50 DECIMAL(5, 4),
    recall_at_50 DECIMAL(5, 4),
    calibration_error DECIMAL(5, 4),
    -- Deployment
    is_champion BOOLEAN DEFAULT false,
    promoted_at TIMESTAMP,
    deprecated_at TIMESTAMP,
    -- Artifacts
    model_path VARCHAR(500) NOT NULL,
    feature_list JSONB,
    hyperparameters JSONB,
    shap_summary_path VARCHAR(500),
    -- Metadata
    trained_by VARCHAR(50) DEFAULT 'system',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_name, version)
);

CREATE INDEX idx_model_registry_name ON model_registry(model_name);
CREATE INDEX idx_model_registry_champion ON model_registry(model_name, is_champion) WHERE is_champion = true;
CREATE INDEX idx_model_registry_trained_on ON model_registry(trained_on);

-- Score History (for PSI monitoring and drift detection)
CREATE TABLE score_history (
    score_id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    score_date DATE NOT NULL,
    account_id VARCHAR(50) NOT NULL,
    score DECIMAL(5, 4) NOT NULL,
    decile INTEGER CHECK (decile BETWEEN 1 AND 10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Partition by month for performance
CREATE INDEX idx_score_history_model_date ON score_history(model_name, score_date);
CREATE INDEX idx_score_history_account ON score_history(account_id, model_name);
CREATE INDEX idx_score_history_decile ON score_history(score_date, decile);

-- Scorecards (daily agent/team performance)
CREATE TABLE scorecard_daily (
    scorecard_id SERIAL PRIMARY KEY,
    entity_type VARCHAR(20) NOT NULL,  -- agent, tl, acm, zone
    entity_id VARCHAR(50) NOT NULL,  -- agent_id, team_id, etc.
    score_date DATE NOT NULL,
    -- Metrics (stored as JSONB for flexibility)
    metrics JSONB NOT NULL,
    -- Composite scores
    performance_score DECIMAL(5, 2),
    rank_in_peer_group INTEGER,
    peer_group_size INTEGER,
    -- Metadata
    difficulty_adjusted BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity_type, entity_id, score_date)
);

CREATE INDEX idx_scorecard_entity ON scorecard_daily(entity_type, entity_id, score_date);
CREATE INDEX idx_scorecard_date ON scorecard_daily(score_date);
CREATE INDEX idx_scorecard_performance ON scorecard_daily(score_date, performance_score DESC);

-- Interventions (business rule alerts and actions)
CREATE TABLE interventions (
    intervention_id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    severity intervention_severity NOT NULL,
    category VARCHAR(50),  -- portfolio, agent_performance, model_drift, ops, etc.
    -- Assignment
    owner_role user_role_type NOT NULL,
    assigned_to VARCHAR(50),  -- User or team
    -- Evidence
    evidence_query TEXT,  -- SQL query that generated the intervention
    evidence_data JSONB,  -- Key metrics/data points
    recommended_action TEXT,
    -- SLA
    sla_hours INTEGER,
    due_date TIMESTAMP,
    -- Status
    status intervention_status DEFAULT 'OPEN',
    acknowledged_at TIMESTAMP,
    acknowledged_by VARCHAR(50),
    resolved_at TIMESTAMP,
    resolved_by VARCHAR(50),
    resolution_notes TEXT,
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_interventions_status ON interventions(status) WHERE status IN ('OPEN', 'ACKNOWLEDGED');
CREATE INDEX idx_interventions_severity ON interventions(severity);
CREATE INDEX idx_interventions_owner ON interventions(owner_role, assigned_to);
CREATE INDEX idx_interventions_due ON interventions(due_date) WHERE status IN ('OPEN', 'ACKNOWLEDGED');
CREATE INDEX idx_interventions_category ON interventions(category);

-- Audit Log (all mutations with actor and reason)
CREATE TABLE audit_log (
    audit_id SERIAL PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    record_id VARCHAR(100),
    operation VARCHAR(20) NOT NULL,  -- INSERT, UPDATE, DELETE
    changed_by VARCHAR(50) NOT NULL,  -- User or 'system'
    change_reason VARCHAR(500),
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Append-only, no updates
CREATE INDEX idx_audit_log_table ON audit_log(table_name, created_at);
CREATE INDEX idx_audit_log_user ON audit_log(changed_by, created_at);
CREATE INDEX idx_audit_log_created ON audit_log(created_at);

-- Users (for authentication and authorization)
CREATE TABLE users (
    user_id VARCHAR(50) PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(200) UNIQUE,
    password_hash VARCHAR(500),  -- NULL for SSO users
    role user_role_type NOT NULL,
    agent_id VARCHAR(50),  -- Link to dim_agent if role is AGENT/TL/ACM
    active BOOLEAN DEFAULT true,
    -- Security
    last_login TIMESTAMP,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP,
    -- Metadata
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_username ON users(username) WHERE active = true;
CREATE INDEX idx_users_agent ON users(agent_id) WHERE agent_id IS NOT NULL;
CREATE INDEX idx_users_role ON users(role);

-- Bot QA scores (call quality monitoring)
CREATE TABLE bot_qa_scores (
    qa_id SERIAL PRIMARY KEY,
    call_id INTEGER NOT NULL REFERENCES fct_calls(call_id),
    qa_date DATE NOT NULL,
    -- Rubric scores (0-1)
    script_adherence DECIMAL(3, 2),
    disclosure_present BOOLEAN,
    tone_score DECIMAL(3, 2),
    outcome_appropriate BOOLEAN,
    overall_score DECIMAL(3, 2),
    -- Analysis
    issues JSONB,  -- Array of detected issues
    transcript_path VARCHAR(500),
    reviewed_by VARCHAR(50),  -- NULL if automated
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_bot_qa_call ON bot_qa_scores(call_id);
CREATE INDEX idx_bot_qa_date ON bot_qa_scores(qa_date);
CREATE INDEX idx_bot_qa_score ON bot_qa_scores(overall_score);

-- Triggers
CREATE TRIGGER update_interventions_updated_at BEFORE UPDATE ON interventions FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at();

COMMENT ON TABLE model_registry IS 'ML model versioning with champion/challenger tracking and metrics';
COMMENT ON TABLE interventions IS 'Business rule alerts requiring action - ownersh and SLA tracked';
COMMENT ON TABLE audit_log IS 'Immutable log of all system mutations for compliance';
COMMENT ON TABLE scorecard_daily IS 'Daily performance metrics for agents and teams with difficulty adjustment';
