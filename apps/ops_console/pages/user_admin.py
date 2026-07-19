"""
User Admin Page
Manage users, roles, and permissions
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from database import execute_query, execute_mutation, execute_insert_returning
from auth import require_permission, get_current_user
from config import ROLES


@require_permission("user_admin")
def render():
    """Render User Admin page."""
    st.title("👥 User Admin")
    st.markdown("---")

    # Tabs
    tab1, tab2 = st.tabs(["User Management", "Create User"])

    with tab1:
        show_user_list()

    with tab2:
        show_create_user_form()


def show_user_list():
    """Display list of users."""
    st.subheader("User Management")

    try:
        query = """
            SELECT
                user_id,
                username,
                email,
                role,
                agent_id,
                active,
                last_login_at,
                created_at
            FROM users
            ORDER BY created_at DESC
        """
        results = execute_query(query)

        if results:
            df = pd.DataFrame(results)
            df['last_login_at'] = pd.to_datetime(df['last_login_at']).dt.strftime('%Y-%m-%d %H:%M')
            df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d')
            df['active'] = df['active'].map({True: '✓', False: '✗'})

            # Summary metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Users", len(df))
            with col2:
                active_count = len([r for r in results if r['active']])
                st.metric("Active Users", active_count)
            with col3:
                role_counts = df['role'].value_counts().to_dict()
                st.metric("Roles", len(role_counts))

            st.markdown("---")

            # Filter by role
            role_filter = st.multiselect(
                "Filter by Role",
                options=df['role'].unique().tolist(),
                default=df['role'].unique().tolist()
            )

            filtered_df = df[df['role'].isin(role_filter)]

            st.dataframe(
                filtered_df[['username', 'email', 'role', 'agent_id', 'active', 'last_login_at', 'created_at']],
                use_container_width=True,
                hide_index=True,
            )

            # User actions
            st.markdown("---")
            st.subheader("User Actions")

            col1, col2 = st.columns(2)

            with col1:
                user_id = st.selectbox(
                    "Select User",
                    options=[row['user_id'] for row in results],
                    format_func=lambda x: next(
                        (row['username'] for row in results if row['user_id'] == x), x
                    ),
                    key="action_user_id"
                )

            with col2:
                action = st.selectbox(
                    "Action",
                    options=["Activate", "Deactivate", "Reset Password", "Delete"],
                    key="user_action"
                )

            if st.button("Execute Action", key="execute_user_action"):
                execute_user_action(user_id, action)

        else:
            st.info("No users found")

    except Exception as e:
        st.error(f"Error loading users: {e}")


def show_create_user_form():
    """Display form to create new user."""
    st.subheader("Create New User")

    with st.form("create_user_form"):
        col1, col2 = st.columns(2)

        with col1:
            username = st.text_input(
                "Username*",
                help="Unique username for login",
                max_chars=100
            )

            email = st.text_input(
                "Email*",
                help="User's email address"
            )

            role = st.selectbox(
                "Role*",
                options=list(ROLES.keys()),
                help="User role determines page access"
            )

        with col2:
            password = st.text_input(
                "Password*",
                type="password",
                help="Initial password (user should change)"
            )

            confirm_password = st.text_input(
                "Confirm Password*",
                type="password"
            )

            # Agent ID (optional, only for AGENT/TL/ACM roles)
            agent_id = st.text_input(
                "Agent ID",
                help="Required for AGENT, TL, ACM roles",
                max_chars=20
            )

        # Show role permissions
        st.markdown("**Role Permissions:**")
        if role:
            allowed_pages = ROLES.get(role, [])
            st.info(f"Pages: {', '.join(allowed_pages)}")

        submitted = st.form_submit_button("Create User", use_container_width=True)

        if submitted:
            if not username or not email or not password or not role:
                st.error("Please fill all required fields")
            elif password != confirm_password:
                st.error("Passwords do not match")
            elif role in ["AGENT", "TL", "ACM"] and not agent_id:
                st.error(f"Agent ID required for role {role}")
            else:
                create_user(username, email, password, role, agent_id)


def create_user(username: str, email: str, password: str, role: str, agent_id: str = None):
    """
    Create a new user.

    Args:
        username: Username
        email: Email address
        password: Password
        role: User role
        agent_id: Agent ID (optional)
    """
    try:
        current_user = get_current_user()

        # For dev, use simple hash (production should use bcrypt)
        import hashlib
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        query = """
            INSERT INTO users (
                username, email, password_hash, role, agent_id, active, created_by
            ) VALUES (
                %s, %s, %s, %s, %s, true, %s
            ) RETURNING user_id
        """

        result = execute_insert_returning(
            query,
            (username, email, password_hash, role, agent_id, current_user['user_id'])
        )

        if result:
            st.success(f"✅ User created successfully! User ID: {result['user_id']}")
            st.info(f"""
            **Login Credentials:**
            - Username: {username}
            - Password: {password}
            - Role: {role}

            User can now login to the Ops Console.
            """)
            st.rerun()
        else:
            st.error("Failed to create user")

    except Exception as e:
        st.error(f"Error creating user: {e}")


def execute_user_action(user_id: str, action: str):
    """
    Execute action on user account.

    Args:
        user_id: User identifier
        action: Action to execute
    """
    try:
        if action == "Delete":
            query = "DELETE FROM users WHERE user_id = %s"
            execute_mutation(query, (user_id,))
            st.success(f"User {user_id} deleted")

        elif action == "Activate":
            query = "UPDATE users SET active = true WHERE user_id = %s"
            execute_mutation(query, (user_id,))
            st.success(f"User {user_id} activated")

        elif action == "Deactivate":
            query = "UPDATE users SET active = false WHERE user_id = %s"
            execute_mutation(query, (user_id,))
            st.success(f"User {user_id} deactivated")

        elif action == "Reset Password":
            # Generate random password
            import secrets
            import string
            new_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))

            import hashlib
            password_hash = hashlib.sha256(new_password.encode()).hexdigest()

            query = "UPDATE users SET password_hash = %s WHERE user_id = %s"
            execute_mutation(query, (password_hash, user_id))

            st.success(f"Password reset for user {user_id}")
            st.info(f"**New temporary password:** {new_password}")

        st.rerun()

    except Exception as e:
        st.error(f"Error executing action: {e}")
