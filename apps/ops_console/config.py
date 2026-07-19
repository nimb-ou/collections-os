"""
Ops Console Configuration
"""

import os
from typing import Dict, List

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://collectos_user:collectos_dev_password_change_in_production@localhost:5432/collectos"
)

# API endpoint (for future integration)
API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")

# App configuration
APP_TITLE = "CollectOS Ops Console"
APP_ICON = "📊"
LAYOUT = "wide"

# User roles and permissions
ROLES: Dict[str, List[str]] = {
    "ADMIN": ["command_center", "campaign_manager", "queue_monitor", "allocation_review",
              "ptp_book", "payments", "model_health", "user_admin"],
    "STRATEGY": ["command_center", "campaign_manager", "allocation_review", "model_health"],
    "TL": ["command_center", "queue_monitor", "ptp_book"],
    "ACM": ["command_center", "queue_monitor", "allocation_review"],
}

# Page metadata
PAGES: Dict[str, Dict[str, str]] = {
    "command_center": {"title": "Command Center", "icon": "🎯"},
    "campaign_manager": {"title": "Campaign Manager", "icon": "📢"},
    "queue_monitor": {"title": "Queue Monitor", "icon": "📞"},
    "allocation_review": {"title": "Allocation Review", "icon": "🗺️"},
    "ptp_book": {"title": "PTP Book", "icon": "📅"},
    "payments": {"title": "Payments (Dev)", "icon": "💰"},
    "model_health": {"title": "Model Health", "icon": "🔬"},
    "user_admin": {"title": "User Admin", "icon": "👥"},
}

# Chart colors
COLORS = {
    "primary": "#1f77b4",
    "success": "#2ca02c",
    "warning": "#ff7f0e",
    "danger": "#d62728",
    "info": "#17becf",
    "buckets": {
        "X": "#2ca02c",      # Green
        "B1": "#ffbb00",     # Yellow
        "B2": "#ff7f0e",     # Orange
        "B3+": "#d62728",    # Red
    },
    "channels": {
        "BOT": "#1f77b4",
        "TELECALLER": "#ff7f0e",
        "FIELD": "#2ca02c",
    }
}

# Date formats
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Pagination
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500
