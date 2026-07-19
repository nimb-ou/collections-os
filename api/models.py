"""
Pydantic Models for API Request/Response Validation
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal


# ============================================================================
# Authentication Models
# ============================================================================

class LoginRequest(BaseModel):
    """Login request payload."""
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    role: str
    agent_id: Optional[str] = None


# ============================================================================
# Account Models
# ============================================================================

class AccountCard(BaseModel):
    """Account insight card with collection reasons."""
    account_id: str
    customer_id: str
    customer_name: Optional[str]
    product_type: str
    bucket: str
    dpd: int
    overdue_amt: Decimal
    pos: Decimal
    emi_amt: Decimal
    bounce_p: Optional[float]
    selfcure_p: Optional[float]
    treatment_code: Optional[str]
    owner_agent_id: Optional[str]
    last_contact_date: Optional[datetime]
    top_reasons: Optional[List[Dict[str, Any]]]  # SHAP reasons
    phone_numbers: Optional[List[str]]
    address: Optional[str]


class AccountHistory(BaseModel):
    """Account historical events."""
    presentations: List[Dict[str, Any]]
    payments: List[Dict[str, Any]]
    calls: List[Dict[str, Any]]
    visits: List[Dict[str, Any]]
    ptps: List[Dict[str, Any]]


# ============================================================================
# Queue Models
# ============================================================================

class QueueItem(BaseModel):
    """Next call queue item for an agent."""
    queue_id: int
    account_id: str
    customer_name: str
    phone_number: str
    bucket: str
    overdue_amt: Decimal
    priority: int
    treatment_code: str
    recommended_script: Optional[str]
    top_reasons: Optional[List[str]]
    last_disposition: Optional[str]


# ============================================================================
# Disposition Models
# ============================================================================

class DispositionCreate(BaseModel):
    """Create a new disposition."""
    account_id: str
    customer_id: str
    agent_id: Optional[str]
    channel: str  # BOT, TELECALLER, FIELD, SMS
    disposition: str  # CONNECT_RPC, PTP, NO_ANSWER, etc.
    call_id: Optional[int]
    visit_id: Optional[int]
    notes: Optional[str]


class DispositionResponse(BaseModel):
    """Disposition creation response."""
    disposition_id: int
    captured_at: datetime


# ============================================================================
# PTP Models
# ============================================================================

class PTPCreate(BaseModel):
    """Create a promise to pay."""
    account_id: str
    customer_id: str
    made_by_agent_id: str
    channel: str
    promise_date: date
    promise_amount: Decimal
    payment_mode: Optional[str]  # NACH, UPI, Cash, etc.
    notes: Optional[str]


class PTPResponse(BaseModel):
    """PTP creation response."""
    ptp_id: int
    account_id: str
    promise_date: date
    promise_amount: Decimal
    status: str


class PTPBookItem(BaseModel):
    """PTP book entry."""
    ptp_id: int
    account_id: str
    customer_name: str
    promise_date: date
    promise_amount: Decimal
    status: str
    made_by: str
    made_at: datetime
    days_to_maturity: int


# ============================================================================
# Payment Models
# ============================================================================

class PaymentCreate(BaseModel):
    """Create a payment record (dev mode)."""
    account_id: str
    payment_date: date
    amount: Decimal
    payment_mode: str
    reference_no: Optional[str]
    allocated_to_inst_no: Optional[int]


class PaymentResponse(BaseModel):
    """Payment creation response."""
    payment_id: int
    account_id: str
    amount: Decimal
    payment_date: date


# ============================================================================
# Beat Plan Models
# ============================================================================

class BeatPlanStop(BaseModel):
    """Beat plan stop for field agent."""
    beat_id: int
    account_id: str
    customer_name: str
    address: str
    sequence_no: int
    priority: str
    expected_collection: Decimal
    visit_reason: str
    latitude: Optional[float]
    longitude: Optional[float]
    completed: bool


# ============================================================================
# Scorecard Models
# ============================================================================

class AgentScorecard(BaseModel):
    """Agent performance scorecard."""
    agent_id: str
    agent_name: str
    date: date
    metrics: Dict[str, Any]  # Dynamic metrics from JSONB
    composite_score: Optional[float]
    rank: Optional[int]
    percentile: Optional[float]


# ============================================================================
# Campaign Models
# ============================================================================

class CampaignCreate(BaseModel):
    """Create a new campaign."""
    name: str
    campaign_type: str
    start_date: date
    end_date: Optional[date]
    target_bucket: Optional[str]
    treatment_codes: List[str]
    control_group_pct: float = Field(default=0.05, ge=0, le=0.5)
    active: bool = True


class CampaignResponse(BaseModel):
    """Campaign response."""
    campaign_id: int
    name: str
    campaign_type: str
    start_date: date
    created_at: datetime


# ============================================================================
# Intervention Models
# ============================================================================

class InterventionUpdate(BaseModel):
    """Update intervention status."""
    status: str  # open, acked, resolved
    assigned_to: Optional[str]
    resolution_notes: Optional[str]


class InterventionResponse(BaseModel):
    """Intervention detail."""
    intervention_id: int
    severity: str
    entity_type: str
    entity_id: str
    issue_type: str
    description: str
    recommended_action: str
    status: str
    created_at: datetime
    resolved_at: Optional[datetime]
