"""
LLM Daily Brief Generator - Executive summaries powered by Ollama

Generates natural language daily briefs for management using local LLM.
Summarizes collections performance, highlights anomalies, and provides insights.
"""

import psycopg2
import psycopg2.extras
import requests
from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
import os
import json


class DailyBriefGenerator:
    """
    Generate executive daily briefs using LLM

    Structure:
    1. Executive Summary (3-5 bullet points)
    2. Key Metrics (collections, resolution, team performance)
    3. Highlights (top performers, wins)
    4. Concerns (underperformance, risks)
    5. Recommendations (actionable insights)
    """

    def __init__(
        self,
        db_host: str = 'localhost',
        db_port: int = 5432,
        db_name: str = 'collectos',
        db_user: str = 'collectos',
        db_password: Optional[str] = None,
        ollama_host: str = 'http://localhost:11434',
        model: str = 'qwen2.5:7b',
    ):
        self.db_config = {
            'host': db_host,
            'port': db_port,
            'dbname': db_name,
            'user': db_user,
            'password': db_password or os.getenv('POSTGRES_PASSWORD'),
        }
        self.ollama_host = ollama_host
        self.model = model

    def get_db_connection(self):
        """Create database connection"""
        return psycopg2.connect(**self.db_config)

    def collect_daily_metrics(self, target_date: date) -> Dict:
        """Collect all metrics needed for brief"""
        metrics = {}

        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Overall collections metrics
                cur.execute("""
                    SELECT
                        COUNT(DISTINCT p.account_id) as accounts_resolved,
                        SUM(p.amount) as total_collected,
                        COUNT(*) as payment_count,
                        AVG(p.amount) as avg_payment
                    FROM fct_payments p
                    WHERE DATE(p.pay_date) = %s
                """, (target_date,))
                metrics['collections'] = dict(cur.fetchone())

                # Bot performance
                cur.execute("""
                    SELECT
                        COUNT(*) as total_calls,
                        SUM(CASE WHEN call_outcome = 'CONNECT_RPC' THEN 1 ELSE 0 END) as connected_calls,
                        SUM(CASE WHEN call_outcome = 'CONNECT_RPC' THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) as connection_rate
                    FROM fct_calls
                    WHERE DATE(call_date) = %s
                      AND channel = 'BOT'
                """, (target_date,))
                metrics['bot'] = dict(cur.fetchone())

                # Field performance
                cur.execute("""
                    SELECT
                        COUNT(*) as total_visits,
                        SUM(CASE WHEN disposition IN ('CUSTOMER_MET', 'PAYMENT_COLLECTED') THEN 1 ELSE 0 END) as successful_visits,
                        SUM(CASE WHEN disposition IN ('CUSTOMER_MET', 'PAYMENT_COLLECTED') THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) as success_rate
                    FROM fct_visits
                    WHERE DATE(visit_date) = %s
                """, (target_date,))
                metrics['field'] = dict(cur.fetchone())

                # PTP performance
                cur.execute("""
                    SELECT
                        SUM(CASE WHEN DATE(made_at) = %s THEN 1 ELSE 0 END) as ptps_made_today,
                        SUM(CASE WHEN promise_date = %s AND status = 'kept' THEN 1 ELSE 0 END) as ptps_kept_today,
                        SUM(CASE WHEN promise_date = %s AND status = 'broken' THEN 1 ELSE 0 END) as ptps_broken_today
                    FROM fct_ptp
                    WHERE DATE(made_at) = %s OR promise_date = %s
                """, (target_date, target_date, target_date, target_date, target_date))
                metrics['ptp'] = dict(cur.fetchone())

                # Team performance (top 3 teams)
                cur.execute("""
                    SELECT
                        t.name as team_name,
                        COUNT(DISTINCT p.account_id) as accounts_resolved,
                        SUM(p.amount) as total_collected
                    FROM fct_payments p
                    JOIN mart_account_daily mad ON
                        p.account_id = mad.account_id AND
                        mad.date = %s
                    JOIN dim_agent ag ON mad.owner_agent_id = ag.agent_id
                    JOIN dim_team t ON ag.team_id = t.team_id
                    WHERE DATE(p.pay_date) = %s
                    GROUP BY t.team_id, t.name
                    ORDER BY SUM(p.amount) DESC
                    LIMIT 3
                """, (target_date, target_date))
                metrics['top_teams'] = [dict(row) for row in cur.fetchall()]

                # Agent performance (top 5 agents)
                cur.execute("""
                    SELECT
                        ag.name as agent_name,
                        ag.role,
                        COUNT(DISTINCT p.account_id) as accounts_resolved,
                        SUM(p.amount) as total_collected
                    FROM fct_payments p
                    JOIN mart_account_daily mad ON
                        p.account_id = mad.account_id AND
                        mad.date = %s
                    JOIN dim_agent ag ON mad.owner_agent_id = ag.agent_id
                    WHERE DATE(p.pay_date) = %s
                    GROUP BY ag.agent_id, ag.name, ag.role
                    ORDER BY SUM(p.amount) DESC
                    LIMIT 5
                """, (target_date, target_date))
                metrics['top_agents'] = [dict(row) for row in cur.fetchall()]

                # Portfolio health
                cur.execute("""
                    SELECT
                        bucket,
                        COUNT(*) as accounts,
                        SUM(overdue_amt) as total_overdue
                    FROM mart_account_daily
                    WHERE date = %s
                    GROUP BY bucket
                    ORDER BY
                        CASE bucket
                            WHEN 'X' THEN 1
                            WHEN 'B1' THEN 2
                            WHEN 'B2' THEN 3
                            WHEN 'B3' THEN 4
                            WHEN '90+' THEN 5
                            ELSE 6
                        END
                """, (target_date,))
                metrics['portfolio'] = [dict(row) for row in cur.fetchall()]

                # Compare to yesterday
                yesterday = target_date - timedelta(days=1)
                cur.execute("""
                    SELECT
                        SUM(p.amount) as total_collected
                    FROM fct_payments p
                    WHERE DATE(p.pay_date) = %s
                """, (yesterday,))
                yesterday_result = cur.fetchone()
                metrics['yesterday_collections'] = float(yesterday_result['total_collected'] or 0)

        return metrics

    def generate_brief_llm(self, metrics: Dict, target_date: date) -> str:
        """Generate brief using LLM"""

        # Format metrics into context for LLM
        context = f"""
You are a collections operations analyst generating a daily executive brief for {target_date.strftime('%B %d, %Y')}.

KEY METRICS:

Collections Performance:
- Total collected: ₹{metrics['collections']['total_collected']:,.0f}
- Accounts resolved: {metrics['collections']['accounts_resolved']:,}
- Number of payments: {metrics['collections']['payment_count']:,}
- Average payment: ₹{metrics['collections']['avg_payment']:,.0f}
- Yesterday's collections: ₹{metrics['yesterday_collections']:,.0f}
- Day-over-day change: {((metrics['collections']['total_collected'] / metrics['yesterday_collections'] - 1) * 100) if metrics['yesterday_collections'] > 0 else 0:.1f}%

Bot Performance:
- Total calls: {metrics['bot']['total_calls']:,}
- Connected calls: {metrics['bot']['connected_calls']:,}
- Connection rate: {metrics['bot']['connection_rate']:.1%}

Field Performance:
- Total visits: {metrics['field']['total_visits']:,}
- Successful visits: {metrics['field']['successful_visits']:,}
- Success rate: {metrics['field']['success_rate']:.1%}

PTP Performance:
- PTPs made today: {metrics['ptp']['ptps_made_today']:,}
- PTPs kept today: {metrics['ptp']['ptps_kept_today']:,}
- PTPs broken today: {metrics['ptp']['ptps_broken_today']:,}
- Keep rate: {(metrics['ptp']['ptps_kept_today'] / (metrics['ptp']['ptps_kept_today'] + metrics['ptp']['ptps_broken_today']) * 100) if (metrics['ptp']['ptps_kept_today'] + metrics['ptp']['ptps_broken_today']) > 0 else 0:.1f}%

Top Performing Teams:
{chr(10).join([f"- {t['team_name']}: ₹{t['total_collected']:,.0f} ({t['accounts_resolved']} accounts)" for t in metrics['top_teams']])}

Top Performing Agents:
{chr(10).join([f"- {a['agent_name']} ({a['role']}): ₹{a['total_collected']:,.0f} ({a['accounts_resolved']} accounts)" for a in metrics['top_agents']])}

Portfolio Health:
{chr(10).join([f"- {p['bucket']}: {p['accounts']:,} accounts, ₹{p['total_overdue']:,.0f} overdue" for p in metrics['portfolio']])}

Generate a concise executive daily brief with these sections:

## Executive Summary
(3-5 bullet points capturing the day's highlights)

## Key Wins
(Notable achievements, top performers, positive trends)

## Concerns
(Underperformance, risks, issues requiring attention)

## Recommendations
(2-3 actionable insights for tomorrow)

Keep it professional, data-driven, and actionable. Focus on insights, not just repeating numbers.
"""

        # Call Ollama API
        try:
            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": context,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,  # Lower temp for more factual output
                        "top_p": 0.9,
                    }
                },
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                return result['response']
            else:
                return f"Error generating brief: {response.status_code}"

        except Exception as e:
            return f"Error calling LLM: {str(e)}"

    def generate_fallback_brief(self, metrics: Dict, target_date: date) -> str:
        """Generate template-based brief if LLM unavailable"""

        collections_change = ((metrics['collections']['total_collected'] / metrics['yesterday_collections'] - 1) * 100) if metrics['yesterday_collections'] > 0 else 0

        brief = f"""
# DAILY COLLECTIONS BRIEF
**Date:** {target_date.strftime('%B %d, %Y')}

## Executive Summary

- Collected ₹{metrics['collections']['total_collected']:,.0f} from {metrics['collections']['accounts_resolved']:,} accounts ({collections_change:+.1f}% vs yesterday)
- Bot achieved {metrics['bot']['connection_rate']:.0%} connection rate across {metrics['bot']['total_calls']:,} calls
- Field agents completed {metrics['field']['total_visits']:,} visits with {metrics['field']['success_rate']:.0%} success rate
- PTP keep rate at {(metrics['ptp']['ptps_kept_today'] / (metrics['ptp']['ptps_kept_today'] + metrics['ptp']['ptps_broken_today']) * 100) if (metrics['ptp']['ptps_kept_today'] + metrics['ptp']['ptps_broken_today']) > 0 else 0:.0f}% ({metrics['ptp']['ptps_kept_today']} kept, {metrics['ptp']['ptps_broken_today']} broken)

## Top Performers

**Teams:**
{chr(10).join([f"- {t['team_name']}: ₹{t['total_collected']:,.0f}" for t in metrics['top_teams']])}

**Agents:**
{chr(10).join([f"- {a['agent_name']} ({a['role']}): ₹{a['total_collected']:,.0f}" for a in metrics['top_agents'][:3]])}

## Portfolio Status

{chr(10).join([f"- {p['bucket']}: {p['accounts']:,} accounts, ₹{p['total_overdue']:,.0f} overdue" for p in metrics['portfolio']])}

## Recommendations

1. {"Focus on maintaining momentum" if collections_change > 0 else "Investigate collection drop and adjust strategy"}
2. {"Continue bot optimization" if metrics['bot']['connection_rate'] > 0.3 else "Review bot connection issues"}
3. {"Scale field visits" if metrics['field']['success_rate'] > 0.5 else "Improve field visit targeting"}
"""
        return brief

    def generate_brief(
        self,
        target_date: date,
        use_llm: bool = True,
    ) -> str:
        """Generate daily brief (main entry point)"""

        print(f"Generating daily brief for {target_date}...")

        # Collect metrics
        metrics = self.collect_daily_metrics(target_date)

        # Generate brief
        if use_llm:
            print("Using LLM to generate brief...")
            brief = self.generate_brief_llm(metrics, target_date)
        else:
            print("Using template to generate brief...")
            brief = self.generate_fallback_brief(metrics, target_date)

        return brief

    def save_brief(self, target_date: date, brief: str):
        """Save brief to database"""
        with self.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO daily_briefs (
                        date, brief_text, generated_at
                    ) VALUES (
                        %s, %s, NOW()
                    )
                    ON CONFLICT (date)
                    DO UPDATE SET
                        brief_text = EXCLUDED.brief_text,
                        generated_at = NOW()
                """, (target_date, brief))

                conn.commit()


def generate_daily_brief(
    target_date: Optional[date] = None,
    use_llm: bool = True,
    print_output: bool = True,
) -> str:
    """Main entry point for daily brief generation"""

    target_date = target_date or date.today()

    generator = DailyBriefGenerator()
    brief = generator.generate_brief(target_date, use_llm=use_llm)

    if print_output:
        print("\n" + "="*100)
        print(brief)
        print("="*100 + "\n")

    # Save to database
    generator.save_brief(target_date, brief)
    print(f"Brief saved to database for {target_date}")

    return brief


if __name__ == '__main__':
    import sys

    target_date = date.today()
    use_llm = True

    if len(sys.argv) > 1:
        target_date = datetime.strptime(sys.argv[1], '%Y-%m-%d').date()

    if len(sys.argv) > 2 and sys.argv[2] == '--no-llm':
        use_llm = False

    generate_daily_brief(target_date, use_llm=use_llm)
