"""
Command Center Page
Dashboard showing today's demand, queue burn-down, resolution vs target, channel split
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from typing import Dict, Any

from database import execute_query
from auth import require_permission
from config import COLORS


@require_permission("command_center")
def render():
    """Render Command Center page."""
    st.title("🎯 Command Center")
    st.markdown(f"**Date:** {date.today().strftime('%Y-%m-%d')}")
    st.markdown("---")

    # Top-level metrics
    show_key_metrics()

    st.markdown("---")

    # Two-column layout
    col1, col2 = st.columns(2)

    with col1:
        show_portfolio_snapshot()
        show_channel_split()

    with col2:
        show_queue_burndown()
        show_resolution_progress()


def show_key_metrics():
    """Display key metrics cards."""
    try:
        query = """
            SELECT
                COUNT(DISTINCT account_id) as total_accounts,
                SUM(overdue_amt) as total_overdue,
                AVG(dpd) as avg_dpd,
                SUM(CASE WHEN bucket = 'X' THEN 1 ELSE 0 END) as bucket_x,
                SUM(CASE WHEN bucket = 'B1' THEN 1 ELSE 0 END) as bucket_b1,
                SUM(CASE WHEN bucket = 'B2' THEN 1 ELSE 0 END) as bucket_b2,
                SUM(CASE WHEN bucket IN ('B3+', 'NPA') THEN 1 ELSE 0 END) as bucket_b3_plus
            FROM mart_account_daily
            WHERE date = CURRENT_DATE
        """
        results = execute_query(query)

        if results:
            data = results[0]

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "Total Accounts",
                    f"{data['total_accounts']:,}" if data['total_accounts'] else "0"
                )

            with col2:
                overdue = data['total_overdue'] or 0
                st.metric(
                    "Total Overdue",
                    f"₹{overdue/10000000:.2f}Cr" if overdue > 0 else "₹0"
                )

            with col3:
                avg_dpd = data['avg_dpd'] or 0
                st.metric(
                    "Avg DPD",
                    f"{avg_dpd:.1f} days"
                )

            with col4:
                # Resolution target (example: 15% of overdue portfolio daily)
                target = overdue * 0.15 if overdue else 0
                st.metric(
                    "Today's Target",
                    f"₹{target/10000000:.2f}Cr"
                )

    except Exception as e:
        st.error(f"Error loading key metrics: {e}")


def show_portfolio_snapshot():
    """Display portfolio breakdown by bucket."""
    st.subheader("Portfolio by Bucket")

    try:
        query = """
            SELECT
                bucket,
                COUNT(DISTINCT account_id) as accounts,
                SUM(overdue_amt) as overdue,
                AVG(dpd) as avg_dpd
            FROM mart_account_daily
            WHERE date = CURRENT_DATE
            GROUP BY bucket
            ORDER BY
                CASE bucket
                    WHEN 'X' THEN 1
                    WHEN 'B1' THEN 2
                    WHEN 'B2' THEN 3
                    ELSE 4
                END
        """
        results = execute_query(query)

        if results:
            df = pd.DataFrame(results)
            df['overdue_cr'] = df['overdue'] / 10000000
            df['avg_dpd'] = df['avg_dpd'].round(1)

            # Display as table
            display_df = df[['bucket', 'accounts', 'overdue_cr', 'avg_dpd']].copy()
            display_df.columns = ['Bucket', 'Accounts', 'Overdue (Cr)', 'Avg DPD']

            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
            )

            # Bar chart
            st.bar_chart(df.set_index('bucket')['accounts'], color=COLORS['primary'])
        else:
            st.info("No portfolio data available for today")

    except Exception as e:
        st.error(f"Error loading portfolio snapshot: {e}")


def show_queue_burndown():
    """Display queue burndown chart."""
    st.subheader("Queue Burndown (Today)")

    try:
        # Get queue counts by hour (simulated for now)
        # In production, this would track actual queue consumption throughout the day
        query = """
            SELECT
                channel,
                COUNT(*) as queue_size,
                SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) as pending
            FROM call_queue
            WHERE created_at >= CURRENT_DATE
            GROUP BY channel
            ORDER BY channel
        """
        results = execute_query(query)

        if results:
            df = pd.DataFrame(results)

            # Show metrics
            total_queue = df['queue_size'].sum()
            total_completed = df['completed'].sum()
            total_pending = df['pending'].sum()

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Queue", f"{total_queue:,}")
            with col2:
                st.metric("Completed", f"{total_completed:,}")
            with col3:
                pct_complete = (total_completed / total_queue * 100) if total_queue > 0 else 0
                st.metric("Progress", f"{pct_complete:.1f}%")

            # Channel breakdown
            st.dataframe(
                df[['channel', 'queue_size', 'completed', 'pending']],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No queue data available for today")

    except Exception as e:
        st.error(f"Error loading queue burndown: {e}")


def show_channel_split():
    """Display treatment channel distribution."""
    st.subheader("Treatment Channel Split")

    try:
        query = """
            SELECT
                treatment,
                COUNT(DISTINCT account_id) as accounts,
                SUM(overdue_amt) as overdue
            FROM mart_account_daily
            WHERE date = CURRENT_DATE
              AND treatment IS NOT NULL
            GROUP BY treatment
            ORDER BY accounts DESC
        """
        results = execute_query(query)

        if results:
            df = pd.DataFrame(results)
            df['overdue_cr'] = df['overdue'] / 10000000

            # Display table
            display_df = df[['treatment', 'accounts', 'overdue_cr']].copy()
            display_df.columns = ['Channel', 'Accounts', 'Overdue (Cr)']

            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
            )

            # Pie chart of account distribution
            if len(df) > 0:
                st.bar_chart(df.set_index('treatment')['accounts'], color=COLORS['info'])
        else:
            st.info("No treatment data available for today")

    except Exception as e:
        st.error(f"Error loading channel split: {e}")


def show_resolution_progress():
    """Display resolution progress vs target."""
    st.subheader("Resolution Progress (MTD)")

    try:
        # Get current month payments
        query = """
            SELECT
                DATE(pay_date) as date,
                COUNT(*) as payment_count,
                SUM(amount) as total_collected
            FROM fct_payments
            WHERE pay_date >= DATE_TRUNC('month', CURRENT_DATE)
              AND pay_date <= CURRENT_DATE
            GROUP BY DATE(pay_date)
            ORDER BY date
        """
        results = execute_query(query)

        if results:
            df = pd.DataFrame(results)
            df['total_collected_cr'] = df['total_collected'] / 10000000
            df['date'] = pd.to_datetime(df['date'])

            # Show cumulative metrics
            total_collected = df['total_collected'].sum()
            total_payments = df['payment_count'].sum()

            col1, col2 = st.columns(2)
            with col1:
                st.metric("MTD Collections", f"₹{total_collected/10000000:.2f}Cr")
            with col2:
                st.metric("MTD Payments", f"{total_payments:,}")

            # Line chart
            st.line_chart(df.set_index('date')['total_collected_cr'])
        else:
            st.info("No payment data available for current month")

    except Exception as e:
        st.error(f"Error loading resolution progress: {e}")
