"""
Synthgen Seed Script
Main entry point for generating and loading synthetic bank data

Usage:
    python -m synthgen.seed

Reads configuration from environment variables (.env file)
"""
import logging
import sys
import time
from datetime import datetime

from .config import SynthgenConfig
from .geo_generator import GeoGenerator
from .customer_generator import CustomerGenerator
from .portfolio_generator import PortfolioGenerator
from .roster_generator import RosterGenerator
from .db_loader import DatabaseLoader

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
    """Main seed execution"""
    start_time = time.time()

    logger.info("=" * 80)
    logger.info("CollectOS Synthetic Bank Generator - Session 2")
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
    logger.info(f"  Accounts: {config.n_accounts:,}")
    logger.info(f"  Customers: {config.n_customers:,}")
    logger.info(f"  History months: {config.history_months}")
    logger.info(f"  Seed: {config.seed}")
    logger.info(f"  Agents: FOS={config.n_fos}, TC={config.n_telecallers}, TL={config.n_tl}, ACM={config.n_acm}, RCM={config.n_rcm}")
    logger.info("")

    # Step 1: Generate Geography
    logger.info("Step 1/6: Generating geography distribution...")
    geo_gen = GeoGenerator(seed=config.seed)
    # Generate enough unique geographies (one per ~100 customers for variety)
    n_geos = max(100, config.n_customers // 100)
    geos = geo_gen.generate_geo_distribution(n_geos)
    logger.info(f"✓ Generated {len(geos)} unique geographies across {len(set(g.state for g in geos))} states")
    logger.info("")

    # Step 2: Generate Customers
    logger.info("Step 2/6: Generating customer profiles...")
    customer_gen = CustomerGenerator(seed=config.seed)
    customers = customer_gen.generate_customers(config.n_customers, geos)
    logger.info(f"✓ Generated {len(customers)} customer profiles")
    logger.info("")

    # Step 3: Generate Portfolio (Accounts + EMI Schedules)
    logger.info("Step 3/6: Generating loan portfolio...")
    portfolio_gen = PortfolioGenerator(
        product_mix=config.product_mix,
        archetype_dist=config.archetype_dist,
        seed=config.seed
    )
    accounts, emi_schedules = portfolio_gen.generate_portfolio(
        config.n_accounts, customers, geos
    )
    logger.info(f"✓ Generated {len(accounts)} accounts")
    logger.info(f"  Product mix:")
    for product, count in sorted(
        [(p, sum(1 for a in accounts if a.product_type == p)) for p in config.product_mix.keys()],
        key=lambda x: x[1],
        reverse=True
    ):
        pct = count / len(accounts) * 100
        logger.info(f"    {product}: {count:,} ({pct:.1f}%)")

    logger.info(f"  Archetype distribution (hidden truth):")
    for archetype, count in sorted(
        [(a, sum(1 for acc in accounts if acc.archetype == a)) for a in config.archetype_dist.keys()],
        key=lambda x: x[1],
        reverse=True
    ):
        pct = count / len(accounts) * 100
        logger.info(f"    {archetype}: {count:,} ({pct:.1f}%)")

    logger.info(f"✓ Generated {len(emi_schedules):,} EMI schedule entries")
    logger.info("")

    # Step 4: Generate Agent Roster
    logger.info("Step 4/6: Generating agent roster...")
    roster_gen = RosterGenerator(seed=config.seed)
    teams, agents = roster_gen.generate_roster(
        config.get_agent_counts_by_role(), geos
    )
    logger.info(f"✓ Generated {len(teams)} teams")
    logger.info(f"✓ Generated {len(agents)} agents:")
    for role, count in sorted(
        [(r, sum(1 for a in agents if a.role == r)) for r in ["RCM", "ACM", "TL", "FOS", "TC"]],
        key=lambda x: ["RCM", "ACM", "TL", "FOS", "TC"].index(x[0])
    ):
        logger.info(f"    {role}: {count:,}")
    logger.info("")

    # Step 5: Load to Database
    logger.info("Step 5/6: Loading data to PostgreSQL...")
    loader = DatabaseLoader(config.database_url)

    try:
        loader.connect()
        logger.info("✓ Connected to database")

        # Load geos and get the geo_id mapping
        geo_id_map = loader.load_geos(geos)

        # Use geo_id_map for other loads
        loader.load_customers(customers, geo_id_map)
        loader.load_accounts(accounts, emi_schedules, geo_id_map)
        loader.load_teams(teams)
        loader.load_agents(agents, geo_id_map)

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

    # Step 6: Summary
    elapsed = time.time() - start_time
    logger.info("=" * 80)
    logger.info("Seed completed successfully!")
    logger.info(f"  Accounts: {len(accounts):,}")
    logger.info(f"  Customers: {len(customers):,}")
    logger.info(f"  Agents: {len(agents):,}")
    logger.info(f"  Teams: {len(teams):,}")
    logger.info(f"  EMI schedules: {len(emi_schedules):,}")
    logger.info(f"  Time: {elapsed:.1f}s")
    logger.info("")
    logger.info("Next: Run Session 3 to generate 24-month behavioral history")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
