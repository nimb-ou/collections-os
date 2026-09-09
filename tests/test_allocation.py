"""
Treatment and Allocation Tests for Collections OS
Validates deterministic rule assignment and risk/value band mapping.
"""

import pytest
from strategy.treatment import TreatmentEngine

@pytest.fixture
def engine():
    return TreatmentEngine()

def test_classify_risk_band(engine):
    assert engine.classify_risk_band(0.05) == "low"
    assert engine.classify_risk_band(0.20) == "medium"
    assert engine.classify_risk_band(0.50) == "high"
    assert engine.classify_risk_band(0.85) == "very_high"

def test_classify_value_band(engine):
    assert engine.classify_value_band(5000.0) == "low"
    assert engine.classify_value_band(18000.0) == "medium"
    assert engine.classify_value_band(35000.0) == "high"
    assert engine.classify_value_band(85000.0) == "very_high"

def test_active_ptp_rule_assignment(engine):
    account = {
        "account_id": "ACC-PTP-01",
        "has_active_ptp": True,
        "days_to_ptp": 1,
        "bucket": "B1",
        "bounce_p": 0.45,
        "overdue_amt": 20000.0
    }
    res = engine.assign_treatment(account)
    assert res["treatment_code"] == "T009_PTP_REMINDER"
    assert res["assigned_reason"] == "Active PTP Reminder"

def test_high_selfcure_suppression_rule(engine):
    account = {
        "account_id": "ACC-SC-01",
        "has_active_ptp": False,
        "bucket": "B1",
        "bounce_p": 0.25,
        "selfcure_p": 0.75,
        "days_since_bounce": 1,
        "overdue_amt": 15000.0
    }
    res = engine.assign_treatment(account)
    assert res["treatment_code"] == "T004_SUPPRESS_SELFCURE"
    assert res["assigned_reason"] == "Bounced High Self-cure"

def test_hard_collection_rule_for_npa(engine):
    account = {
        "account_id": "ACC-NPA-01",
        "has_active_ptp": False,
        "bucket": "NPA1",
        "bounce_p": 0.90,
        "selfcure_p": 0.05,
        "overdue_amt": 120000.0
    }
    res = engine.assign_treatment(account)
    assert res["treatment_code"] == "T008_HARD_COLLECT"
    assert res["assigned_reason"] == "90+ Hard Collection"

def test_default_treatment_fallback(engine):
    account = {
        "account_id": "ACC-DEF-01",
        "has_active_ptp": False,
        "bucket": "UNKNOWN",
        "bounce_p": 0.01,
        "overdue_amt": 100.0
    }
    res = engine.assign_treatment(account)
    assert res["treatment_code"] in engine.treatments
