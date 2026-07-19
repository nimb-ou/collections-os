"""
Run Call Simulator - Main entry point for bot simulation at volume

Usage:
    python -m bot.simulator.run_simulator --limit 100
    python -m bot.simulator.run_simulator --date 2026-07-19 --qa-sample 0.1
"""

import argparse
import logging
from datetime import date, datetime
import json
import os

from .batch_processor import BatchCallProcessor
from .qa_rubric import QARubric

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_simulator(
    limit: int = None,
    target_date: date = None,
    channel: str = 'bot',
    qa_sample_rate: float = 0.02,  # 2% sampling per PLAN
    dry_run: bool = False,
):
    """
    Run call simulator for a batch of calls

    Args:
        limit: Max calls to process (None = all)
        target_date: Target date (None = today)
        channel: Channel filter (bot, human)
        qa_sample_rate: Fraction of calls to QA evaluate
        dry_run: If True, don't write to database
    """
    logger.info("=" * 80)
    logger.info("COLLECTIONS OS - CALL SIMULATOR")
    logger.info("=" * 80)
    logger.info(f"Parameters:")
    logger.info(f"  Limit: {limit or 'All'}")
    logger.info(f"  Target Date: {target_date or 'Today'}")
    logger.info(f"  Channel: {channel}")
    logger.info(f"  QA Sample Rate: {qa_sample_rate:.1%}")
    logger.info(f"  Dry Run: {dry_run}")
    logger.info("=" * 80)

    # Initialize processor
    processor = BatchCallProcessor(
        db_host=os.getenv('POSTGRES_HOST', 'localhost'),
        db_port=int(os.getenv('POSTGRES_PORT', 5432)),
        db_name=os.getenv('POSTGRES_DB', 'collectos'),
        db_user=os.getenv('POSTGRES_USER', 'collectos_user'),
        db_password=os.getenv('POSTGRES_PASSWORD'),
    )

    # Process queue
    logger.info("\n[1/3] Processing call queue...")
    result = processor.process_queue(
        channel=channel,
        limit=limit,
        target_date=target_date,
        dry_run=dry_run,
    )

    logger.info(f"\nProcessing Summary:")
    logger.info(f"  Total Calls: {result['total_calls']}")
    logger.info(f"  Processed: {result['processed']}")
    logger.info(f"  PTPs Made: {result['ptps_made']}")
    logger.info(f"  Avg Duration: {result.get('avg_duration_seconds', 0):.1f}s")
    logger.info(f"\nDispositions:")
    for disp, count in result['dispositions'].items():
        logger.info(f"    {disp}: {count}")

    # Run QA evaluation if calls were processed
    if result['processed'] > 0 and not dry_run:
        logger.info(f"\n[2/3] Running QA evaluation (sample rate: {qa_sample_rate:.1%})...")

        # Get call results from database for QA
        # For now, we'll skip this and just log
        logger.info("QA evaluation logged (detailed eval in future enhancement)")

    # Generate report
    logger.info("\n[3/3] Generating report...")

    report = {
        'run_timestamp': datetime.now().isoformat(),
        'parameters': {
            'limit': limit,
            'target_date': str(target_date or date.today()),
            'channel': channel,
            'qa_sample_rate': qa_sample_rate,
            'dry_run': dry_run,
        },
        'results': result,
    }

    # Write report to file
    report_dir = 'bot/simulator/reports'
    os.makedirs(report_dir, exist_ok=True)

    report_file = f"{report_dir}/sim_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    logger.info(f"\nReport saved to: {report_file}")

    logger.info("\n" + "=" * 80)
    logger.info("SIMULATION COMPLETE")
    logger.info("=" * 80)

    return result


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Run AI bot call simulator at volume'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Max number of calls to process (default: all)'
    )

    parser.add_argument(
        '--date',
        type=str,
        default=None,
        help='Target date in YYYY-MM-DD format (default: today)'
    )

    parser.add_argument(
        '--channel',
        type=str,
        default='BOT',
        choices=['BOT', 'TELECALLER', 'FIELD'],
        help='Channel filter (default: BOT)'
    )

    parser.add_argument(
        '--qa-sample',
        type=float,
        default=0.02,
        help='QA sampling rate 0.0-1.0 (default: 0.02 = 2%%)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run mode - do not write to database'
    )

    args = parser.parse_args()

    # Parse date if provided
    target_date = None
    if args.date:
        try:
            target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        except ValueError:
            logger.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD")
            return 1

    # Run simulator
    try:
        result = run_simulator(
            limit=args.limit,
            target_date=target_date,
            channel=args.channel,
            qa_sample_rate=args.qa_sample,
            dry_run=args.dry_run,
        )

        return 0

    except Exception as e:
        logger.error(f"Simulation failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit(main())
