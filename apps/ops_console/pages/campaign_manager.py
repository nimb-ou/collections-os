"""
Campaign Manager Page
Create, pause, and configure campaigns with cadence and control groups
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
from typing import Optional

from database import execute_query, execute_mutation, execute_insert_returning
from auth import require_permission, get_current_user


@require_permission("campaign_manager")
def render():
    """Render Campaign Manager page."""
    st.title("📢 Campaign Manager")
    st.markdown("---")

    # Tabs for different views
    tab1, tab2 = st.tabs(["Active Campaigns", "Create New Campaign"])

    with tab1:
        show_active_campaigns()

    with tab2:
        show_create_campaign_form()


def show_active_campaigns():
    """Display list of active campaigns."""
    st.subheader("Active Campaigns")

    try:
        query = """
            SELECT
                campaign_id,
                name,
                type,
                channel,
                status,
                control_pct,
                cadence,
                priority,
                start_date,
                end_date,
                created_at
            FROM campaigns
            ORDER BY created_at DESC
            LIMIT 50
        """
        results = execute_query(query)

        if results:
            df = pd.DataFrame(results)

            # Format dates
            df['start_date'] = pd.to_datetime(df['start_date']).dt.date
            df['end_date'] = pd.to_datetime(df['end_date']).dt.date

            # Display table with actions
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
            )

            # Campaign actions
            st.markdown("---")
            st.subheader("Campaign Actions")

            col1, col2 = st.columns(2)

            with col1:
                campaign_id = st.selectbox(
                    "Select Campaign",
                    options=[row['campaign_id'] for row in results],
                    format_func=lambda x: next(
                        (row['name'] for row in results if row['campaign_id'] == x), x
                    ),
                    key="action_campaign_id"
                )

            with col2:
                action = st.selectbox(
                    "Action",
                    options=["Pause", "Resume", "Complete", "Delete"],
                    key="campaign_action"
                )

            if st.button("Execute Action", key="execute_campaign_action"):
                execute_campaign_action(campaign_id, action)

            # Show campaign details
            if campaign_id:
                show_campaign_details(campaign_id)

        else:
            st.info("No campaigns found")

    except Exception as e:
        st.error(f"Error loading campaigns: {e}")


def show_campaign_details(campaign_id: str):
    """
    Display detailed campaign information and metrics.

    Args:
        campaign_id: Campaign identifier
    """
    st.markdown("---")
    st.subheader("Campaign Details")

    try:
        # Get campaign info
        query = """
            SELECT
                c.campaign_id,
                c.name,
                c.type,
                c.channel,
                c.status,
                c.control_pct,
                c.cadence,
                c.priority,
                c.filters,
                c.start_date,
                c.end_date,
                c.created_by,
                COUNT(DISTINCT cq.account_id) as total_accounts,
                SUM(CASE WHEN cq.status = 'COMPLETED' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN cq.status = 'PENDING' THEN 1 ELSE 0 END) as pending
            FROM campaigns c
            LEFT JOIN call_queue cq ON c.campaign_id = cq.campaign_id
            WHERE c.campaign_id = %s
            GROUP BY c.campaign_id, c.name, c.type, c.channel, c.status, c.control_pct,
                     c.cadence, c.priority, c.filters, c.start_date, c.end_date, c.created_by
        """
        results = execute_query(query, (campaign_id,))

        if results:
            campaign = results[0]

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Total Accounts", f"{campaign['total_accounts']:,}")
            with col2:
                st.metric("Completed", f"{campaign['completed'] or 0:,}")
            with col3:
                st.metric("Pending", f"{campaign['pending'] or 0:,}")

            # Campaign configuration
            st.markdown("**Configuration:**")
            config_col1, config_col2 = st.columns(2)

            with config_col1:
                st.write(f"**Type:** {campaign['type']}")
                st.write(f"**Channel:** {campaign['channel']}")
                st.write(f"**Status:** {campaign['status']}")
                st.write(f"**Priority:** {campaign['priority']}")

            with config_col2:
                st.write(f"**Control %:** {campaign['control_pct']}%")
                st.write(f"**Cadence:** {campaign['cadence']}")
                st.write(f"**Start:** {campaign['start_date']}")
                st.write(f"**End:** {campaign['end_date']}")

    except Exception as e:
        st.error(f"Error loading campaign details: {e}")


def show_create_campaign_form():
    """Display form to create new campaign."""
    st.subheader("Create New Campaign")

    with st.form("create_campaign_form"):
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input("Campaign Name*", help="Unique campaign identifier")
            type_ = st.selectbox(
                "Campaign Type*",
                options=["PRE_DUE", "POST_DUE", "PTP_REMINDER", "REACTIVATION"],
                help="Type of campaign"
            )
            channel = st.selectbox(
                "Channel*",
                options=["BOT", "TELECALLER", "FIELD", "SMS", "EMAIL"],
                help="Treatment channel"
            )
            priority = st.slider("Priority", min_value=1, max_value=10, value=5,
                               help="1=lowest, 10=highest")

        with col2:
            control_pct = st.slider("Control Group %", min_value=0, max_value=20, value=5,
                                   help="Percentage of accounts held out for impact measurement")
            cadence = st.text_input("Cadence", value="0,1,3,7",
                                   help="Days after start: 0,1,3,7")
            start_date = st.date_input("Start Date", value=date.today())
            end_date = st.date_input("End Date", value=date.today())

        st.markdown("**Filters (YAML format)**")
        filters = st.text_area(
            "Filters",
            value="""buckets: [B1, B2]
