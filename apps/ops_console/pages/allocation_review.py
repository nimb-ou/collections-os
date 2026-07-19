"""
Allocation Review Page
Capacity heatmap, allocation overrides, zone distribution
"""

import streamlit as st
import pandas as pd
from datetime import date

from database import execute_query, execute_mutation
from auth import require_permission, get_current_user


@require_permission("allocation_review")
def render():
    """Render Allocation Review page."""
    st.title("🗺️ Allocation Review")
    st.markdown(f"**Date:** {date.today().strftime('%Y-%m-%d')}")
    st.markdown("---")

    # Tabs
    tab1, tab2 = st.tabs(["Allocation Summary", "Manual Overrides"])

    with tab1:
        show_allocation_summary()

    with tab2:
        show_allocation_overrides()


def show_allocation_summary():
    """Display allocation summary by agent/zone."""
    st.subheader("Allocation Summary (Today)")

    try:
        query = """
            SELECT
                mad.owner_agent_id as agent_id,
                da.name as agent_name,
                da.role,
                dg.zone,
                COUNT(DISTINCT mad.account_id) as allocated_accounts,
                SUM(mad.overdue_amt) as total_overdue,
                AVG(mad.bounce_p) as avg_risk_score
            FROM mart_account_daily mad
            JOIN dim_agent da ON mad.owner_agent_id = da.agent_id
            LEFT JOIN dim_account dac ON mad.account_id = dac.account_id
            LEFT JOIN dim_geo dg ON dac.geo_id = dg.geo_id
            WHERE mad.date = CURRENT_DATE
              AND mad.owner_agent_id IS NOT NULL
            GROUP BY mad.owner_agent_id, da.name, da.role, dg.zone
            ORDER BY allocated_accounts DESC
            LIMIT 100
        """
        results = execute_query(query)

        if results:
            df = pd.DataFrame(results)
            df['total_overdue_cr'] = (df['total_overdue'] / 10000000).round(2)
            df['avg_risk_score'] = (df['avg_risk_score'] * 100).round(2)

            # Summary metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Agents", len(df['agent_id'].unique()))
            with col2:
                st.metric("Total Allocated", f"{df['allocated_accounts'].sum():,}")
            with col3:
                st.metric("Total Overdue", f"₹{df['total_overdue_cr'].sum():.2f}Cr")

            # Filter by role
            role_filter = st.multiselect(
                "Filter by Role",
                options=df['role'].unique().tolist(),
                default=df['role'].unique().tolist()
            )

            filtered_df = df[df['role'].isin(role_filter)]

            st.dataframe(
                filtered_df[['agent_name', 'role', 'zone', 'allocated_accounts', 'total_overdue_cr', 'avg_risk_score']],
                use_container_width=True,
                hide_index=True,
            )

            # Capacity heatmap
            st.markdown("---")
            st.subheader("Capacity Heatmap")

            capacity_df = filtered_df.groupby('role').agg({
                'allocated_accounts': 'sum',
                'agent_id': 'nunique'
            }).reset_index()
            capacity_df.columns = ['Role', 'Total Accounts', 'Agent Count']
            capacity_df['Avg per Agent'] = (capacity_df['Total Accounts'] / capacity_df['Agent Count']).round(0)

            st.dataframe(capacity_df, use_container_width=True, hide_index=True)

        else:
            st.info("No allocation data available for today")

    except Exception as e:
        st.error(f"Error loading allocation summary: {e}")


def show_allocation_overrides():
    """Show manual allocation override interface."""
    st.subheader("Manual Allocation Override")

    st.info("""
    Use this interface to manually reassign accounts between agents.
    Overrides will be logged with reason and created_by for audit trail.
    """)

    with st.form("allocation_override_form"):
        col1, col2 = st.columns(2)

        with col1:
            account_id = st.text_input("Account ID*", help="Account to reassign")

            # Load agent list
            try:
                agent_query = "SELECT agent_id, name, role FROM dim_agent WHERE active = true ORDER BY name"
                agents = execute_query(agent_query)
                agent_options = {f"{a['name']} ({a['role']})": a['agent_id'] for a in agents}

                from_agent = st.selectbox(
                    "From Agent",
                    options=list(agent_options.keys()),
                    help="Current owner (optional)"
                )

                to_agent = st.selectbox(
                    "To Agent*",
                    options=list(agent_options.keys()),
                    help="New owner"
                )

            except Exception as e:
                st.error(f"Error loading agents: {e}")
                agent_options = {}
                from_agent = None
                to_agent = None

        with col2:
            reason = st.text_area(
                "Reason*",
                help="Why is this override needed?",
                placeholder="e.g., Language match, customer escalation, capacity rebalance"
            )

            override_type = st.selectbox(
                "Override Type",
                options=["TEMPORARY", "PERMANENT"],
                help="Temporary overrides may be reverted during next allocation run"
            )

        submitted = st.form_submit_button("Submit Override", use_container_width=True)

        if submitted:
            if not account_id or not to_agent or not reason:
                st.error("Please fill all required fields")
            elif account_id and to_agent and reason and agent_options:
                to_agent_id = agent_options[to_agent]
                from_agent_id = agent_options.get(from_agent) if from_agent else None

                create_allocation_override(
                    account_id, from_agent_id, to_agent_id, reason, override_type
                )

    # Show recent overrides
    st.markdown("---")
    show_recent_overrides()


def create_allocation_override(account_id: str, from_agent_id: str, to_agent_id: str,
                               reason: str, override_type: str):
    """
    Create allocation override.

    Args:
        account_id: Account identifier
        from_agent_id: Current owner
        to_agent_id: New owner
        reason: Override reason
        override_type: Override type
    """
    try:
        user = get_current_user()

        # Update owner in mart_account_daily
        update_query = """
            UPDATE mart_account_daily
            SET owner_agent_id = %s,
                allocation_reason = %s
            WHERE account_id = %s
              AND date = CURRENT_DATE
        """
        execute_mutation(update_query, (to_agent_id, f"MANUAL_OVERRIDE: {reason}", account_id))

        # Log the override
        log_query = """
            INSERT INTO audit_log (
                user_id, action, entity_type, entity_id, details
            ) VALUES (
                %s, 'ALLOCATION_OVERRIDE', 'account', %s, %s
            )
        """
        details = f"From {from_agent_id} to {to_agent_id}: {reason} ({override_type})"
        execute_mutation(log_query, (user['user_id'], account_id, details))

        st.success(f"Account {account_id} reassigned to agent {to_agent_id}")
        st.rerun()

    except Exception as e:
        st.error(f"Error creating override: {e}")


def show_recent_overrides():
    """Display recent allocation overrides."""
    st.subheader("Recent Overrides (Last 24h)")

    try:
        query = """
            SELECT
                al.created_at,
                al.user_id,
                u.username,
                al.entity_id as account_id,
                al.details
            FROM audit_log al
            LEFT JOIN users u ON al.user_id = u.user_id
            WHERE al.action = 'ALLOCATION_OVERRIDE'
              AND al.created_at >= NOW() - INTERVAL '24 hours'
            ORDER BY al.created_at DESC
            LIMIT 50
        """
        results = execute_query(query)

        if results:
            df = pd.DataFrame(results)
            df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M')

            st.dataframe(
                df[['created_at', 'username', 'account_id', 'details']],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No recent overrides")

    except Exception as e:
        st.error(f"Error loading recent overrides: {e}")
