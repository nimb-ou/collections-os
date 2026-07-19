"""
Allocation Engine
Assigns accounts to agents based on capacity, geography, skill, and optimization.
"""

import yaml
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, date, timedelta
from dataclasses import dataclass
import psycopg2
from psycopg2.extras import execute_batch
import math

try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False
    print("⚠️  OR-Tools not available. Only greedy algorithm will work.")

# Load capacity configuration
CONFIG_PATH = Path(__file__).parent / "capacity.yaml"


@dataclass
class Agent:
    """Agent attributes for allocation."""
    agent_id: str
    name: str
    role: str
    team_id: int
    base_pincode: str
    base_lat: float
    base_lon: float
    langs: List[str]
    capacity: int
    skill_score: float = 0.0
    current_load: int = 0
    active: bool = True


@dataclass
class Account:
    """Account attributes for allocation."""
    account_id: str
    customer_id: str
    bucket: str
    treatment_code: str
    pincode: str
    lat: float
    lon: float
    lang_pref: str
    overdue_amt: float
    bounce_p: float
    difficulty_score: float = 0.0
    current_owner: Optional[str] = None
    requires_field: bool = False


class CapacityManager:
    """
    Manages agent capacity calculations and constraints.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize capacity manager with config."""
        self.config_path = config_path or CONFIG_PATH

        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.capacity_config = self.config['capacity']
        self.eligibility = self.config['role_bucket_eligibility']
        self.hard_constraints = self.config['hard_constraints']

    def get_agent_capacity(self, agent: Agent, date: date = None) -> int:
        """
        Get daily capacity for an agent.

        Args:
            agent: Agent object
            date: Date for capacity calculation (for future: holidays, etc.)

        Returns:
            Daily capacity (number of accounts/dials)
        """
        role_config = self.capacity_config.get(agent.role, {})

        # Check for agent-specific override
        if hasattr(agent, 'capacity_override') and agent.capacity:
            return agent.capacity

        # Default capacity by role
        if agent.role == 'FOS':
            return role_config.get('default_accounts_per_day', 55)
        elif agent.role == 'TC':
            return role_config.get('default_dials_per_day', 225)
        else:
            return 0  # TL/ACM/RCM don't get direct allocations

    def is_eligible(self, agent: Agent, account: Account) -> bool:
        """
        Check if agent is eligible for account based on hard constraints.

        Returns:
            True if all hard constraints satisfied
        """
        # Role-bucket eligibility
        if self.hard_constraints['role_bucket_match']['enabled']:
            eligible_buckets = self.eligibility.get(agent.role, {}).get('eligible_buckets', [])
            if account.bucket not in eligible_buckets:
                return False

        # Language match (with fallback)
        if self.hard_constraints['language_match']['enabled']:
            allow_fallback = self.hard_constraints['language_match'].get('allow_fallback', True)
            if account.lang_pref not in agent.langs:
                # Check if agent has fallback languages
                if not allow_fallback:
                    return False
                if 'hindi' not in agent.langs and 'english' not in agent.langs:
                    return False

        # Active agents only
        if self.hard_constraints['active_agents_only']['enabled']:
            if not agent.active:
                return False

        # Geography match (for FOS)
        if agent.role == 'FOS' and self.hard_constraints['geography_match']['enabled']:
            distance = self.haversine_distance(
                agent.base_lat, agent.base_lon,
                account.lat, account.lon
            )
            max_radius = self.config['geography'].get('max_beat_radius_km', 25)
            if distance > max_radius:
                return False

        return True

    def is_within_capacity(self, agent: Agent, additional_accounts: int = 1) -> bool:
        """Check if agent can handle additional accounts."""
        capacity = self.get_agent_capacity(agent)
        return (agent.current_load + additional_accounts) <= capacity

    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate haversine distance between two lat/lon points in kilometers.
        """
        R = 6371  # Earth radius in km

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c


class AllocationEngine:
    """
    Core allocation engine - assigns accounts to agents.
    Supports greedy and OR-Tools CP-SAT algorithms.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize allocation engine."""
        self.config_path = config_path or CONFIG_PATH

        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.capacity_mgr = CapacityManager(config_path)
        self.soft_weights = self.config['soft_constraints']['weights']
        self.templates = self.config['transparency']['allocation_reason_templates']

    def allocate_greedy(
        self,
        accounts: List[Account],
        agents: List[Agent],
        previous_allocations: Dict[str, str] = None
    ) -> List[Dict]:
        """
        Greedy allocation algorithm with soft constraint scoring.

        Args:
            accounts: List of accounts to allocate
            agents: List of available agents
            previous_allocations: Dict mapping account_id -> agent_id from last month

        Returns:
            List of allocation records
        """
        allocations = []
        previous_allocations = previous_allocations or {}

        # Sort accounts by priority (high value, broken PTP, high risk first)
        accounts_sorted = sorted(
            accounts,
            key=lambda a: (-a.overdue_amt, -a.bounce_p, a.account_id)
        )

        for account in accounts_sorted:
            # Find best agent for this account
            best_agent = None
            best_score = -float('inf')
            best_reason = ""

            for agent in agents:
                # Check hard constraints
                if not self.capacity_mgr.is_eligible(agent, account):
                    continue

                if not self.capacity_mgr.is_within_capacity(agent):
                    continue

                # Calculate soft constraint score
                score, reason = self.calculate_allocation_score(
                    agent, account, previous_allocations
                )

                if score > best_score:
                    best_score = score
                    best_agent = agent
                    best_reason = reason

            # Allocate to best agent
            if best_agent:
                allocation = {
                    'account_id': account.account_id,
                    'owner_agent_id': best_agent.agent_id,
                    'allocation_reason': best_reason,
                    'difficulty_score': account.difficulty_score,
                    'allocated_by': 'SYSTEM_GREEDY',
                }
                allocations.append(allocation)
                best_agent.current_load += 1
            else:
                # No eligible agent found - log warning
                print(f"⚠️  No eligible agent for account {account.account_id}")

        return allocations

    def calculate_allocation_score(
        self,
        agent: Agent,
        account: Account,
        previous_allocations: Dict[str, str]
    ) -> Tuple[float, str]:
        """
        Calculate weighted soft constraint score for agent-account pair.

        Returns:
            (score, reason_string)
        """
        score = 0.0
        reasons = []

        # 1. Skill score (0.25 weight)
        skill_component = agent.skill_score * self.soft_weights['skill_score']
        score += skill_component
        if agent.skill_score > 0.7:
            reasons.append(f"high skill ({agent.skill_score:.2f})")

        # 2. Continuity (0.20 weight)
        prev_owner = previous_allocations.get(account.account_id)
        if prev_owner == agent.agent_id:
            continuity_component = 1.0 * self.soft_weights['continuity']
            score += continuity_component
            reasons.append("continuity")

        # 3. Geography proximity (0.15 weight) - for FOS only
        if agent.role == 'FOS':
            distance = self.capacity_mgr.haversine_distance(
                agent.base_lat, agent.base_lon,
                account.lat, account.lon
            )
            max_dist = self.config['geography']['max_beat_radius_km']
            # Normalize: 0 km = 1.0, max_dist km = 0.0
            proximity_score = max(0, 1 - (distance / max_dist))
            proximity_component = proximity_score * self.soft_weights['geography_proximity']
            score += proximity_component
            if distance < 5:
                reasons.append(f"nearby ({distance:.1f} km)")

        # 4. Workload balance (0.15 weight)
        capacity = self.capacity_mgr.get_agent_capacity(agent)
        utilization = agent.current_load / capacity if capacity > 0 else 1.0
        # Prefer agents with lower current load
        balance_score = max(0, 1 - utilization)
        balance_component = balance_score * self.soft_weights['workload_balance']
        score += balance_component

        # 5. Language exact match (0.05 weight)
        if account.lang_pref in agent.langs:
            lang_component = 1.0 * self.soft_weights['language_exact_match']
            score += lang_component
            if account.lang_pref not in ['hindi', 'english']:
                reasons.append(f"lang:{account.lang_pref}")

        # Build reason string
        if not reasons:
            reasons.append("capacity available")
        reason_text = f"Greedy allocation: {', '.join(reasons)}"

        return score, reason_text

    def allocate_ortools(
        self,
        accounts: List[Account],
        agents: List[Agent],
        previous_allocations: Dict[str, str] = None
    ) -> List[Dict]:
        """
        OR-Tools CP-SAT optimization for allocation.
        Finds globally optimal assignment under constraints.

        Returns:
            List of allocation records
        """
        if not ORTOOLS_AVAILABLE:
            raise ImportError("OR-Tools not installed. Use greedy algorithm instead.")

        model = cp_model.CpModel()
        previous_allocations = previous_allocations or {}

        # Decision variables: x[i,j] = 1 if account i assigned to agent j
        x = {}
        for i, account in enumerate(accounts):
            for j, agent in enumerate(agents):
                if self.capacity_mgr.is_eligible(agent, account):
                    x[i, j] = model.NewBoolVar(f'assign_{i}_{j}')

        # Constraint 1: Each account assigned to exactly one eligible agent
        for i in range(len(accounts)):
            eligible_vars = [x[i, j] for j in range(len(agents)) if (i, j) in x]
            if eligible_vars:
                model.Add(sum(eligible_vars) == 1)

        # Constraint 2: Agent capacity limits
        for j, agent in enumerate(agents):
            capacity = self.capacity_mgr.get_agent_capacity(agent)
            assigned_to_j = [x[i, j] for i in range(len(accounts)) if (i, j) in x]
            if assigned_to_j:
                model.Add(sum(assigned_to_j) <= capacity)

        # Objective: Maximize weighted soft constraints
        objective_terms = []

        for i, account in enumerate(accounts):
            for j, agent in enumerate(agents):
                if (i, j) not in x:
                    continue

                # Calculate score (scaled to integer for CP-SAT)
                score, _ = self.calculate_allocation_score(agent, account, previous_allocations)
                # Scale to 0-1000 range
                int_score = int(score * 1000)
                objective_terms.append(x[i, j] * int_score)

        model.Maximize(sum(objective_terms))

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.config['ortools_config']['max_time_seconds']
        solver.parameters.num_search_workers = self.config['ortools_config']['num_search_workers']

        status = solver.Solve(model)

        allocations = []
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            for i, account in enumerate(accounts):
                for j, agent in enumerate(agents):
                    if (i, j) in x and solver.Value(x[i, j]) == 1:
                        _, reason = self.calculate_allocation_score(
                            agent, account, previous_allocations
                        )
                        allocation = {
                            'account_id': account.account_id,
                            'owner_agent_id': agent.agent_id,
                            'allocation_reason': f"OR-Tools optimal: {reason}",
                            'difficulty_score': account.difficulty_score,
                            'allocated_by': 'SYSTEM_ORTOOLS',
                        }
                        allocations.append(allocation)
                        agent.current_load += 1
                        break

            print(f"✓ OR-Tools allocation: {len(allocations)} accounts assigned (status: {solver.StatusName(status)})")
        else:
            print(f"⚠️  OR-Tools failed: {solver.StatusName(status)}. Falling back to greedy.")
            return self.allocate_greedy(accounts, agents, previous_allocations)

        return allocations


class BeatPlanner:
    """
    Generates optimized daily beat plans for field agents.
    Orders accounts to minimize travel and maximize collection probability.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize beat planner."""
        self.config_path = config_path or CONFIG_PATH

        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.beat_config = self.config['beat_planning']
        self.capacity_mgr = CapacityManager(config_path)

    def create_beat_plan(
        self,
        agent: Agent,
        accounts: List[Account],
        beat_date: date
    ) -> List[Dict]:
        """
        Create ordered beat plan for a field agent for one day.

        Args:
            agent: FOS agent
            accounts: Accounts allocated to this agent
            beat_date: Date of the beat

        Returns:
            List of beat plan records with sequence_no
        """
        if agent.role != 'FOS':
            return []

        # Filter accounts that need field visits
        field_accounts = [acc for acc in accounts if acc.requires_field]

        if not field_accounts:
            return []

        # Sort by optimization objective
        if self.beat_config['optimization_objective'] == 'minimize_travel':
            ordered_accounts = self.tsp_nearest_neighbor(agent, field_accounts)
        else:
            # maximize_collection: prioritize by expected collection
            ordered_accounts = sorted(
                field_accounts,
                key=lambda a: -a.overdue_amt
            )

        # Generate beat plan records
        beat_plan = []
        for seq, account in enumerate(ordered_accounts, start=1):
            priority = self.determine_priority(account)
            beat_record = {
                'agent_id': agent.agent_id,
                'beat_date': beat_date,
                'account_id': account.account_id,
                'sequence_no': seq,
                'priority': priority,
                'expected_collection': account.overdue_amt,
                'visit_reason': self.get_visit_reason(account),
                'notes': None,
            }
            beat_plan.append(beat_record)

        return beat_plan

    def tsp_nearest_neighbor(self, agent: Agent, accounts: List[Account]) -> List[Account]:
        """
        Nearest-neighbor heuristic for TSP (traveling salesman problem).
        Start from agent base, always visit nearest unvisited account.

        Returns:
            Ordered list of accounts
        """
        if not accounts:
            return []

        ordered = []
        unvisited = accounts.copy()
        current_lat, current_lon = agent.base_lat, agent.base_lon

        while unvisited:
            # Find nearest account
            nearest = min(
                unvisited,
                key=lambda a: self.capacity_mgr.haversine_distance(
                    current_lat, current_lon, a.lat, a.lon
                )
            )

            ordered.append(nearest)
            unvisited.remove(nearest)
            current_lat, current_lon = nearest.lat, nearest.lon

        return ordered

    def determine_priority(self, account: Account) -> str:
        """Determine visit priority based on account attributes."""
        if account.overdue_amt > 50000:
            return 'HIGH'
        elif account.overdue_amt > 25000 or account.bounce_p > 0.6:
            return 'MEDIUM'
        else:
            return 'LOW'

    def get_visit_reason(self, account: Account) -> str:
        """Generate human-readable visit reason."""
        if 'BROKEN_PTP' in account.treatment_code:
            return "Broken PTP follow-up"
        elif account.bucket in ['B2', 'B3']:
            return f"Bucket {account.bucket} field collection"
        elif account.overdue_amt > 50000:
            return "High-value account visit"
        else:
            return "Routine field visit"


class RebalanceEngine:
    """
    Handles daily allocation adjustments without disrupting monthly base.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize rebalance engine."""
        self.config_path = config_path or CONFIG_PATH

        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.allocation_engine = AllocationEngine(config_path)
        self.capacity_mgr = CapacityManager(config_path)

    def rebalance_for_absence(
        self,
        absent_agent_id: str,
        agents: List[Agent],
        accounts: List[Account]
    ) -> List[Dict]:
        """
        Redistribute accounts when an agent is absent.

        Args:
            absent_agent_id: ID of absent agent
            agents: Available replacement agents (same team preferred)
            accounts: Accounts currently allocated to absent agent

        Returns:
            List of new allocation records
        """
        print(f"Rebalancing {len(accounts)} accounts from absent agent {absent_agent_id}")

        # Use greedy algorithm to reassign
        reallocations = self.allocation_engine.allocate_greedy(
            accounts, agents, previous_allocations={}
        )

        # Add rebalance-specific reason
        for alloc in reallocations:
            alloc['allocation_reason'] = f"Rebalanced: agent {absent_agent_id} absent"
            alloc['allocated_by'] = 'SYSTEM_REBALANCE'

        return reallocations

    def allocate_new_bounces(
        self,
        new_bounce_accounts: List[Account],
        agents: List[Agent]
    ) -> List[Dict]:
        """
        Allocate newly bounced accounts based on their treatment codes.

        Args:
            new_bounce_accounts: Accounts that bounced today
            agents: Available agents

        Returns:
            List of allocation records
        """
        print(f"Allocating {len(new_bounce_accounts)} new bounces")

        allocations = self.allocation_engine.allocate_greedy(
            new_bounce_accounts, agents, previous_allocations={}
        )

        for alloc in allocations:
            alloc['allocation_reason'] = f"New bounce: {alloc['allocation_reason']}"
            alloc['allocated_by'] = 'SYSTEM_DAILY'

        return allocations


def run_monthly_allocation(
    db_config: Dict,
    period_month: date,
    algorithm: str = 'greedy'
) -> int:
    """
    Run monthly base allocation for all accounts.

    Args:
        db_config: PostgreSQL connection config
        period_month: First day of the month to allocate for
        algorithm: 'greedy' or 'ortools'

    Returns:
        Number of accounts allocated
    """
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()

    print(f"\n{'='*60}")
    print(f"Monthly Allocation - {period_month.strftime('%B %Y')}")
    print(f"Algorithm: {algorithm.upper()}")
    print(f"{'='*60}\n")

    # Load agents
    cur.execute("""
        SELECT
            a.agent_id, a.name, a.role, a.team_id,
            a.base_pincode, g.lat, g.lon,
            a.langs, a.capacity_override, a.active
        FROM dim_agent a
        LEFT JOIN dim_geo g ON a.base_geo_id = g.geo_id
        WHERE a.active = true
          AND a.valid_to = '9999-12-31'::timestamp
          AND a.role IN ('FOS', 'TC')
        ORDER BY a.agent_id
    """)

    agent_rows = cur.fetchall()
    agents = []
    for row in agent_rows:
        agent = Agent(
            agent_id=row[0],
            name=row[1],
            role=row[2],
            team_id=row[3],
            base_pincode=row[4],
            base_lat=row[5] or 28.6139,  # Default Delhi
            base_lon=row[6] or 77.2090,
            langs=row[7] or ['hindi', 'english'],
            capacity=row[8] or 0,
            active=row[9]
        )
        agents.append(agent)

    print(f"Loaded {len(agents)} active agents ({sum(1 for a in agents if a.role == 'FOS')} FOS, {sum(1 for a in agents if a.role == 'TC')} TC)")

    # Load accounts to allocate (all due/overdue accounts)
    # Use most recent date in mart (or period_month if specified)
    cur.execute("""
        SELECT
            m.account_id, a.customer_id, m.bucket,
            m.treatment_code, a.pincode,
            g.lat, g.lon,
            c.lang_pref, m.overdue_amt, m.bounce_p,
            m.owner_agent_id
        FROM mart_account_daily m
        JOIN dim_account a ON m.account_id = a.account_id
        LEFT JOIN dim_geo g ON a.geo_id = g.geo_id
        LEFT JOIN dim_customer c ON a.customer_id = c.customer_id
        WHERE m.date = (SELECT MAX(date) FROM mart_account_daily)
          AND m.bucket IN ('X', 'B1', 'B2', 'B3', 'NPA_90', 'NPA_120')
        ORDER BY m.overdue_amt DESC, m.bounce_p DESC
    """)

    account_rows = cur.fetchall()
    accounts = []
    previous_allocations = {}

    for row in account_rows:
        requires_field = row[2] in ['B2', 'B3', 'NPA_90', 'NPA_120'] or 'FIELD' in (row[3] or '')
        account = Account(
            account_id=row[0],
            customer_id=row[1],
            bucket=row[2],
            treatment_code=row[3] or 'T002_BOT_SMS',
            pincode=row[4],
            lat=row[5] or 28.6139,
            lon=row[6] or 77.2090,
            lang_pref=row[7] or 'hindi',
            overdue_amt=row[8] or 0,
            bounce_p=row[9] or 0,
            current_owner=row[10],
            requires_field=requires_field
        )
        accounts.append(account)
        if account.current_owner:
            previous_allocations[account.account_id] = account.current_owner

    print(f"Loaded {len(accounts)} accounts to allocate")
    print(f"  - {sum(1 for a in accounts if a.requires_field)} require field visits")
    print(f"  - {len(previous_allocations)} have previous owners (continuity candidate)\n")

    # Run allocation
    engine = AllocationEngine()

    if algorithm == 'ortools' and ORTOOLS_AVAILABLE:
        allocations = engine.allocate_ortools(accounts, agents, previous_allocations)
    else:
        allocations = engine.allocate_greedy(accounts, agents, previous_allocations)

    print(f"\n✓ Allocated {len(allocations)} accounts")

    # Write to database
    if allocations:
        cur.execute("DELETE FROM allocations WHERE period_month = %s", (period_month,))

        insert_query = """
            INSERT INTO allocations (
                account_id, period_month, owner_agent_id,
                allocation_reason, difficulty_score, allocated_by
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """

        values = [
            (
                alloc['account_id'],
                period_month,
                alloc['owner_agent_id'],
                alloc['allocation_reason'],
                alloc.get('difficulty_score', 0.5),
                alloc['allocated_by']
            )
            for alloc in allocations
        ]

        execute_batch(cur, insert_query, values)
        conn.commit()

        print(f"✓ Written {len(allocations)} allocations to database\n")

    # Generate beat plans for FOS agents
    planner = BeatPlanner()
    all_beat_plans = []

    for agent in agents:
        if agent.role != 'FOS':
            continue

        # Get this agent's allocated accounts (deduplicated)
        agent_account_ids = {
            alloc['account_id'] for alloc in allocations
            if alloc['owner_agent_id'] == agent.agent_id
        }
        # Use dict to ensure unique accounts by ID
        agent_accounts_dict = {acc.account_id: acc for acc in accounts if acc.account_id in agent_account_ids}
        agent_accounts = list(agent_accounts_dict.values())

        if agent_accounts:
            beat_plan = planner.create_beat_plan(agent, agent_accounts, period_month)
            all_beat_plans.extend(beat_plan)

    if all_beat_plans:
        print(f"Generating beat plans for {period_month.strftime('%Y-%m-%d')}...")

        # Deduplicate beat plans by (agent_id, beat_date, account_id)
        seen = set()
        unique_beat_plans = []
        for bp in all_beat_plans:
            key = (bp['agent_id'], bp['beat_date'], bp['account_id'])
            if key not in seen:
                seen.add(key)
                unique_beat_plans.append(bp)
        all_beat_plans = unique_beat_plans

        cur.execute("""
            DELETE FROM beat_plan
            WHERE beat_date = %s
        """, (period_month,))
        conn.commit()

        insert_beat_query = """
            INSERT INTO beat_plan (
                agent_id, beat_date, account_id, sequence_no,
                priority, expected_collection, visit_reason, notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        beat_values = [
            (
                bp['agent_id'], bp['beat_date'], bp['account_id'], bp['sequence_no'],
                bp['priority'], bp['expected_collection'], bp['visit_reason'], bp['notes']
            )
            for bp in all_beat_plans
        ]

        execute_batch(cur, insert_beat_query, beat_values)
        conn.commit()

        print(f"✓ Created {len(all_beat_plans)} beat plan stops for field agents\n")

    cur.close()
    conn.close()

    return len(allocations)


if __name__ == '__main__':
    # Test allocation engine
    import os

    db_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'database': os.getenv('POSTGRES_DB', 'collectos'),
        'user': os.getenv('POSTGRES_USER', 'collectos'),
        'password': os.getenv('POSTGRES_PASSWORD', 'collectos123'),
    }

    # Run monthly allocation for current month
    period_month = date.today().replace(day=1)

    try:
        num_allocated = run_monthly_allocation(
            db_config=db_config,
            period_month=period_month,
            algorithm='greedy'  # Change to 'ortools' to test optimization
        )
        print(f"✓ Monthly allocation complete: {num_allocated} accounts assigned\n")
    except Exception as e:
        print(f"✗ Allocation failed: {e}")
        import traceback
        traceback.print_exc()
