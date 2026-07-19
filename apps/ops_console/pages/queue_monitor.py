"""
Queue Monitor Page
Real-time queue status, agent productivity, SLA tracking
"""

import streamlit as st
import pandas as pd
from datetime import date

from database import execute_query
from auth import require_permission


@require_permission("queue_monitor")
def render():
    """Render Queue Monitor page."""
    st.title("📞 Queue Monitor")
    st.markdown(f"**Date:** {date.today().strftime('%Y-%m-%d')}")
    st.markdown("---")

    # Top metrics
    show_queue_metrics()

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        show_queue_by_channel()
        show_agent_productivity()

    with col2:
        show_queue_by_priority()
        show_disposition_summary()


def show_queue_metrics():
    """Display queue summary metrics."""
    try:
        query = """
            SELECT
                COUNT(*) as total_queue,
                SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'IN_PROGRESS' THEN 1 ELSE 0 END) as in_progress,
                SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed,
                AVG(CASE WHEN status = 'COMPLETED' THEN priority END) as avg_priority
            FROM call_queue
            WHERE created_at >= CURRENT_DATE
        """
        results = execute_query(query)

        if results:
            data = results[0]

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Total Queue", f"{data['total_queue']:,}")
            with col2:
                st.metric("Pending", f"{data['pending'] or 0:,}")
            with col3:
                st.metric("In Progress", f"{data['in_progress'] or 0:,}")
            with col4:
                st.metric("Completed", f"{data['completed'] or 0:,}")

    except Exception as e:
        st.error(f"Error loading queue metrics: {e}")


def show_queue_by_channel():
    """Display queue breakdown by channel."""
    st.subheader("Queue by Channel")

    try:
        query = """
            SELECT
                channel,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed
            FROM call_queue
            WHERE created_at >= CURRENT_DATE
            GROUP BY channel
            ORDER BY total DESC
        """
        results = execute_query(query)

        if results:
            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.bar_chart(df.set_index('channel')['total'])
        else:
            st.info("No queue data available")

    except Exception as e:
        st.error(f"Error loading queue by channel: {e}")


def show_queue_by_priority():
    """Display queue breakdown by priority."""
    st.subheader("Queue by Priority")

    try:
        query = """
            SELECT
                priority,
                COUNT(*) as count,
                AVG(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completion_rate
            FROM call_queue
            WHERE created_at >= CURRENT_DATE
            GROUP BY priority
            ORDER BY priority DESC
        """
        results = execute_query(query)

        if results:
            df = pd.DataFrame(results)
            df['completion_rate'] = (df['completion_rate'] * 100).round(2)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No priority data available")

    except Exception as e:
        st.error(f"Error loading queue by priority: {e}")


def show_agent_productivity():
    """Display agent productivity today."""
    st.subheader("Agent Productivity (Today)")

    try:
        query = """
            SELECT
                fc.agent_id,
                da.name as agent_name,
                COUNT(*) as calls_made,
                SUM(CASE WHEN fc.outcome = 'CONNECTED' THEN 1 ELSE 0 END) as connected,
                SUM(CASE WHEN fc.disposition IN ('PTP', 'PAID_CLAIM') THEN 1 ELSE 0 END) as productive
            FROM fct_calls fc
            JOIN dim_agent da ON fc.agent_id = da.agent_id
            WHERE fc.call_date = CURRENT_DATE
              AND da.role IN ('TELECALLER', 'TL')
            GROUP BY fc.agent_id, da.name
            ORDER BY calls_made DESC
            LIMIT 20
        """
        results = execute_query(query)

        if results:
            df = pd.DataFrame(results)
            df['connect_rate'] = ((df['connected'] / df['calls_made']) * 100).round(2)
            df['productive_rate'] = ((df['productive'] / df['calls_made']) * 100).round(2)

            st.dataframe(
                df[['agent_name', 'calls_made', 'connected', 'productive', 'connect_rate', 'productive_rate']],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No agent productivity data available")

    except Exception as e:
        st.error(f"Error loading agent productivity: {e}")


def show_disposition_summary():
    """Display disposition summary."""
    st.subheader("Disposition Summary (Today)")

    try:
        query = """
            SELECT
                disposition,
                COUNT(*) as count
            FROM fct_calls
            WHERE call_date = CURRENT_DATE
              AND disposition IS NOT NULL
            GROUP BY disposition
            ORDER BY count DESC
            LIMIT 10
        """
        results = execute_query(query)

        if results:
            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No disposition data available")

    except Exception as e:
        st.error(f"Error loading disposition summary: {e}")
