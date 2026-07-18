-- Migration 002: Dimension Tables
-- Customer, Account, Agent, Team, Geography dimensions
-- Created: 2026-07-19

-- Geography dimension (pincode → city → state → zone)
CREATE TABLE dim_geo (
    geo_id SERIAL PRIMARY KEY,
    pincode VARCHAR(6) NOT NULL UNIQUE,
    city VARCHAR(100) NOT NULL,
    district VARCHAR(100),
    state VARCHAR(100) NOT NULL,
    zone VARCHAR(50) NOT NULL,  -- North, South, East, West, Central
    lat DECIMAL(10, 8),
    lon DECIMAL(11, 8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dim_geo_state_city ON dim_geo(state, city);
CREATE INDEX idx_dim_geo_zone ON dim_geo(zone);

-- Customer dimension (SCD Type 1 - current state only)
CREATE TABLE dim_customer (
    customer_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    dob DATE,
    segment VARCHAR(20),  -- FTB, SRTO, MRTO, LRTO, CAPTIVE
    lang_pref VARCHAR(10) DEFAULT 'en',  -- en, hi, ta, te, mr, gu, etc.
    addr_line1 VARCHAR(200),
    addr_line2 VARCHAR(200),
    city VARCHAR(100),
    state VARCHAR(100),
    pincode VARCHAR(6),
    geo_id INTEGER REFERENCES dim_geo(geo_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dim_customer_segment ON dim_customer(segment);
CREATE INDEX idx_dim_customer_geo ON dim_customer(geo_id);
CREATE INDEX idx_dim_customer_name_trgm ON dim_customer USING gin(name gin_trgm_ops);

-- Customer contacts (one-to-many)
CREATE TABLE dim_customer_contacts (
    contact_id SERIAL PRIMARY KEY,
    customer_id VARCHAR(50) REFERENCES dim_customer(customer_id),
    phone VARCHAR(15) NOT NULL,
    phone_type VARCHAR(20) DEFAULT 'mobile',  -- mobile, landline, alternate
    is_primary BOOLEAN DEFAULT false,
    dnc_flag BOOLEAN DEFAULT false,
    last_verified TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(customer_id, phone)
);

CREATE INDEX idx_contacts_customer ON dim_customer_contacts(customer_id);
CREATE INDEX idx_contacts_phone ON dim_customer_contacts(phone);
CREATE INDEX idx_contacts_primary ON dim_customer_contacts(customer_id, is_primary) WHERE is_primary = true;

-- Account dimension
CREATE TABLE dim_account (
    account_id VARCHAR(50) PRIMARY KEY,
    customer_id VARCHAR(50) NOT NULL REFERENCES dim_customer(customer_id),
    product_type VARCHAR(50) NOT NULL,  -- HCV, LCV, TIPPER, TRACTOR, EXCAVATOR, etc.
    asset_desc VARCHAR(200),
    disbursal_date DATE NOT NULL,
    disbursal_amt DECIMAL(12, 2) NOT NULL,
    tenure_m INTEGER NOT NULL,
    roi DECIMAL(5, 2) NOT NULL,
    emi_amt DECIMAL(10, 2) NOT NULL,
    cycle_day INTEGER NOT NULL CHECK (cycle_day IN (1, 5, 10, 15)),
    branch VARCHAR(100),
    state VARCHAR(100),
    city VARCHAR(100),
    pincode VARCHAR(6),
    geo_id INTEGER REFERENCES dim_geo(geo_id),
    status VARCHAR(20) DEFAULT 'ACTIVE',  -- ACTIVE, CLOSED, WRITTEN_OFF
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valid_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valid_to TIMESTAMP DEFAULT '9999-12-31'::timestamp
);

CREATE INDEX idx_dim_account_customer ON dim_account(customer_id);
CREATE INDEX idx_dim_account_product ON dim_account(product_type);
CREATE INDEX idx_dim_account_status ON dim_account(status) WHERE status = 'ACTIVE';
CREATE INDEX idx_dim_account_cycle_day ON dim_account(cycle_day);
CREATE INDEX idx_dim_account_geo ON dim_account(geo_id);

-- EMI schedule (account x installment)
CREATE TABLE dim_emi_schedule (
    schedule_id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL REFERENCES dim_account(account_id),
    inst_no INTEGER NOT NULL,
    due_date DATE NOT NULL,
    emi_amt DECIMAL(10, 2) NOT NULL,
    principal DECIMAL(10, 2) NOT NULL,
    interest DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, inst_no)
);

CREATE INDEX idx_emi_schedule_account ON dim_emi_schedule(account_id);
CREATE INDEX idx_emi_schedule_due_date ON dim_emi_schedule(due_date);

-- Team dimension
CREATE TABLE dim_team (
    team_id SERIAL PRIMARY KEY,
    team_name VARCHAR(100) NOT NULL UNIQUE,
    team_type VARCHAR(20) NOT NULL,  -- FOS, TC, MIXED
    parent_team_id INTEGER REFERENCES dim_team(team_id),
    zone VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dim_team_type ON dim_team(team_type);
CREATE INDEX idx_dim_team_zone ON dim_team(zone);

-- Agent dimension (SCD Type 2 - track history)
CREATE TABLE dim_agent (
    agent_id VARCHAR(50),
    surrogate_key SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    role agent_role_type NOT NULL,
    team_id INTEGER REFERENCES dim_team(team_id),
    supervisor_id VARCHAR(50),  -- References agent_id
    base_pincode VARCHAR(6),
    base_geo_id INTEGER REFERENCES dim_geo(geo_id),
    langs VARCHAR(50)[],  -- Array of language codes
    capacity_override INTEGER,  -- Override default capacity for this agent
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valid_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valid_to TIMESTAMP DEFAULT '9999-12-31'::timestamp
);

CREATE INDEX idx_dim_agent_id ON dim_agent(agent_id);
CREATE INDEX idx_dim_agent_active ON dim_agent(agent_id, valid_to) WHERE active = true AND valid_to = '9999-12-31';
CREATE INDEX idx_dim_agent_role ON dim_agent(role);
CREATE INDEX idx_dim_agent_team ON dim_agent(team_id);
CREATE INDEX idx_dim_agent_supervisor ON dim_agent(supervisor_id);
CREATE INDEX idx_dim_agent_geo ON dim_agent(base_geo_id);

-- Add triggers for updated_at
CREATE TRIGGER update_dim_geo_updated_at BEFORE UPDATE ON dim_geo FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_dim_customer_updated_at BEFORE UPDATE ON dim_customer FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_dim_customer_contacts_updated_at BEFORE UPDATE ON dim_customer_contacts FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_dim_account_updated_at BEFORE UPDATE ON dim_account FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_dim_team_updated_at BEFORE UPDATE ON dim_team FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_dim_agent_updated_at BEFORE UPDATE ON dim_agent FOR EACH ROW EXECUTE FUNCTION update_updated_at();