dpd_min: 30
dpd_max: 90""",
            height=150,
            help="YAML filters for account selection"
        )

        submitted = st.form_submit_button("Create Campaign", use_container_width=True)

        if submitted:
            if not name or not type_ or not channel:
                st.error("Please fill all required fields")
            else:
                create_campaign(name, type_, channel, priority, control_pct, cadence,
                              start_date, end_date, filters)


def create_campaign(name: str, type_: str, channel: str, priority: int,
                    control_pct: int, cadence: str, start_date: date,
                    end_date: date, filters: str):
    """
    Create a new campaign.

    Args:
        name: Campaign name
        type_: Campaign type
        channel: Treatment channel
        priority: Priority level
        control_pct: Control group percentage
        cadence: Cadence string
        start_date: Start date
        end_date: End date
        filters: YAML filters
    """
    try:
        user = get_current_user()

        query = """
            INSERT INTO campaigns (
                name, type, channel, status, control_pct, cadence,
                priority, filters, start_date, end_date, created_by
            ) VALUES (
                %s, %s, %s, 'DRAFT', %s, %s,
                %s, %s, %s, %s, %s
            ) RETURNING campaign_id
        """

        result = execute_insert_returning(
            query,
            (name, type_, channel, control_pct, cadence, priority,
             filters, start_date, end_date, user['user_id'])
        )

        if result:
            st.success(f"Campaign created successfully! ID: {result['campaign_id']}")
            st.rerun()
        else:
            st.error("Failed to create campaign")

    except Exception as e:
        st.error(f"Error creating campaign: {e}")


def execute_campaign_action(campaign_id: str, action: str):
    """
    Execute action on campaign (pause, resume, complete, delete).

    Args:
        campaign_id: Campaign identifier
        action: Action to execute
    """
    try:
        if action == "Delete":
            query = "DELETE FROM campaigns WHERE campaign_id = %s"
            execute_mutation(query, (campaign_id,))
            st.success(f"Campaign {campaign_id} deleted")
        else:
            status_map = {
                "Pause": "PAUSED",
                "Resume": "ACTIVE",
                "Complete": "COMPLETED"
            }
            new_status = status_map.get(action)

            if new_status:
                query = "UPDATE campaigns SET status = %s WHERE campaign_id = %s"
                execute_mutation(query, (new_status, campaign_id))
                st.success(f"Campaign {campaign_id} {action.lower()}d")

        st.rerun()

    except Exception as e:
        st.error(f"Error executing action: {e}")
