-- Migration 003: Fact Tables
-- Transactional events: presentations, payments, bounces, calls, visits, PTPs, SMS
-- Created: 2026-07-19

-- NACH Presentations
CREATE TABLE fct_presentations (
    presentation_id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL REFERENCES dim_account(account_id),
    present_date DATE NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(10) NOT NULL CHECK (status IN ('S', 'B')),  -- Success or Bounce
    bounce_reason VARCHAR(100),
    inst_no INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_fct_presentations_account ON fct_presentations(account_id);
CREATE INDEX idx_fct_presentations_date ON fct_presentations(present_date);
CREATE INDEX idx_fct_presentations_status ON fct_presentations(status);
CREATE INDEX idx_fct_presentations_account_date ON fct_presentations(account_id, present_date);

-- Payments
CREATE TABLE fct_payments (
    payment_id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL REFERENCES dim_account(account_id),
    pay_date DATE NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    mode VARCHAR(50),  -- NACH, UPI, CASH, CHEQUE, NEFT, etc.
    alloc_to_inst INTEGER,
    reference_no VARCHAR(100),
    collected_by VARCHAR(50),  -- agent_id if field collection
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_fct_payments_account ON fct_payments(account_id);
CREATE INDEX idx_fct_payments_date ON fct_payments(pay_date);
CREATE INDEX idx_fct_payments_mode ON fct_payments(mode);
CREATE INDEX idx_fct_payments_account_date ON fct_payments(account_id, pay_date);

-- Bounces (denormalized from presentations for quick access)
CREATE TABLE fct_bounces (
    bounce_id SERIAL PRIMARY KEY,
    presentation_id INTEGER REFERENCES fct_presentations(presentation_id),
    account_id VARCHAR(50) NOT NULL REFERENCES dim_account(account_id),
    bounce_date DATE NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    bounce_reason VARCHAR(100),
    inst_no INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_fct_bounces_account ON fct_bounces(account_id);
CREATE INDEX idx_fct_bounces_date ON fct_bounces(bounce_date);
CREATE INDEX idx_fct_bounces_account_date ON fct_bounces(account_id, bounce_date);

-- Calls (bot + human)
CREATE TABLE fct_calls (
    call_id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL REFERENCES dim_account(account_id),
    customer_id VARCHAR(50) NOT NULL REFERENCES dim_customer(customer_id),
    phone VARCHAR(15) NOT NULL,
    channel channel_type NOT NULL,
    agent_id VARCHAR(50),  -- NULL for bot
    campaign_id INTEGER,  -- References campaigns table (to be created in 005)
    call_start_time TIMESTAMP NOT NULL,
    call_end_time TIMESTAMP,
    duration_sec INTEGER,
    outcome call_outcome_type NOT NULL,
    disposition disposition_type,
    notes TEXT,
    transcript_path VARCHAR(500),  -- Path to call recording/transcript
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_fct_calls_account ON fct_calls(account_id);
CREATE INDEX idx_fct_calls_customer ON fct_calls(customer_id);
CREATE INDEX idx_fct_calls_date ON fct_calls(DATE(call_start_time));
CREATE INDEX idx_fct_calls_channel ON fct_calls(channel);
CREATE INDEX idx_fct_calls_agent ON fct_calls(agent_id) WHERE agent_id IS NOT NULL;
CREATE INDEX idx_fct_calls_outcome ON fct_calls(outcome);

-- Field Visits
CREATE TABLE fct_visits (
    visit_id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL REFERENCES dim_account(account_id),
    customer_id VARCHAR(50) NOT NULL REFERENCES dim_customer(customer_id),
    agent_id VARCHAR(50) NOT NULL,
    visit_date DATE NOT NULL,
    visit_time TIMESTAMP NOT NULL,
    disposition disposition_type NOT NULL,
    amount_collected DECIMAL(10, 2) DEFAULT 0,
    payment_mode VARCHAR(50),
    payment_ref VARCHAR(100),
    geo_lat DECIMAL(10, 8),  -- Geo-stamped location
    geo_lon DECIMAL(11, 8),
    photo_path VARCHAR(500),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_fct_visits_account ON fct_visits(account_id);
CREATE INDEX idx_fct_visits_agent ON fct_visits(agent_id);
CREATE INDEX idx_fct_visits_date ON fct_visits(visit_date);
CREATE INDEX idx_fct_visits_agent_date ON fct_visits(agent_id, visit_date);

-- Promises to Pay (PTPs)
CREATE TABLE fct_ptp (
    ptp_id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL REFERENCES dim_account(account_id),
    customer_id VARCHAR(50) NOT NULL REFERENCES dim_customer(customer_id),
    made_by VARCHAR(50) NOT NULL,  -- agent_id
    channel channel_type NOT NULL,
    call_id INTEGER REFERENCES fct_calls(call_id),
    visit_id INTEGER REFERENCES fct_visits(visit_id),
    promise_date DATE NOT NULL,
    promise_amount DECIMAL(10, 2) NOT NULL,
    payment_mode VARCHAR(50),
    status ptp_status_type DEFAULT 'OPEN',
    kept_date DATE,
    kept_amount DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_fct_ptp_account ON fct_ptp(account_id);
CREATE INDEX idx_fct_ptp_status ON fct_ptp(status);
CREATE INDEX idx_fct_ptp_promise_date ON fct_ptp(promise_date);
CREATE INDEX idx_fct_ptp_open ON fct_ptp(account_id, status) WHERE status = 'OPEN';
CREATE INDEX idx_fct_ptp_made_by ON fct_ptp(made_by);

-- SMS Outbox
CREATE TABLE fct_sms (
    sms_id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) REFERENCES dim_account(account_id),
    customer_id VARCHAR(50) REFERENCES dim_customer(customer_id),
    phone VARCHAR(15) NOT NULL,
    message_text TEXT NOT NULL,
    campaign_id INTEGER,
    scheduled_at TIMESTAMP NOT NULL,
    sent_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'PENDING',  -- PENDING, SENT, FAILED, DNC_BLOCKED
    gateway_msg_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_fct_sms_account ON fct_sms(account_id);
CREATE INDEX idx_fct_sms_phone ON fct_sms(phone);
CREATE INDEX idx_fct_sms_status ON fct_sms(status) WHERE status = 'PENDING';
CREATE INDEX idx_fct_sms_scheduled ON fct_sms(scheduled_at) WHERE status = 'PENDING';

-- Add triggers
CREATE TRIGGER update_fct_ptp_updated_at BEFORE UPDATE ON fct_ptp FOR EACH ROW EXECUTE FUNCTION update_updated_at();

COMMENT ON TABLE fct_calls IS 'All collection calls (bot and human) with dispositions and outcomes';
COMMENT ON TABLE fct_visits IS 'Field agent visits with geo-stamps and collection details';
COMMENT ON TABLE fct_ptp IS 'Promises to pay with tracking of kept/broken status';
