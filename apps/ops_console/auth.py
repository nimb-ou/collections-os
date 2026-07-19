"""
Authentication module for Ops Console
Uses Streamlit session state for session management
"""

import streamlit as st
from typing import Optional, Dict, Any
import hashlib

from database import execute_query, execute_mutation
from config import ROLES


def hash_password(password: str) -> str:
    """
    Hash password using SHA-256 (simple version for dev).
    Production should use bcrypt via passlib.

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    return hashlib.sha256(password.encode()).hexdigest()


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate user against database.

    Args:
        username: Username
        password: Plain text password

    Returns:
        User dict if authenticated, None otherwise
    """
    try:
        # For dev, we'll use simple password check
        # In production, this should verify against bcrypt hash from users table
        query = """
            SELECT user_id, username, email, role, agent_id, active
            FROM users
            WHERE username = %s AND active = true
            LIMIT 1
        """
        results = execute_query(query, (username,))

        if not results:
            return None

        user = results[0]

        # TODO: Verify password hash when users table is populated
        # For now, accept any password for development

        # Update last login
        update_query = """
            UPDATE users
            SET last_login_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
        """
        execute_mutation(update_query, (user["user_id"],))

        return user
    except Exception as e:
        st.error(f"Authentication error: {e}")
        return None


def login(username: str, password: str) -> bool:
    """
    Perform login and set session state.

    Args:
        username: Username
        password: Password

    Returns:
        True if login successful
    """
    user = authenticate_user(username, password)
    if user:
        st.session_state.authenticated = True
        st.session_state.user = user
        st.session_state.username = user["username"]
        st.session_state.role = user["role"]
        st.session_state.user_id = user["user_id"]
        st.session_state.agent_id = user.get("agent_id")
        return True
    return False


def logout():
    """Clear session state and logout."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


def is_authenticated() -> bool:
    """Check if user is authenticated."""
    return st.session_state.get("authenticated", False)


def get_current_user() -> Optional[Dict[str, Any]]:
    """Get current authenticated user."""
    return st.session_state.get("user")


def get_current_role() -> Optional[str]:
    """Get current user's role."""
    return st.session_state.get("role")


def has_permission(page_key: str) -> bool:
    """
    Check if current user has permission to access a page.

    Args:
        page_key: Page identifier from config.PAGES

    Returns:
        True if user has permission
    """
    role = get_current_role()
    if not role:
        return False

    allowed_pages = ROLES.get(role, [])
    return page_key in allowed_pages


def require_auth(func):
    """
    Decorator to require authentication for a page function.
    """
    def wrapper(*args, **kwargs):
        if not is_authenticated():
            st.warning("Please login to access this page")
            st.stop()
        return func(*args, **kwargs)
    return wrapper


def require_permission(page_key: str):
    """
    Decorator factory to require specific page permission.

    Args:
        page_key: Page identifier from config.PAGES
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not is_authenticated():
                st.warning("Please login to access this page")
                st.stop()
            if not has_permission(page_key):
                st.error(f"Access denied. Your role ({get_current_role()}) does not have permission to access this page.")
                st.stop()
            return func(*args, **kwargs)
        return wrapper
    return decorator


def show_login_page():
    """Display login page."""
    st.title("🔐 CollectOS Ops Console")
    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.subheader("Login")

        with st.form("login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submit = st.form_submit_button("Login", use_container_width=True)

            if submit:
                if not username or not password:
                    st.error("Please enter both username and password")
                else:
                    if login(username, password):
                        st.success(f"Welcome, {username}!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password")

        st.markdown("---")
        st.info("""
        **Development Credentials:**

        Use any username from the users table. For testing:
        - `admin` / any password (ADMIN role)
        - `strategy` / any password (STRATEGY role)
        - `tl_north` / any password (TL role)

        Note: Password validation is disabled for development.
        """)
