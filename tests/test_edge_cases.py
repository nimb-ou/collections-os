"""
Edge Case and Robustness Tests for Collections OS
Validates boundary values, missing attributes, extreme balance tiers,
and strict compliance limit enforcement under edge-case scenarios.
"""

import pytest
from datetime import datetime, time
from strategy.treatment import TreatmentEngine
from api.routers.campaigns import validate_contact_compliance, ComplianceCheckRequest, CampaignCreate


@pytest.fixture
def engine():
    return TreatmentEngine()


def test_extreme_overdue_amounts(engine):
    """Verify value band classification across zero, negative, and extreme balances."""
    assert engine.classify_value_band(0.0) == "low"
    assert engine.classify_value_band(-1500.0) == "low"
    assert engine.classify_value_band(100_000_000.0) == "very_high"


def test_boundary_risk_bands(engine):
    """Verify exact boundary conditions for bounce probability risk bands."""
    # 0.0 is low risk (< 0.10)
    assert engine.classify_risk_band(0.0) == "low"
    assert engine.classify_risk_band(0.09) == "low"
    # Exact thresholds from rules (< 0.35 is medium, < 0.60 is high)
    assert engine.classify_risk_band(0.10) == "medium"
    assert engine.classify_risk_band(0.35) == "high"
    assert engine.classify_risk_band(0.60) == "very_high"
    # Saturated risk
    assert engine.classify_risk_band(1.0) == "very_high"


def test_missing_optional_account_fields(engine):
    """Verify that an account payload with minimal or missing fields falls back deterministically."""
    minimal_account = {
        "account_id": "ACC-EDGE-SPARSE"
    }
    result = engine.assign_treatment(minimal_account)
    assert "treatment_code" in result
    assert result["treatment_code"] in engine.treatments


def test_compliance_exact_time_boundaries():
    """Verify window enforcement at exact 08:00:00 and 19:00:00 boundary seconds."""
    # 08:00:00 - exactly on opening second (weekday)
    t_open = datetime(2026, 7, 22, 8, 0, 0)
    req_open = ComplianceCheckRequest(
        account_id="ACC-TIME-01",
        contact_type="CALL",
        attempt_time=t_open,
        calls_today=0,
        hours_since_last_contact=24.0
    )
    res_open = validate_contact_compliance(req_open)
    assert res_open.allowed is True

    # 19:00:00 - exactly on closing second
    t_close = datetime(2026, 7, 22, 19, 0, 0)
    req_close = ComplianceCheckRequest(
        account_id="ACC-TIME-02",
        contact_type="CALL",
        attempt_time=t_close,
        calls_today=0,
        hours_since_last_contact=24.0
    )
    res_close = validate_contact_compliance(req_close)
    assert res_close.allowed is True

    # 07:59:59 - 1 second too early
    t_early = datetime(2026, 7, 22, 7, 59, 59)
    req_early = ComplianceCheckRequest(
        account_id="ACC-TIME-03",
        contact_type="CALL",
        attempt_time=t_early,
        calls_today=0,
        hours_since_last_contact=24.0
    )
    res_early = validate_contact_compliance(req_early)
    assert res_early.allowed is False
    assert any("outside permitted window" in v for v in res_early.violations)

    # 19:00:01 - 1 second too late
    t_late = datetime(2026, 7, 22, 19, 0, 1)
    req_late = ComplianceCheckRequest(
        account_id="ACC-TIME-04",
        contact_type="CALL",
        attempt_time=t_late,
        calls_today=0,
        hours_since_last_contact=24.0
    )
    res_late = validate_contact_compliance(req_late)
    assert res_late.allowed is False
    assert any("outside permitted window" in v for v in res_late.violations)


def test_compliance_multiple_simultaneous_violations():
    """Verify that multiple simultaneous rule breaches are all captured in violations list."""
    # Sunday + DNC + 3 calls already + 0.5h since last contact + 21:00 PM
    dt_night_sunday = datetime(2026, 7, 26, 21, 0, 0)
    req = ComplianceCheckRequest(
        account_id="ACC-MULTI-VIOLATION",
        contact_type="CALL",
        attempt_time=dt_night_sunday,
        calls_today=3,
        hours_since_last_contact=0.5,
        is_dnc=True,
        is_sunday=True
    )
    res = validate_contact_compliance(req)
    assert res.allowed is False
    assert len(res.violations) >= 4
    # All 4 violations must be present
    assert any("Do-Not-Call" in v for v in res.violations)
    assert any("outside permitted window" in v for v in res.violations)
    assert any("Sundays" in v for v in res.violations)
    assert any("Exceeded max daily calls" in v for v in res.violations)
    assert any("Cool-off violation" in v for v in res.violations)


def test_compliance_public_holiday():
    """Verify public holiday block prevents contact."""
    dt = datetime(2026, 8, 15, 11, 0, 0)  # Independence Day
    req = ComplianceCheckRequest(
        account_id="ACC-HOLIDAY",
        contact_type="CALL",
        attempt_time=dt,
        is_holiday=True
    )
    res = validate_contact_compliance(req)
    assert res.allowed is False
    assert any("Public Holidays" in v for v in res.violations)


def test_campaign_model_schema_validation():
    """Verify CampaignCreate model behaves as expected with defaults and overrides."""
    campaign = CampaignCreate(
        name="High Balance Escalation",
        channel="TELECALLER",
        buckets=["B2", "B3", "NPA1"],
        min_overdue_amt=50000.0,
        max_risk_band="very_high"
    )
    assert campaign.name == "High Balance Escalation"
    assert campaign.channel == "TELECALLER"
    assert campaign.min_overdue_amt == 50000.0
    assert len(campaign.buckets) == 3
