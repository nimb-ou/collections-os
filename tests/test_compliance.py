"""
Compliance Guardrail Tests for Collections OS
Validates RBI Fair Practices Code and FDCPA regulatory constraints:
1. Permitted contact hours (08:00 to 19:00).
2. Max daily contact frequency (calls <= 2, visits <= 1).
3. Cooling-off intervals between consecutive interactions (>= 4h).
4. Do-Not-Call (DNC) flag adherence.
5. Sunday and public holiday restrictions.
"""

import pytest
from datetime import datetime, time
from api.routers.campaigns import validate_contact_compliance, ComplianceCheckRequest

def test_permitted_calling_window_valid():
    # 10:30 AM on a weekday
    dt = datetime(2026, 7, 22, 10, 30, 0)
    req = ComplianceCheckRequest(
        account_id="ACC-001",
        contact_type="CALL",
        attempt_time=dt,
        calls_today=0,
        hours_since_last_contact=48.0
    )
    res = validate_contact_compliance(req)
    assert res.allowed is True
    assert len(res.violations) == 0

def test_calling_window_too_early():
    # 07:15 AM - before 08:00 AM
    dt = datetime(2026, 7, 22, 7, 15, 0)
    req = ComplianceCheckRequest(
        account_id="ACC-002",
        contact_type="CALL",
        attempt_time=dt,
        calls_today=0
    )
    res = validate_contact_compliance(req)
    assert res.allowed is False
    assert any("outside permitted window" in v for v in res.violations)

def test_calling_window_too_late():
    # 20:30 PM - after 19:00 PM
    dt = datetime(2026, 7, 22, 20, 30, 0)
    req = ComplianceCheckRequest(
        account_id="ACC-003",
        contact_type="CALL",
        attempt_time=dt,
        calls_today=0
    )
    res = validate_contact_compliance(req)
    assert res.allowed is False
    assert any("outside permitted window" in v for v in res.violations)

def test_max_daily_calls_exceeded():
    # 3 calls already made today
    dt = datetime(2026, 7, 22, 14, 0, 0)
    req = ComplianceCheckRequest(
        account_id="ACC-004",
        contact_type="CALL",
        attempt_time=dt,
        calls_today=2
    )
    res = validate_contact_compliance(req)
    assert res.allowed is False
    assert any("Exceeded max daily calls" in v for v in res.violations)

def test_max_daily_field_visits_exceeded():
    # 1 field visit already performed
    dt = datetime(2026, 7, 22, 11, 0, 0)
    req = ComplianceCheckRequest(
        account_id="ACC-005",
        contact_type="VISIT",
        attempt_time=dt,
        visits_today=1
    )
    res = validate_contact_compliance(req)
    assert res.allowed is False
    assert any("Exceeded max daily field visits" in v for v in res.violations)

def test_dnc_flag_prohibits_contact():
    dt = datetime(2026, 7, 22, 12, 0, 0)
    req = ComplianceCheckRequest(
        account_id="ACC-006",
        contact_type="CALL",
        attempt_time=dt,
        is_dnc=True
    )
    res = validate_contact_compliance(req)
    assert res.allowed is False
    assert any("Do-Not-Call" in v for v in res.violations)

def test_sunday_restriction():
    # 2026-07-26 is a Sunday
    dt = datetime(2026, 7, 26, 12, 0, 0)
    req = ComplianceCheckRequest(
        account_id="ACC-007",
        contact_type="CALL",
        attempt_time=dt,
        is_sunday=True
    )
    res = validate_contact_compliance(req)
    assert res.allowed is False
    assert any("Sundays" in v for v in res.violations)

def test_cool_off_interval_enforced():
    # Only 1.5 hours since previous contact
    dt = datetime(2026, 7, 22, 14, 0, 0)
    req = ComplianceCheckRequest(
        account_id="ACC-008",
        contact_type="CALL",
        attempt_time=dt,
        hours_since_last_contact=1.5
    )
    res = validate_contact_compliance(req)
    assert res.allowed is False
    assert any("Cool-off violation" in v for v in res.violations)
