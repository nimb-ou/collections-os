"""
Treatment Strategy Engine
Assigns treatment codes based on rules, scores, and account state.
"""

import yaml
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta
import psycopg2
from psycopg2.extras import execute_batch

# Load treatment rules
RULES_PATH = Path(__file__).parent / "treatment_rules.yaml"


class TreatmentEngine:
    """
    Rule-based treatment assignment engine.
    Deterministic and auditable.
    """

    def __init__(self, rules_path: Optional[Path] = None):
        """
        Initialize treatment engine with rules.

        Args:
            rules_path: Path to treatment rules YAML file
        """
        self.rules_path = rules_path or RULES_PATH

        with open(self.rules_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.version = self.config['version']
        self.treatments = self.config['treatments']
        self.rules = self.config['rules']
        self.guardrails = self.config['guardrails']
        self.risk_bands = self.config['risk_bands']
        self.value_bands = self.config['value_bands']

        print(f"Loaded treatment rules v{self.version} with {len(self.rules)} rules")

    def classify_risk_band(self, bounce_p: float) -> str:
        """Classify account into risk band based on bounce probability."""
        if bounce_p < self.risk_bands['low']['bounce_p_max']:
            return 'low'
        elif bounce_p < self.risk_bands['medium']['bounce_p_max']:
            return 'medium'
        elif bounce_p < self.risk_bands['high']['bounce_p_max']:
            return 'high'
        else:
            return 'very_high'

    def classify_value_band(self, overdue_amt: float) -> str:
        """Classify account into value band based on overdue amount."""
        if overdue_amt < self.value_bands['low']['overdue_max']:
            return 'low'
        elif overdue_amt < self.value_bands['medium']['overdue_max']:
            return 'medium'
        elif overdue_amt < self.value_bands['high']['overdue_max']:
            return 'high'
        else:
            return 'very_high'

    def evaluate_condition(self, condition_key: str, condition_value: Any, account_data: Dict) -> bool:
        """
        Evaluate a single condition against account data.

        Args:
            condition_key: Condition field name
            condition_value: Expected value or constraint
            account_data: Account attributes

        Returns:
            True if condition is met
        """
        account_value = account_data.get(condition_key)

        # Handle missing data
        if account_value is None:
            return False

        # Direct equality check
        if isinstance(condition_value, (str, bool, int, float)):
            return account_value == condition_value

        # List membership check
        if isinstance(condition_value, list):
            return account_value in condition_value

        # Range check (dict with min/max)
        if isinstance(condition_value, dict):
            if 'min' in condition_value and account_value < condition_value['min']:
                return False
            if 'max' in condition_value and account_value > condition_value['max']:
                return False
            return True

        return False

    def match_rule(self, rule: Dict, account_data: Dict) -> bool:
        """
        Check if an account matches all conditions in a rule.

        Args:
            rule: Rule definition
            account_data: Account attributes

        Returns:
            True if all conditions are met
        """
        conditions = rule.get('conditions', {})

        # Empty conditions = default rule (always matches)
        if not conditions:
            return True

        # All conditions must be met
        for condition_key, condition_value in conditions.items():
            if not self.evaluate_condition(condition_key, condition_value, account_data):
                return False

        return True

    def assign_treatment(self, account_data: Dict) -> Dict:
        """
        Assign treatment code to an account.

        Args:
            account_data: Dictionary with account attributes:
                - account_id
                - bucket (X, B1, B2, B3, NPA1, etc.)
                - bounce_p (model score)
                - selfcure_p (model score)
                - overdue_amt
                - days_to_due (negative if past due)
                - days_since_bounce
                - has_active_ptp
                - has_broken_ptp
                - last_contact_date
                - dnc_flag

        Returns:
            Dictionary with treatment assignment:
                - treatment_code
                - treatment_name
                - channels
                - priority
                - assigned_reason (rule name)
        """
        # Enrich account data with derived fields
        enriched_data = account_data.copy()
        enriched_data['risk_band'] = self.classify_risk_band(account_data.get('bounce_p', 0))
        enriched_data['value_band'] = self.classify_value_band(account_data.get('overdue_amt', 0))

        # Evaluate rules in order until first match
        for rule in self.rules:
            if self.match_rule(rule, enriched_data):
                treatment_code = rule['treatment']
                treatment_def = self.treatments[treatment_code]

                return {
                    'account_id': account_data.get('account_id', 'unknown'),
                    'treatment_code': treatment_code,
                    'treatment_name': treatment_def['name'],
                    'channels': treatment_def['channels'],
                    'priority': treatment_def['priority'],
                    'assigned_reason': rule['name'],
                    'assigned_at': datetime.now(),
                }

        # Should never reach here if default rule is defined
        raise ValueError(f"No treatment matched for account {account_data.get('account_id', 'unknown')}")

    def check_guardrails(self, account_id: str, contact_history: List[Dict]) -> Dict:
        """
        Check if account can be contacted based on guardrails.

        Args:
            account_id: Account identifier
            contact_history: List of recent contacts with dates/types

        Returns:
            Dict with can_contact (bool) and reasons (list)
        """
        reasons = []
        now = datetime.now()

        # Count contacts today
        today_contacts = [c for c in contact_history
                          if c['contact_date'].date() == now.date()]
        calls_today = sum(1 for c in today_contacts if c['contact_type'] in ['BOT', 'TELECALLER'])
        visits_today = sum(1 for c in today_contacts if c['contact_type'] == 'FIELD')

        # Check daily limits
        if calls_today >= self.guardrails['contact_limits']['max_calls_per_day']:
            reasons.append(f"Max calls per day reached ({calls_today})")

        if visits_today >= self.guardrails['contact_limits']['max_visits_per_day']:
            reasons.append(f"Max visits per day reached ({visits_today})")

        # Check timing window
        current_hour = now.hour
        start_hour = int(self.guardrails['timing']['call_window_start'].split(':')[0])
        end_hour = int(self.guardrails['timing']['call_window_end'].split(':')[0])

        if current_hour < start_hour or current_hour >= end_hour:
            reasons.append(f"Outside contact window ({start_hour}:00-{end_hour}:00)")

        # Check Sunday restriction
        if self.guardrails['timing']['no_sundays'] and now.weekday() == 6:
            reasons.append("No contact on Sundays")

        # Check cool-off periods
        last_rpc = next((c for c in contact_history
                        if c.get('outcome') == 'CONNECT_RPC'), None)
        if last_rpc:
            hours_since_rpc = (now - last_rpc['contact_date']).total_seconds() / 3600
            if hours_since_rpc < self.guardrails['cool_off']['after_rpc_hours']:
                reasons.append(f"Cool-off after RPC ({hours_since_rpc:.1f}h < 48h)")

        return {
            'account_id': account_id,
            'can_contact': len(reasons) == 0,
            'reasons': reasons,
            'checked_at': now,
        }


def assign_treatments_batch(
    accounts_df: pd.DataFrame,
    rules_path: Optional[Path] = None
) -> pd.DataFrame:
    """
    Assign treatments to a batch of accounts.

    Args:
        accounts_df: DataFrame with account data
        rules_path: Optional path to rules YAML

    Returns:
        DataFrame with treatment assignments
    """
    engine = TreatmentEngine(rules_path)

    assignments = []
    for _, row in accounts_df.iterrows():
        account_data = row.to_dict()
        assignment = engine.assign_treatment(account_data)
        assignments.append(assignment)

    return pd.DataFrame(assignments)


if __name__ == '__main__':
    # Test with sample data
    test_accounts = [
        {
            'account_id': 'ACC001',
            'bucket': 'X',
            'bounce_p': 0.05,
            'selfcure_p': 0.8,
            'overdue_amt': 0,
            'days_to_due': 3,
            'days_since_bounce': None,
            'has_active_ptp': False,
            'has_broken_ptp': False,
            'dnc_flag': False,
        },
        {
            'account_id': 'ACC002',
            'bucket': 'B1',
            'bounce_p': 0.25,
            'selfcure_p': 0.75,
            'overdue_amt': 5000,
            'days_to_due': -2,
            'days_since_bounce': 1,
            'has_active_ptp': False,
            'has_broken_ptp': False,
            'dnc_flag': False,
        },
        {
            'account_id': 'ACC003',
            'bucket': 'B2',
            'bounce_p': 0.45,
            'selfcure_p': 0.2,
            'overdue_amt': 35000,
            'days_to_due': -35,
            'days_since_bounce': 30,
            'has_active_ptp': False,
            'has_broken_ptp': True,
            'dnc_flag': False,
        },
    ]

    engine = TreatmentEngine()

    print("\nTesting treatment assignments:\n")
    for account in test_accounts:
        assignment = engine.assign_treatment(account)
        print(f"Account {account['account_id']}:")
        print(f"  Bucket: {account['bucket']}, Risk: {account['bounce_p']:.2f}")
        print(f"  → Treatment: {assignment['treatment_code']} - {assignment['treatment_name']}")
        print(f"  → Channels: {', '.join(assignment['channels'])}")
        print(f"  → Reason: {assignment['assigned_reason']}")
        print()
