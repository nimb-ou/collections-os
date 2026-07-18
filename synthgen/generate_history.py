"""
Generate History Script
Generates 24-month behavioral history for existing accounts
Run after seed.py has created the portfolio

Usage:
    python -m synthgen.generate_history
"""
import logging
import sys
import time
import psycopg2
from datetime import date

from .config import SynthgenConfig
from .history_generator import HistoryGenerator
from .history_loader import HistoryLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Main history generation execution"""
    start_time = time.time()

    logger.info("=" * 80)
    logger.info("CollectOS Behavioral History Generator - Session 3")
    logger.info("=" * 80)

    # Load configuration
    logger.info("Loading configuration from environment...")
    try:
        config = SynthgenConfig.from_env()
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)

    logger.info(f"Configuration loaded:")
    logger.info(f"  Mode: {'SMALL (30k accounts)' if config.small_mode else 'FULL (300k accounts)'}")
    logger.info(f"  History months: {config.history_months}")
    logger.info(f"  Seed: {config.seed}")
    logger.info("")

    # Connect to database and fetch data
    logger.info("Fetching accounts and archetypes from database...")
    try:
        conn = psycopg2.connect(config.database_url)
        cur = conn.cursor()

        # Fetch accounts with archetypes from temp table
        cur.execute("""
            SELECT
                a.account_id,
                a.customer_id,
                a.product_type,
                a.disbursal_date,
                a.disbursal_amt,
                a.tenure_m,
                a.roi,
                a.emi_amt,
                a.cycle_day,
                aa.archetype
            FROM dim_account a
            LEFT JOIN account_archetypes aa ON a.account_id = aa.account_id
            WHERE a.status = 'ACTIVE'
            ORDER BY a.account_id
        """)

        accounts_data = []
        for row in cur.fetchall():
            accounts_data.append({
                'account_id': row[0],
                'customer_id': row[1],
                'product_type': row[2],
                'disbursal_date': row[3],
                'disbursal_amt': float(row[4]),
                'tenure_m': row[5],
                'roi': float(row[6]),
                'emi_amt': float(row[7]),
                'cycle_day': row[8],
                'archetype': row[9] or 'PRIME',  # Default if missing
            })

        logger.info(f"✓ Fetched {len(accounts_data)} accounts")

        # Fetch customers
        cur.execute("""
            SELECT
                c.customer_id,
                c.name,
                cc.phone
            FROM dim_customer c
            LEFT JOIN dim_customer_contacts cc ON c.customer_id = cc.customer_id AND cc.is_primary = true
        """)

        customers_data = {}
        for row in cur.fetchall():
            customers_data[row[0]] = {
                'customer_id': row[0],
                'name': row[1],
                'primary_phone': row[2] or '9999999999',
            }

        # Map customers by account_id for easier lookup
        customer_by_account = {}
        for acc in accounts_data:
            customer_by_account[acc['account_id']] = customers_data.get(acc['customer_id'], {
                'customer_id': acc['customer_id'],
                'name': 'Unknown',
                'primary_phone': '9999999999',
            })

        logger.info(f"✓ Fetched {len(customers_data)} customers")

        # Fetch agents
        cur.execute("""
            SELECT agent_id, name, role, team_id
            FROM dim_agent
            WHERE active = true
        """)

        agents_data = []
        for row in cur.fetchall():
            agents_data.append({
                'agent_id': row[0],
                'name': row[1],
                'role': row[2],
                'team_id': row[3],
            })

        logger.info(f"✓ Fetched {len(agents_data)} agents")

        conn.close()

    except Exception as e:
        logger.error(f"Database error: {e}")
        logger.exception(e)
        sys.exit(1)

    logger.info("")

    # Calculate history start date (24 months before today)
    today = date.today()
    from datetime import timedelta
    import calendar

    def subtract_months(d: date, months: int) -> date:
        month = d.month - 1 - months
        year = d.year + month // 12
        month = month % 12 + 1
        _, last_day = calendar.monthrange(year, month)
        day = min(d.day, last_day)
        return date(year, month, day)

    history_start_date = subtract_months(today, config.history_months)

    logger.info(f"Generating history from {history_start_date} to {today}...")
    logger.info("")

    # Generate history
    generator = HistoryGenerator(seed=config.seed)

    presentations, payments, calls, visits, ptps, sms, mart_snapshots = generator.generate_history(
        accounts_data=accounts_data,
        customers_data=customer_by_account,
        agents_data=agents_data,
        start_date=history_start_date,
        months=config.history_months
    )

    logger.info("")

    # Load to database
    logger.info("Loading history data to PostgreSQL...")
    loader = HistoryLoader(config.database_url)

    try:
        loader.connect()
        logger.info("✓ Connected to database")

        loader.load_presentations(presentations)
        loader.load_payments(payments)
        loader.load_calls(calls)
        loader.load_visits(visits)
        loader.load_ptps(ptps)
        loader.load_sms(sms)
        loader.load_mart_snapshots(mart_snapshots)

        # Get stats
        stats = loader.get_stats()
        logger.info("")
        logger.info("Database statistics:")
        for table, count in stats.items():
            logger.info(f"  {table}: {count:,} rows")

        loader.close()
        logger.info("✓ Database connection closed")

    except Exception as e:
        logger.error(f"Database error: {e}")
        logger.exception(e)
        sys.exit(1)

    logger.info("")

    # Summary
    elapsed = time.time() - start_time
    logger.info("=" * 80)
    logger.info("History generation completed successfully!")
    logger.info(f"  Accounts: {len(accounts_data):,}")
    logger.info(f"  History period: {config.history_months} months ({history_start_date} to {today})")
    logger.info(f"  Presentations: {len(presentations):,}")
    logger.info(f"  Payments: {len(payments):,}")
    logger.info(f"  Calls: {len(calls):,}")
    logger.info(f"  Visits: {len(visits):,}")
    logger.info(f"  PTPs: {len(ptps):,}")
    logger.info(f"  SMS: {len(sms):,}")
    logger.info(f"  Mart snapshots: {len(mart_snapshots):,}")
    logger.info(f"  Time: {elapsed:.1f}s")
    logger.info("")

    # Calculate aggregate stats
    bounces = [p for p in presentations if p.status == 'B']
    bounce_rate = len(bounces) / len(presentations) * 100 if presentations else 0

    logger.info("Behavioral statistics:")
    logger.info(f"  Bounce rate: {bounce_rate:.1f}%")
    logger.info(f"  Payment rate: {len(payments) / len(presentations) * 100:.1f}%")
    logger.info(f"  Contact attempts: {len(calls) + len(visits):,}")
    logger.info(f"  Call connect rate: {len([c for c in calls if c.outcome == 'CONNECTED']) / len(calls) * 100 if calls else 0:.1f}%")
    logger.info("")

    logger.info("Next: Run Session 4 to build dbt marts and Dagster pipeline")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
