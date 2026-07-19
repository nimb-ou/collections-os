"""
PTP Book Page
Promise-to-Pay tracking: aging, due today, broken promises
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta

from database import execute_query
from auth import require_permission


@require_permission("ptp_book")
def render():
    """Render PTP Book page."""
    st.title("📅 PTP Book")
    st.markdown(f"**Date:** {date.today().strftime('%Y-%m-%d')}")
    st.markdown("---")

    # Top metrics
    show_ptp_metrics()

    st.markdown("---")

    # Tabs
    tab1, tab2, tab3 = st.tabs(["Due Today", "Aging", "Broken PTPs"])

    with tab1:
        show_ptps_due_today()

    with tab2:
        show_ptp_aging()

    with tab3:
        show_broken_ptps()


def show_ptp_metrics():
    """Display PTP summary metrics."""
    try:
        query = """
            SELECT
                COUNT(*) as total_ptps,
                SUM(promised_amt) as total_promised,
                SUM(CASE WHEN ptp_date = CURRENT_DATE THEN 1 ELSE 0 END) as due_today,
                SUM(CASE WHEN ptp_date < CURRENT_DATE AND kept = false THEN 1 ELSE 0 END) as broken,
                SUM(CASE WHEN kept = true THEN 1 ELSE 0 END) as kept,
                AVG(CASE WHEN kept = true THEN 1.0 ELSE 0.0 END) as kept_rate
            FROM fct_ptps
            WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
        """
        results = execute_query(query)

        if results:
            data = results[0]

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Total PTPs (30d)", f"{data['total_ptps']:,}")

            with col2:
                st.metric("Due Today", f"{data['due_today'] or 0:,}")

            with col3:
                st.metric("Broken", f"{data['broken'] or 0:,}")

            with col4:
                kept_rate = (data['kept_rate'] * 100) if data['kept_rate'] else 0
                st.metric("Kept Rate", f"{kept_rate:.1f}%")

    except Exception as e:
        st.error(f"Error loading PTP metrics: {e}")


def show_ptps_due_today():
    """Display PTPs due today."""
    st.subheader("PTPs Due Today")

    try:
        query = """
            SELECT
                fp.ptp_id,
                fp.account_id,
                dc.name as customer_name,
                fp.promised_amt,
                fp.created_at,
                fp.ptp_date,
                fp.kept,
                da.name as agent_name
            FROM fct_ptps fp
            JOIN dim_account dac ON fp.account_id = dac.account_id
            JOIN dim_customer dc ON dac.customer_id = dc.customer_id
            LEFT JOIN dim_agent da ON fp.agent_id = da.agent_id
            WHERE fp.ptp_date = CURRENT_DATE
            ORDER BY fp.promised_amt DESC
        """
        results = execute_query(query)

        if results:
            df = pd.DataFrame(results)
            df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M')

            st.dataframe(
                df[['ptp_id', 'account_id', 'customer_name', 'promised_amt', 'created_at', 'kept', 'agent_name']],
                use_container_width=True,
                hide_index=True,
            )

            # Summary
            total_promised = df['promised_amt'].sum()
            st.info(f"Total promised amount due today: ₹{total_promised/100000:.2f}L")
        else:
            st.info("No PTPs due today")

    except Exception as e:
        st.error(f"Error loading PTPs due today: {e}")


def show_ptp_aging():
    """Display PTP aging analysis."""
    st.subheader("PTP Aging")

    try:
        query = """
            SELECT
                CASE
                    WHEN ptp_date = CURRENT_DATE THEN 'Due Today'
                    WHEN ptp_date = CURRENT_DATE + 1 THEN 'Due Tomorrow'
                    WHEN ptp_date BETWEEN CURRENT_DATE + 2 AND CURRENT_DATE + 7 THEN 'Due in 2-7 days'
                    WHEN ptp_date > CURRENT_DATE + 7 THEN 'Due in 7+ days'
                    WHEN ptp_date < CURRENT_DATE THEN 'Overdue'
                END as aging_bucket,
                COUNT(*) as ptp_count,
                SUM(promised_amt) as total_promised
            FROM fct_ptps
            WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
              AND kept = false
            GROUP BY aging_bucket
            ORDER BY
                CASE aging_bucket
                    WHEN 'Overdue' THEN 1
                    WHEN 'Due Today' THEN 2
                    WHEN 'Due Tomorrow' THEN 3
                    WHEN 'Due in 2-7 days' THEN 4
                    WHEN 'Due in 7+ days' THEN 5
                END
        """
        results = execute_query(query)

        if results:
            df = pd.DataFrame(results)
            df['total_promised_l'] = (df['total_promised'] / 100000).round(2)

            st.dataframe(
                df[['aging_bucket', 'ptp_count', 'total_promised_l']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    'aging_bucket': 'Aging Bucket',
                    'ptp_count': 'PTP Count',
                    'total_promised_l': 'Total Promised (L)'
                }
            )

            st.bar_chart(df.set_index('aging_bucket')['ptp_count'])
        else:
            st.info("No PTP aging data available")

    except Exception as e:
        st.error(f"Error loading PTP aging: {e}")


def show_broken_ptps():
    """Display broken PTPs (overdue and not kept)."""
    st.subheader("Broken PTPs (Last 30 Days)")

    try:
        query = """
            SELECT
                fp.ptp_id,
                fp.account_id,
                dc.name as customer_name,
                fp.promised_amt,
                fp.ptp_date,
                CURRENT_DATE - fp.ptp_date as days_overdue,
                da.name as agent_name
            FROM fct_ptps fp
            JOIN dim_account dac ON fp.account_id = dac.account_id
            JOIN dim_customer dc ON dac.customer_id = dc.customer_id
            LEFT JOIN dim_agent da ON fp.agent_id = da.agent_id
            WHERE fp.ptp_date < CURRENT_DATE
              AND fp.kept = false
              AND fp.created_at >= CURRENT_DATE - INTERVAL '30 days'
            ORDER BY days_overdue DESC, fp.promised_amt DESC
            LIMIT 100
        """
        results = execute_query(query)

        if results:
            df = pd.DataFrame(results)

            st.dataframe(
                df[['ptp_id', 'account_id', 'customer_name', 'promised_amt', 'ptp_date', 'days_overdue', 'agent_name']],
                use_container_width=True,
                hide_index=True,
            )

            # Summary
            total_broken = len(df)
            total_amount = df['promised_amt'].sum()

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Broken PTPs", f"{total_broken:,}")
            with col2:
                st.metric("Total Broken Amount", f"₹{total_amount/100000:.2f}L")

        else:
            st.info("No broken PTPs in the last 30 days")

    except Exception as e:
        st.error(f"Error loading broken PTPs: {e}")
