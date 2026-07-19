"""
CollectOS Ops Console - Main Application
Streamlit-based operations console for collections management

Usage:
    streamlit run app.py
"""

import streamlit as st
from datetime import date

from config import APP_TITLE, APP_ICON, LAYOUT, PAGES, ROLES
from auth import show_login_page, is_authenticated, logout, get_current_user, get_current_role, has_permission

# Import pages
from pages import (
    command_center,
    campaign_manager,
    queue_monitor,
    allocation_review,
    ptp_book,
    payments,
    model_health,
    user_admin,
)


def main():
    """Main application entry point."""
    # Page configuration
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=APP_ICON,
        layout=LAYOUT,
        initial_sidebar_state="expanded",
    )

    # Check authentication
    if not is_authenticated():
        show_login_page()
        return

    # Show sidebar navigation
    show_sidebar()

    # Get selected page from session state
    page = st.session_state.get("current_page", "command_center")

    # Render selected page
    render_page(page)


def show_sidebar():
    """Display sidebar with navigation and user info."""
    with st.sidebar:
        st.title(f"{APP_ICON} {APP_TITLE}")
        st.markdown("---")

        # User info
        user = get_current_user()
        role = get_current_role()

        st.markdown(f"**User:** {user['username']}")
        st.markdown(f"**Role:** {role}")
        if user.get("agent_id"):
            st.markdown(f"**Agent ID:** {user['agent_id']}")

        st.markdown("---")

        # Navigation
        st.subheader("Navigation")

        # Get allowed pages for user's role
        allowed_pages = ROLES.get(role, [])

        for page_key, page_meta in PAGES.items():
            if page_key in allowed_pages:
                if st.button(
                    f"{page_meta['icon']} {page_meta['title']}",
                    key=f"nav_{page_key}",
                    use_container_width=True,
                ):
                    st.session_state.current_page = page_key
                    st.rerun()

        st.markdown("---")

        # Logout button
        if st.button("🚪 Logout", use_container_width=True):
            logout()

        st.markdown("---")

        # Footer
        st.caption(f"📅 Today: {date.today().strftime('%Y-%m-%d')}")
        st.caption("CollectOS v1.0")


def render_page(page: str):
    """
    Render the selected page.

    Args:
        page: Page identifier
    """
    # Check permission
    if not has_permission(page):
        st.error(f"Access denied. You don't have permission to access this page.")
        return

    # Page routing
    page_functions = {
        "command_center": command_center.render,
        "campaign_manager": campaign_manager.render,
        "queue_monitor": queue_monitor.render,
        "allocation_review": allocation_review.render,
        "ptp_book": ptp_book.render,
        "payments": payments.render,
        "model_health": model_health.render,
        "user_admin": user_admin.render,
    }

    # Render page
    page_func = page_functions.get(page)
    if page_func:
        try:
            page_func()
        except Exception as e:
            st.error(f"Error rendering page: {e}")
            st.exception(e)
    else:
        st.error(f"Page '{page}' not found")


if __name__ == "__main__":
    main()
