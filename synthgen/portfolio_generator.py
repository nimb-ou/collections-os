"""
Portfolio Generator
Creates loan accounts with realistic CV/CE product characteristics
"""
import random
import calendar
from datetime import date, timedelta
from typing import List, Dict, Tuple
from dataclasses import dataclass
import math

from .config import PRODUCT_SPECS
from .customer_generator import CustomerData
from .geo_generator import GeoData


@dataclass
class AccountData:
    """Account (loan) data"""

    account_id: str
    customer_id: str
    product_type: str
    asset_desc: str
    disbursal_date: date
    disbursal_amt: float
    tenure_m: int
    roi: float
    emi_amt: float
    cycle_day: int
    branch: str
    state: str
    city: str
    pincode: str
    geo_id: int
    archetype: str  # Hidden truth for behavior simulation


@dataclass
class EMIScheduleData:
    """EMI schedule entry"""

    account_id: str
    inst_no: int
    due_date: date
    emi_amt: float
    principal: float
    interest: float


class PortfolioGenerator:
    """Generates loan portfolio with realistic characteristics"""

    CYCLE_DAYS = [1, 5, 10, 15]

    def __init__(
        self,
        product_mix: Dict[str, int],
        archetype_dist: Dict[str, int],
        seed: int = 42,
    ):
        self.rng = random.Random(seed)
        self.product_mix = product_mix
        self.archetype_dist = archetype_dist

        # Build weighted product list
        self.product_list = []
        for product, weight in product_mix.items():
            self.product_list.extend([product] * weight)

        # Build weighted archetype list
        self.archetype_list = []
        for archetype, weight in archetype_dist.items():
            self.archetype_list.extend([archetype] * weight)

    def generate_portfolio(
        self,
        n_accounts: int,
        customers: List[CustomerData],
        geos: List[GeoData],
        geo_start_id: int = 1,
    ) -> Tuple[List[AccountData], List[EMIScheduleData]]:
        """
        Generate n_accounts with assignment to customers
        Returns (accounts, emi_schedules)
        """
        accounts = []
        emi_schedules = []

        # Some customers can have multiple accounts (10%)
        customer_pool = customers.copy()
        multi_account_customers = self.rng.sample(
            customer_pool, k=int(len(customer_pool) * 0.05)
        )

        for i in range(n_accounts):
            account_id = f"ACC{i+1:08d}"

            # Assign customer (with possibility of repeat)
            if i < len(customer_pool):
                customer = customer_pool[i]
            else:
                # Reuse from multi-account pool
                customer = self.rng.choice(multi_account_customers)

            # Pick product type
            product_type = self.rng.choice(self.product_list)
            product_spec = PRODUCT_SPECS[product_type]

            # Generate loan parameters
            disbursal_amt = self.rng.uniform(*product_spec["ticket_range"])
            disbursal_amt = round(disbursal_amt / 1000) * 1000  # Round to nearest 1000

            tenure_m = self.rng.randint(*product_spec["tenure_range"])
            roi = round(self.rng.uniform(*product_spec["roi_range"]), 2)

            # Calculate EMI (simple EMI formula)
            monthly_rate = roi / 12 / 100
            if monthly_rate > 0:
                emi_amt = (
                    disbursal_amt
                    * monthly_rate
                    * (1 + monthly_rate) ** tenure_m
                    / ((1 + monthly_rate) ** tenure_m - 1)
                )
            else:
                emi_amt = disbursal_amt / tenure_m
            emi_amt = round(emi_amt, 2)

            # Disbursal date: spread over last 5 years
            days_ago = self.rng.randint(30, 5 * 365)  # Min 1 month old
            disbursal_date = date.today() - timedelta(days=days_ago)

            # Cycle day
            cycle_day = self.rng.choice(self.CYCLE_DAYS)

            # Asset description
            asset_desc = self.rng.choice(product_spec["asset_examples"])

            # Branch (simplified - city-based)
            branch = f"{customer.city} Branch"

            # Assign archetype (hidden behavioral truth)
            archetype = self.rng.choice(self.archetype_list)

            # Get geo_id
            geo_id = customer.geo_id

            account = AccountData(
                account_id=account_id,
                customer_id=customer.customer_id,
                product_type=product_type,
                asset_desc=asset_desc,
                disbursal_date=disbursal_date,
                disbursal_amt=disbursal_amt,
                tenure_m=tenure_m,
                roi=roi,
                emi_amt=emi_amt,
                cycle_day=cycle_day,
                branch=branch,
                state=customer.state,
                city=customer.city,
                pincode=customer.pincode,
                geo_id=geo_id,
                archetype=archetype,
            )

            accounts.append(account)

            # Generate EMI schedule for this account
            schedule = self._generate_emi_schedule(account)
            emi_schedules.extend(schedule)

        return accounts, emi_schedules

    def _generate_emi_schedule(self, account: AccountData) -> List[EMIScheduleData]:
        """Generate EMI schedule for an account"""
        schedule = []

        # Calculate principal and interest per installment
        monthly_rate = account.roi / 12 / 100
        remaining_principal = account.disbursal_amt

        for inst_no in range(1, account.tenure_m + 1):
            # Due date calculation
            months_from_disbursal = inst_no
            due_date = self._add_months(account.disbursal_date, months_from_disbursal)
            due_date = self._adjust_to_cycle_day(due_date, account.cycle_day)

            # Interest component
            interest = round(remaining_principal * monthly_rate, 2)

            # Principal component
            principal = round(account.emi_amt - interest, 2)

            # Ensure last installment closes the loan
            if inst_no == account.tenure_m:
                principal = remaining_principal
                emi_amt = principal + interest
            else:
                emi_amt = account.emi_amt

            schedule.append(
                EMIScheduleData(
                    account_id=account.account_id,
                    inst_no=inst_no,
                    due_date=due_date,
                    emi_amt=emi_amt,
                    principal=principal,
                    interest=interest,
                )
            )

            remaining_principal -= principal

        return schedule

    def _add_months(self, start_date: date, months: int) -> date:
        """Add months to a date, handling variable month lengths"""
        month = start_date.month - 1 + months
        year = start_date.year + month // 12
        month = month % 12 + 1
        # Get the last day of the target month
        _, last_day = calendar.monthrange(year, month)
        day = min(start_date.day, last_day)
        return date(year, month, day)

    def _adjust_to_cycle_day(self, base_date: date, cycle_day: int) -> date:
        """Adjust date to the specified cycle day"""
        if base_date.day <= cycle_day:
            # Same month - ensure cycle_day is valid for this month
            _, last_day = calendar.monthrange(base_date.year, base_date.month)
            actual_day = min(cycle_day, last_day)
            return date(base_date.year, base_date.month, actual_day)
        else:
            # Next month - ensure cycle_day is valid for next month
            next_month = self._add_months(base_date, 1)
            _, last_day = calendar.monthrange(next_month.year, next_month.month)
            actual_day = min(cycle_day, last_day)
            return date(next_month.year, next_month.month, actual_day)
