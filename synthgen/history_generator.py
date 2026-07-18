"""
History Generator
Generates 24-month behavioral history for all accounts
Implements archetype-specific bounce/cure patterns with seasonality and contact effects
"""
import random
from datetime import date, timedelta
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
import logging

from .config import ARCHETYPE_PARAMS, PRODUCT_SPECS

logger = logging.getLogger(__name__)


@dataclass
class AccountState:
    """Track account state through time"""
    account_id: str
    archetype: str
    product_type: str
    disbursal_date: date
    emi_amt: float
    cycle_day: int
    tenure_m: int

    # Current state
    current_dpd: int = 0
    current_bucket: str = "X"
    pos: float = 0  # Principal Outstanding
    overdue_amt: float = 0
    last_payment_date: Optional[date] = None
    last_contact_date: Optional[date] = None
    last_contact_channel: Optional[str] = None
    open_ptp: Optional[Dict] = None
    bounces_in_last_3m: int = 0
    payments_in_last_3m: int = 0

    # History
    bounce_dates: List[date] = None
    payment_dates: List[date] = None

    def __post_init__(self):
        if self.bounce_dates is None:
            self.bounce_dates = []
        if self.payment_dates is None:
            self.payment_dates = []


@dataclass
class PresentationEvent:
    """EMI presentation event"""
    account_id: str
    present_date: date
    amount: float
    inst_no: int
    status: str  # 'S' or 'B'
    bounce_reason: Optional[str] = None


@dataclass
class PaymentEvent:
    """Payment event"""
    account_id: str
    pay_date: date
    amount: float
    mode: str
    alloc_to_inst: Optional[int] = None
    collected_by: Optional[str] = None


@dataclass
class CallEvent:
    """Call event"""
    account_id: str
    customer_id: str
    phone: str
    channel: str  # 'TELECALLER' or 'BOT'
    agent_id: Optional[str]
    call_start_time: date
    outcome: str  # 'CONNECTED', 'NO_ANSWER', etc.
    disposition: Optional[str]
    duration_sec: Optional[int] = None


@dataclass
class VisitEvent:
    """Field visit event"""
    account_id: str
    customer_id: str
    agent_id: str
    visit_date: date
    disposition: str
    amount_collected: float = 0
    payment_mode: Optional[str] = None


@dataclass
class PTPEvent:
    """Promise to Pay event"""
    account_id: str
    customer_id: str
    made_by: str
    channel: str
    promise_date: date
    promise_amount: float
    payment_mode: Optional[str]
    status: str = 'OPEN'


@dataclass
class SMSEvent:
    """SMS event"""
    account_id: str
    customer_id: str
    phone: str
    message_text: str
    scheduled_at: date
    status: str = 'SENT'


@dataclass
class MartSnapshot:
    """Daily mart_account_daily snapshot"""
    account_id: str
    date: date
    dpd: int
    bucket: str
    overdue_amt: float
    pos: float
    total_dues: float
    emi_amt: float
    cycle_day: int
    last_contact_date: Optional[date] = None
    last_contact_channel: Optional[str] = None
    last_payment_date: Optional[date] = None
    last_payment_amt: Optional[float] = None
    has_open_ptp: bool = False


