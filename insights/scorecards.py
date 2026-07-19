"""
Scorecard Calculation - Difficulty-adjusted agent performance scoring

Computes daily scorecards for agents/TLs/ACMs/zones with fairness adjustments.
"""

import psycopg2
import psycopg2.extras
from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
import os
import json


class ScorecardCalculator:
    """
    Calculate performance scorecards with difficulty adjustment

    Composite Score Formula (§5):
    - Difficulty-adjusted resolution: 40%
    - Collection efficiency (₹): 25%
    - PTP-kept rate: 15%
    - Activity compliance: 10%
    - Quality metrics: 10%
    """

    # Score weights
    WEIGHTS = {
        'resolution': 0.40,
        'efficiency': 0.25,
        'ptp_kept': 0.15,
        'activity': 0.10,
        'quality': 0.10,
    }

    def __init__(
        self,
        db_host: str = 'localhost',
        db_port: int = 5432,
        db_name: str = 'collectos',
        db_user: str = 'collectos',
        db_password: Optional[str] = None,
    ):
        self.db_config = {
            'host': db_host,
            'port': db_port,
            'dbname': db_name,
            'user': db_user,
            'password': db_password or os.getenv('POSTGRES_PASSWORD'),
        }

    def get_db_connection(self):
        """Create database connection"""
        return psycopg2.connect(**self.db_config)

    def calculate_agent_scorecards(
        self,
        target_date: date,
        entity_type: str = 'agent',
    ) -> List[Dict]:
        """
        Calculate scorecards for all agents on target date

        Args:
            target_date: Date to calculate for
            entity_type: 'agent', 'tl', 'acm', 'zone'

        Returns:
            List of scorecard dicts
        """
        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Get agent allocations and expected difficulty
                cur.execute("""
                    WITH agent_book AS (
                        SELECT
                            mad.owner_agent_id as agent_id,
                            COUNT(*) as allocated_accounts,
                            AVG(mad.bounce_p) as avg_bounce_risk,
                            AVG(mad.selfcure_p) as avg_selfcure_prob,
                            SUM(mad.overdue_amt) as total_overdue,
                            SUM(CASE WHEN mad.bucket IN ('B2', 'B3', '90+') THEN 1 ELSE 0 END) as deep_bucket_count
                        FROM mart_account_daily mad
                        WHERE mad.date = %s
                          AND mad.owner_agent_id IS NOT NULL
                        GROUP BY mad.owner_agent_id
                    ),
                    agent_outcomes AS (
                        SELECT
                            a.owner_agent_id as agent_id,
                            COUNT(DISTINCT p.account_id) as accounts_resolved,
                            SUM(p.amount) as total_collected,
                            COUNT(DISTINCT c.account_id) as accounts_contacted,
                            COUNT(DISTINCT v.account_id) as accounts_visited
                        FROM mart_account_daily a
                        LEFT JOIN fct_payments p ON
                            a.account_id = p.account_id AND
                            DATE(p.pay_date) = %s
                        LEFT JOIN fct_calls c ON
                            a.account_id = c.account_id AND
                            DATE(c.call_date) = %s AND
                            c.call_outcome = 'CONNECT_RPC'
                        LEFT JOIN fct_visits v ON
                            a.account_id = v.account_id AND
                            DATE(v.visit_date) = %s
                        WHERE a.date = %s
                          AND a.owner_agent_id IS NOT NULL
                        GROUP BY a.owner_agent_id
                    ),
                    ptp_performance AS (
                        SELECT
                            made_by as agent_id,
                            COUNT(*) as ptps_made,
                            SUM(CASE WHEN status = 'kept' THEN 1 ELSE 0 END) as ptps_kept,
                            SUM(CASE WHEN status = 'broken' THEN 1 ELSE 0 END) as ptps_broken
                        FROM fct_ptp
                        WHERE DATE(made_at) = %s
                        GROUP BY made_by
                    )
                    SELECT
                        ab.agent_id,
                        ag.name as agent_name,
                        ag.role,
                        ag.team_id,
                        -- Book characteristics
                        ab.allocated_accounts,
                        ab.avg_bounce_risk,
                        ab.avg_selfcure_prob,
                        ab.total_overdue,
                        ab.deep_bucket_count,
                        -- Outcomes
                        COALESCE(ao.accounts_resolved, 0) as accounts_resolved,
                        COALESCE(ao.total_collected, 0) as total_collected,
                        COALESCE(ao.accounts_contacted, 0) as accounts_contacted,
                        COALESCE(ao.accounts_visited, 0) as accounts_visited,
                        -- PTP performance
                        COALESCE(ptp.ptps_made, 0) as ptps_made,
                        COALESCE(ptp.ptps_kept, 0) as ptps_kept,
                        COALESCE(ptp.ptps_broken, 0) as ptps_broken
                    FROM agent_book ab
                    JOIN dim_agent ag ON ab.agent_id = ag.agent_id
                    LEFT JOIN agent_outcomes ao ON ab.agent_id = ao.agent_id
                    LEFT JOIN ptp_performance ptp ON ab.agent_id = ptp.agent_id
                    WHERE ag.active = TRUE
                    ORDER BY ab.agent_id
                """, (target_date, target_date, target_date, target_date, target_date, target_date))

                agents = cur.fetchall()

        # Calculate scores for each agent
        scorecards = []
        for agent in agents:
            scorecard = self._calculate_agent_score(agent, target_date)
            scorecards.append(scorecard)

        # Rank agents
        scorecards.sort(key=lambda x: x['composite_score'], reverse=True)
        for rank, scorecard in enumerate(scorecards, 1):
            scorecard['rank'] = rank
            scorecard['total_agents'] = len(scorecards)

        return scorecards

    def _calculate_agent_score(self, agent: Dict, target_date: date) -> Dict:
        """Calculate composite score for single agent"""

        # 1. Resolution Score (difficulty-adjusted)
        allocated = agent['allocated_accounts']
        resolved = agent['accounts_resolved']

        # Expected resolution based on book characteristics
        # Higher selfcure_prob = easier book, lower bounce_risk = easier
        expected_resolution_rate = (
            0.30 +  # Base resolution rate
            (agent['avg_selfcure_prob'] or 0.5) * 0.20 +  # Selfcure bonus
            (1 - (agent['avg_bounce_risk'] or 0.15)) * 0.15  # Low risk bonus
        )
        expected_resolved = allocated * expected_resolution_rate

        if expected_resolved > 0:
            resolution_score = min(100, (resolved / expected_resolved) * 100)
        else:
            resolution_score = 0

        # 2. Collection Efficiency (₹)
        if agent['total_overdue'] > 0:
            efficiency_score = min(100, (agent['total_collected'] / agent['total_overdue']) * 100)
        else:
            efficiency_score = 0

        # 3. PTP-kept Rate
        if agent['ptps_made'] > 0:
            ptp_kept_score = (agent['ptps_kept'] / agent['ptps_made']) * 100
        else:
            ptp_kept_score = 0

        # 4. Activity Compliance
        # Expected: contact 80% of allocated accounts
        expected_contacts = allocated * 0.80
        actual_contacts = agent['accounts_contacted'] + agent['accounts_visited']

        if expected_contacts > 0:
            activity_score = min(100, (actual_contacts / expected_contacts) * 100)
        else:
            activity_score = 0

        # 5. Quality (placeholder - would integrate bot QA, audit scores)
        quality_score = 75  # Default baseline

        # Composite Score
        composite_score = (
            resolution_score * self.WEIGHTS['resolution'] +
            efficiency_score * self.WEIGHTS['efficiency'] +
            ptp_kept_score * self.WEIGHTS['ptp_kept'] +
            activity_score * self.WEIGHTS['activity'] +
            quality_score * self.WEIGHTS['quality']
        )

        return {
            'date': target_date.isoformat(),
            'entity_type': 'agent',
            'entity_id': agent['agent_id'],
            'entity_name': agent['agent_name'],
            'role': agent['role'],
            'team_id': agent['team_id'],
            # Metrics
            'allocated_accounts': allocated,
            'accounts_resolved': resolved,
            'total_collected': float(agent['total_collected']),
            'accounts_contacted': agent['accounts_contacted'],
            'ptps_made': agent['ptps_made'],
            'ptps_kept': agent['ptps_kept'],
            # Scores
            'resolution_score': round(resolution_score, 1),
            'efficiency_score': round(efficiency_score, 1),
            'ptp_kept_score': round(ptp_kept_score, 1),
            'activity_score': round(activity_score, 1),
            'quality_score': round(quality_score, 1),
            'composite_score': round(composite_score, 1),
            # Difficulty adjustment
            'expected_resolution_rate': round(expected_resolution_rate, 3),
            'difficulty_index': round(1 - expected_resolution_rate, 3),
            'rank': 0,  # Will be set after sorting
            'total_agents': 0,
        }

    def save_scorecards(self, scorecards: List[Dict]):
        """Save scorecards to database"""
        with self.get_db_connection() as conn:
            with conn.cursor() as cur:
                for scorecard in scorecards:
                    cur.execute("""
                        INSERT INTO scorecard_daily (
                            date, entity_type, entity_id, entity_name,
                            metrics, created_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, NOW()
                        )
                        ON CONFLICT (date, entity_type, entity_id)
                        DO UPDATE SET
                            metrics = EXCLUDED.metrics,
                            updated_at = NOW()
                    """, (
                        scorecard['date'],
                        scorecard['entity_type'],
                        scorecard['entity_id'],
                        scorecard['entity_name'],
                        json.dumps(scorecard),
                    ))

                conn.commit()


def calculate_daily_scorecards(target_date: Optional[date] = None):
    """Main entry point for daily scorecard calculation"""
    target_date = target_date or date.today()

    print(f"Calculating scorecards for {target_date}")

    calculator = ScorecardCalculator()
    scorecards = calculator.calculate_agent_scorecards(target_date)

    print(f"Calculated {len(scorecards)} agent scorecards")
    print(f"Top 5 performers:")
    for i, sc in enumerate(scorecards[:5], 1):
        print(f"  {i}. {sc['entity_name']}: {sc['composite_score']:.1f}")

    calculator.save_scorecards(scorecards)
    print("Scorecards saved to database")

    return scorecards


if __name__ == '__main__':
    import sys

    target_date = date.today()
    if len(sys.argv) > 1:
        target_date = datetime.strptime(sys.argv[1], '%Y-%m-%d').date()

    calculate_daily_scorecards(target_date)
