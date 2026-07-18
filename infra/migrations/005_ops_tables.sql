-- Migration 005: Operational Tables
-- Campaigns, queues, beat plans, allocations
-- Created: 2026-07-19

-- Campaigns
CREATE TABLE campaigns (
    campaign_id SERIAL PRIMARY KEY,
    campaign_name VARCHAR(200) NOT NULL,
    campaign_type campaign_type NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    channel channel_type NOT NULL,
    target_bucket bucket_type[],  -- Array of target buckets
    control_group_pct DECIMAL(4, 2) DEFAULT 5.00,
    active BOOLEAN DEFAULT true,
    cadence_rules JSONB,  -- Cadence configuration (flexible schema)
    script_id VARCHAR(100),  -- Reference to call/bot script
    created_by VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_campaigns_type ON campaigns(campaign_type);
CREATE INDEX idx_campaigns_active ON campaigns(active) WHERE active = true;
CREATE INDEX idx_campaigns_dates ON campaigns(start_date, end_date);

-- Campaign Targets (which accounts are in this campaign)
CREATE TABLE campaign_targets (
    target_id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(campaign_id),
    account_id VARCHAR(50) NOT NULL REFERENCES dim_account(account_id),
    date DATE NOT NULL,
    is_control_group BOOLEAN DEFAULT false,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(campaign_id, account_id, date)
);

CREATE INDEX idx_campaign_targets_campaign ON campaign_targets(campaign_id);
CREATE INDEX idx_campaign_targets_account ON campaign_targets(account_id);
CREATE INDEX idx_campaign_targets_date ON campaign_targets(date);
CREATE INDEX idx_campaign_targets_control ON campaign_targets(campaign_id, is_control_group);

-- Call Queue (for bot and telecaller)
CREATE TABLE call_queue (
    queue_id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL REFERENCES dim_account(account_id),
    customer_id VARCHAR(50) NOT NULL REFERENCES dim_customer(customer_id),
    phone VARCHAR(15) NOT NULL,
    campaign_id INTEGER REFERENCES campaigns(campaign_id),
    channel channel_type NOT NULL,
    agent_id VARCHAR(50),  -- Assigned agent (null for bot)
    scheduled_slot TIMESTAMP NOT NULL,  -- Slotted time for call
    priority_score DECIMAL(8, 2) NOT NULL,
    status queue_status_type DEFAULT 'NEW',
    attempts INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMP,
    result_call_id INTEGER REFERENCES fct_calls(call_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_call_queue_status ON call_queue(status) WHERE status IN ('NEW', 'QUEUED');
CREATE INDEX idx_call_queue_agent ON call_queue(agent_id, scheduled_slot) WHERE agent_id IS NOT NULL;
CREATE INDEX idx_call_queue_slot ON call_queue(scheduled_slot, priority_score DESC) WHERE status IN ('NEW', 'QUEUED');
CREATE INDEX idx_call_queue_account ON call_queue(account_id);
CREATE INDEX idx_call_queue_campaign ON call_queue(campaign_id);

-- Allocations (who owns which accounts and why)
CREATE TABLE allocations (
    allocation_id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL REFERENCES dim_account(account_id),
    period_month DATE NOT NULL,  -- First day of the month
    owner_agent_id VARCHAR(50) NOT NULL,
    allocation_reason VARCHAR(200),  -- Why this account → this agent
    difficulty_score DECIMAL(5, 4),  -- Expected difficulty (for fair scorecards)
    allocated_by VARCHAR(50),  -- System or manual override by user
    allocated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, period_month)
);

CREATE INDEX idx_allocations_agent_month ON allocations(owner_agent_id, period_month);
CREATE INDEX idx_allocations_account_month ON allocations(account_id, period_month);
CREATE INDEX idx_allocations_month ON allocations(period_month);

-- Beat Plan (field agent daily route)
CREATE TABLE beat_plan (
    beat_id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    beat_date DATE NOT NULL,
    account_id VARCHAR(50) NOT NULL REFERENCES dim_account(account_id),
    sequence_no INTEGER NOT NULL,  -- Visit order for the day
    priority VARCHAR(20),  -- HIGH, MEDIUM, LOW
    expected_collection DECIMAL(10, 2),
    visit_reason VARCHAR(200),
    notes TEXT,
    completed BOOLEAN DEFAULT false,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(agent_id, beat_date, account_id)
);

CREATE INDEX idx_beat_plan_agent_date ON beat_plan(agent_id, beat_date, sequence_no);
CREATE INDEX idx_beat_plan_account ON beat_plan(account_id);
CREATE INDEX idx_beat_plan_pending ON beat_plan(agent_id, beat_date) WHERE completed = false;

-- Dispositions (append-only audit log of all actions)
CREATE TABLE dispositions (
    disposition_id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL REFERENCES dim_account(account_id),
    customer_id VARCHAR(50) NOT NULL REFERENCES dim_customer(customer_id),
    agent_id VARCHAR(50),
    channel channel_type NOT NULL,
    disposition disposition_type NOT NULL,
    call_id INTEGER REFERENCES fct_calls(call_id),
    visit_id INTEGER REFERENCES fct_visits(visit_id),
    notes TEXT,
    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    captured_by VARCHAR(50) NOT NULL  -- Agent or system
);

-- No updates allowed - append only
CREATE INDEX idx_dispositions_account ON dispositions(account_id);
CREATE INDEX idx_dispositions_agent ON dispositions(agent_id);
CREATE INDEX idx_dispositions_date ON dispositions(DATE(captured_at));
CREATE INDEX idx_dispositions_disposition ON dispositions(disposition);

-- Payment Links (for UPI)
CREATE TABLE payment_links (
    link_id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL REFERENCES dim_account(account_id),
    amount DECIMAL(10, 2) NOT NULL,
    link_url VARCHAR(500) NOT NULL,
    sent_via channel_type,
    sent_to VARCHAR(50),  -- Phone or email
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    clicked BOOLEAN DEFAULT false,
    clicked_at TIMESTAMP,
    paid BOOLEAN DEFAULT false,
    paid_at TIMESTAMP,
    payment_id INTEGER REFERENCES fct_payments(payment_id)
);

CREATE INDEX idx_payment_links_account ON payment_links(account_id);
CREATE INDEX idx_payment_links_sent ON payment_links(sent_at);
CREATE INDEX idx_payment_links_pending ON payment_links(account_id) WHERE paid = false AND expires_at > CURRENT_TIMESTAMP;

-- Triggers
CREATE TRIGGER update_campaigns_updated_at BEFORE UPDATE ON campaigns FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_call_queue_updated_at BEFORE UPDATE ON call_queue FOR EACH ROW EXECUTE FUNCTION update_updated_at();

COMMENT ON TABLE call_queue IS 'Scheduled calls for bot and telecallers with priority and slotting';
COMMENT ON TABLE allocations IS 'Monthly account ownership assignments with transparency';
COMMENT ON TABLE beat_plan IS 'Daily field agent routes with ordered visit sequence';
COMMENT ON TABLE dispositions IS 'Append-only log of all collector actions for audit';