class HistoryGenerator:
    """Generates behavioral history for the entire portfolio"""

    BOUNCE_REASONS = [
        "INSUFFICIENT_FUNDS",
        "ACCOUNT_CLOSED",
        "PAYMENT_STOPPED",
        "TECHNICAL_ISSUE",
        "MANDATE_CANCELLED",
    ]

    PAYMENT_MODES = ["NACH", "UPI", "NEFT", "CASH", "CHEQUE"]

    CALL_DISPOSITIONS = [
        "CONNECT_RPC",
        "PTP",
        "PAID_CLAIM",
        "NOT_INTERESTED",
        "CALLBACK",
        "DISPUTE",
        "HARDSHIP",
    ]

    VISIT_DISPOSITIONS = [
        "VISIT_MET",
        "COLLECTED",
        "PTP",
        "VISIT_NOT_FOUND",
        "ADDRESS_ISSUE",
    ]

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.accounts: List[AccountState] = []
        self.presentations: List[PresentationEvent] = []
        self.payments: List[PaymentEvent] = []
        self.bounces: List[PresentationEvent] = []
        self.calls: List[CallEvent] = []
        self.visits: List[VisitEvent] = []
        self.ptps: List[PTPEvent] = []
        self.sms: List[SMSEvent] = []
        self.mart_snapshots: List[MartSnapshot] = []

    def generate_history(
        self,
        accounts_data: List[Dict],
        customers_data: Dict[str, Dict],
        agents_data: List[Dict],
        start_date: date,
        months: int = 24
    ) -> Tuple[List, List, List, List, List, List, List]:
        """
        Generate full behavioral history
        Returns: (presentations, payments, calls, visits, ptps, sms, mart_snapshots)
        """
        logger.info(f"Generating {months}-month history for {len(accounts_data)} accounts...")

        # Initialize account states
        self._initialize_accounts(accounts_data, start_date)

        # Month-by-month simulation
        current_date = start_date
        for month_num in range(months):
            month_start = self._add_months(start_date, month_num)
            month_end = self._add_months(month_start, 1) - timedelta(days=1)

            if month_num % 3 == 0:
                logger.info(f"  Processing month {month_num+1}/{months}: {month_start.strftime('%Y-%m')}...")

            self._simulate_month(
                month_start,
                month_end,
                customers_data,
                agents_data,
                month_num
            )

        logger.info(f"✓ Generated history:")
        logger.info(f"  Presentations: {len(self.presentations):,}")
        logger.info(f"  Bounces: {len(self.bounces):,}")
        logger.info(f"  Payments: {len(self.payments):,}")
        logger.info(f"  Calls: {len(self.calls):,}")
        logger.info(f"  Visits: {len(self.visits):,}")
        logger.info(f"  PTPs: {len(self.ptps):,}")
        logger.info(f"  SMS: {len(self.sms):,}")
        logger.info(f"  Mart snapshots: {len(self.mart_snapshots):,}")

        return (
            self.presentations,
            self.payments,
            self.calls,
            self.visits,
            self.ptps,
            self.sms,
            self.mart_snapshots,
        )

    def _initialize_accounts(self, accounts_data: List[Dict], start_date: date):
        """Initialize account states"""
        for acc_data in accounts_data:
            # Calculate initial POS based on how long account has been active
            months_since_disbursal = self._months_between(
                acc_data['disbursal_date'],
                start_date
            )

            # Simplified: assume EMI paid mostly on time
            installments_paid = max(0, months_since_disbursal - self.rng.randint(0, 3))
            pos = acc_data['disbursal_amt'] * (1 - installments_paid / acc_data['tenure_m'])
            pos = max(0, pos)

            state = AccountState(
                account_id=acc_data['account_id'],
                archetype=acc_data['archetype'],
                product_type=acc_data['product_type'],
                disbursal_date=acc_data['disbursal_date'],
                emi_amt=acc_data['emi_amt'],
                cycle_day=acc_data['cycle_day'],
                tenure_m=acc_data['tenure_m'],
                pos=pos,
            )
            self.accounts.append(state)

    def _simulate_month(
        self,
        month_start: date,
        month_end: date,
        customers_data: Dict,
        agents_data: List[Dict],
        month_num: int
    ):
        """Simulate one month of activity"""
        # Process each day in the month
        current_date = month_start
        while current_date <= month_end:
            day_of_month = current_date.day

            # Generate presentations for accounts with cycle_day == today
            for account in self.accounts:
                if account.cycle_day == day_of_month:
                    self._generate_presentation(account, current_date, month_num)

            # Update DPDs daily
            self._update_dpds(current_date)

            # Generate collection activity for overdue accounts
            self._generate_collection_activity(
                current_date,
                customers_data,
                agents_data
            )

            # Generate daily mart snapshots (sample 1 day per week to save space)
            if current_date.weekday() == 0 or current_date == month_end:  # Monday or month-end
                self._generate_mart_snapshots(current_date)

            current_date += timedelta(days=1)

    def _generate_presentation(self, account: AccountState, present_date: date, month_num: int):
        """Generate EMI presentation and bounce/payment"""
        # Calculate which installment this is
        months_since_disbursal = self._months_between(account.disbursal_date, present_date)
        inst_no = months_since_disbursal + 1

        if inst_no > account.tenure_m:
            return  # Loan fully paid

        # Get archetype parameters
        archetype_params = ARCHETYPE_PARAMS[account.archetype]
        base_bounce_prob = archetype_params["base_bounce_prob"]

        # Apply seasonality multipliers
        bounce_prob = self._apply_seasonality(
            base_bounce_prob,
            account.product_type,
            present_date
        )

        # Bounce decision
        bounced = self.rng.random() < bounce_prob

        if bounced:
            # Presentation bounced
            bounce_reason = self.rng.choice(self.BOUNCE_REASONS)
            event = PresentationEvent(
                account_id=account.account_id,
                present_date=present_date,
                amount=account.emi_amt,
                inst_no=inst_no,
                status='B',
                bounce_reason=bounce_reason,
            )
            self.presentations.append(event)
            self.bounces.append(event)

            # Update account state
            account.overdue_amt += account.emi_amt
            account.bounces_in_last_3m += 1
            account.bounce_dates.append(present_date)

            # Decide if self-cure or need contact
            self._process_bounce_cure(account, present_date, archetype_params)

        else:
            # Presentation succeeded
            event = PresentationEvent(
                account_id=account.account_id,
                present_date=present_date,
                amount=account.emi_amt,
                inst_no=inst_no,
                status='S',
            )
            self.presentations.append(event)

            # Auto payment
            payment = PaymentEvent(
                account_id=account.account_id,
                pay_date=present_date,
                amount=account.emi_amt,
                mode="NACH",
                alloc_to_inst=inst_no,
            )
            self.payments.append(payment)

            # Update account state
            account.pos = max(0, account.pos - account.emi_amt * 0.7)  # Simplified: 70% principal, 30% interest
            account.last_payment_date = present_date
            account.payments_in_last_3m += 1
            account.payment_dates.append(present_date)

    def _process_bounce_cure(self, account: AccountState, bounce_date: date, archetype_params: Dict):
        """Process whether bounced account self-cures or needs contact"""
        selfcure_prob = archetype_params["selfcure_prob"]

        # Self-cure within 7 days?
        if self.rng.random() < selfcure_prob:
            # Self-cure in 1-7 days
            cure_days = self.rng.randint(1, 7)
            cure_date = bounce_date + timedelta(days=cure_days)

            payment = PaymentEvent(
                account_id=account.account_id,
                pay_date=cure_date,
                amount=account.emi_amt,
                mode=self.rng.choice(["UPI", "NEFT", "CASH"]),
            )
            self.payments.append(payment)

            # Update state
            account.overdue_amt = max(0, account.overdue_amt - account.emi_amt)
            account.last_payment_date = cure_date
            account.payments_in_last_3m += 1
            account.payment_dates.append(cure_date)

    def _apply_seasonality(self, base_prob: float, product_type: str, date: date) -> float:
        """Apply seasonal multipliers"""
        multiplier = 1.0
        month = date.month

        # Monsoon effect (June-Sept) - higher bounce for TIPPER/CE
        if 6 <= month <= 9 and product_type in ["TIPPER", "CE"]:
            multiplier *= 1.3

        # Harvest effect (Oct-Nov, Mar-Apr) - lower bounce for TRACTOR
        if product_type == "TRACTOR" and (month in [10, 11, 3, 4]):
            multiplier *= 0.8

        return min(1.0, base_prob * multiplier)

    def _generate_collection_activity(
        self,
        current_date: date,
        customers_data: Dict,
        agents_data: List[Dict]
    ):
        """Generate calls, visits, PTPs for overdue accounts"""
        # Sample overdue accounts for collection activity
        overdue_accounts = [acc for acc in self.accounts if acc.current_dpd > 0]

        # Don't call everyone every day - sample based on bucket
        for account in overdue_accounts:
            # Contact probability based on bucket
            contact_prob = self._get_contact_probability(account.current_bucket, current_date)

            if self.rng.random() < contact_prob:
                self._generate_contact_attempt(account, current_date, customers_data, agents_data)

    def _get_contact_probability(self, bucket: str, current_date: date) -> float:
        """Get probability of contact attempt based on bucket"""
        # Don't contact on weekends
        if current_date.weekday() >= 5:
            return 0.0

        bucket_probs = {
            "X": 0.0,
            "PRE_DUE": 0.02,
            "B1": 0.15,
            "B2": 0.25,
            "B3": 0.30,
            "NPA_90": 0.25,
            "NPA_120": 0.20,
            "NPA_150": 0.15,
            "NPA_180+": 0.10,
        }
        return bucket_probs.get(bucket, 0.0)

    def _generate_contact_attempt(
        self,
        account: AccountState,
        contact_date: date,
        customers_data: Dict,
        agents_data: List[Dict]
    ):
        """Generate a contact attempt (call or visit)"""
        customer = customers_data.get(account.account_id)
        if not customer:
            return

        archetype_params = ARCHETYPE_PARAMS[account.archetype]
        contact_responsiveness = archetype_params["contact_responsiveness"]

        # Decide channel: mostly calls, some visits for higher buckets
        is_visit = account.current_bucket in ["B2", "B3", "NPA_90"] and self.rng.random() < 0.15

        if is_visit:
            # Generate field visit
            agent = self.rng.choice([a for a in agents_data if a['role'] == 'FOS'])

            # Did contact happen?
            contacted = self.rng.random() < contact_responsiveness

            if contacted:
                disposition = self.rng.choice(["VISIT_MET", "COLLECTED", "PTP"])

                # Collection?
                if disposition == "COLLECTED":
                    amount = account.emi_amt
                    payment = PaymentEvent(
                        account_id=account.account_id,
                        pay_date=contact_date,
                        amount=amount,
                        mode="CASH",
                        collected_by=agent['agent_id'],
                    )
                    self.payments.append(payment)
                    account.overdue_amt = max(0, account.overdue_amt - amount)
                    account.last_payment_date = contact_date

                    visit_amt = amount
                else:
                    visit_amt = 0

                visit = VisitEvent(
                    account_id=account.account_id,
                    customer_id=customer['customer_id'],
                    agent_id=agent['agent_id'],
                    visit_date=contact_date,
                    disposition=disposition,
                    amount_collected=visit_amt,
                    payment_mode="CASH" if visit_amt > 0 else None,
                )
                self.visits.append(visit)

                account.last_contact_date = contact_date
                account.last_contact_channel = "FIELD"

            else:
                # Visit but not found
                agent = self.rng.choice([a for a in agents_data if a['role'] == 'FOS'])
                visit = VisitEvent(
                    account_id=account.account_id,
                    customer_id=customer['customer_id'],
                    agent_id=agent['agent_id'],
                    visit_date=contact_date,
                    disposition="VISIT_NOT_FOUND",
                )
                self.visits.append(visit)

        else:
            # Generate call (bot or telecaller)
            is_bot = self.rng.random() < 0.60  # 60% bot, 40% telecaller
            channel = "BOT" if is_bot else "TELECALLER"
            agent_id = None if is_bot else self.rng.choice([a for a in agents_data if a['role'] == 'TC'])['agent_id']

            # Did call connect?
            connected = self.rng.random() < contact_responsiveness

            if connected:
                outcome = "CONNECTED"
                disposition = self.rng.choice(self.CALL_DISPOSITIONS)
                duration_sec = self.rng.randint(60, 300)
            else:
                outcome = self.rng.choice(["NO_ANSWER", "BUSY", "FAILED"])
                disposition = None
                duration_sec = 0

            call = CallEvent(
                account_id=account.account_id,
                customer_id=customer['customer_id'],
                phone=customer['primary_phone'],
                channel=channel,
                agent_id=agent_id,
                call_start_time=contact_date,
                outcome=outcome,
                disposition=disposition,
                duration_sec=duration_sec,
            )
            self.calls.append(call)

            if connected:
                account.last_contact_date = contact_date
                account.last_contact_channel = channel

    def _update_dpds(self, current_date: date):
        """Update DPD for all accounts"""
        for account in self.accounts:
            if account.overdue_amt > 0:
                # Simple DPD: days since last expected payment
                # For now, increment by 1 each day if overdue
                account.current_dpd += 1
            else:
                account.current_dpd = 0

            # Update bucket
            account.current_bucket = self._dpd_to_bucket(account.current_dpd)

    def _dpd_to_bucket(self, dpd: int) -> str:
        """Convert DPD to bucket"""
        if dpd < 0:
            return "PRE_DUE"
        elif dpd == 0:
            return "X"
        elif dpd <= 30:
            return "B1"
        elif dpd <= 60:
            return "B2"
        elif dpd <= 90:
            return "B3"
        elif dpd <= 120:
            return "NPA_90"
        elif dpd <= 150:
            return "NPA_120"
        elif dpd <= 180:
            return "NPA_150"
        else:
            return "NPA_180+"

    def _generate_mart_snapshots(self, snapshot_date: date):
        """Generate mart_account_daily snapshots for all accounts"""
        for account in self.accounts:
            snapshot = MartSnapshot(
                account_id=account.account_id,
                date=snapshot_date,
                dpd=account.current_dpd,
                bucket=account.current_bucket,
                overdue_amt=account.overdue_amt,
                pos=account.pos,
                total_dues=account.overdue_amt,
                emi_amt=account.emi_amt,
                cycle_day=account.cycle_day,
                last_contact_date=account.last_contact_date,
                last_contact_channel=account.last_contact_channel,
                last_payment_date=account.last_payment_date,
                has_open_ptp=account.open_ptp is not None,
            )
            self.mart_snapshots.append(snapshot)

    def _add_months(self, start_date: date, months: int) -> date:
        """Add months to a date"""
        import calendar
        month = start_date.month - 1 + months
        year = start_date.year + month // 12
        month = month % 12 + 1
        _, last_day = calendar.monthrange(year, month)
        day = min(start_date.day, last_day)
        return date(year, month, day)

    def _months_between(self, start_date: date, end_date: date) -> int:
        """Calculate months between two dates"""
        return (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
