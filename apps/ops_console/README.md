# CollectOS Ops Console

Streamlit-based operations console for collections management.

## Overview

The Ops Console provides a web interface for:
- Portfolio monitoring and KPI tracking
- Campaign management and queue monitoring
- Allocation review and manual overrides
- PTP (Promise-to-Pay) book management
- Development payment entry
- ML model health monitoring
- User administration

## Features

### Pages

1. **Command Center** - Real-time portfolio dashboard
   - Today's demand and overdue metrics
   - Queue burn-down tracking
   - Resolution progress vs target
   - Treatment channel split (Bot/Telecaller/Field)

2. **Campaign Manager** - Create and manage calling campaigns
   - Active campaign monitoring
   - Campaign creation with filters
   - Control group configuration
   - Cadence editor
   - Pause/resume/complete actions

3. **Queue Monitor** - Real-time queue status
   - Queue metrics by channel and priority
   - Agent productivity tracking
   - Disposition summary
   - SLA monitoring

4. **Allocation Review** - Account allocation management
   - Allocation summary by agent/zone
   - Capacity heatmap
   - Manual allocation overrides with reason tracking
   - Recent override audit trail

5. **PTP Book** - Promise-to-Pay tracking
   - PTPs due today
   - PTP aging analysis
   - Broken PTP tracking
   - Kept rate metrics

6. **Payments (Dev)** - Manual payment entry for testing
   - Mark accounts as paid
   - Payment history
   - Development/testing workflow

7. **Model Health** - ML model monitoring
   - Model performance metrics (AUC, Precision, Recall)
   - Version history and registry
   - Feature importance (SHAP)
   - Score distribution and PSI monitoring

8. **User Admin** - User management (Admin only)
   - User creation and role assignment
   - Activate/deactivate users
   - Password reset
   - Role-based access control

## Installation

### Prerequisites

- Python 3.12+
- PostgreSQL database running (via `make up`)
- Database migrations applied (Session 1)

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Or install individually
pip install streamlit psycopg2-binary pandas pyyaml
```

## Usage

### Running the Console

```bash
# From ops_console directory
cd apps/ops_console
streamlit run app.py

# Or from project root
streamlit run apps/ops_console/app.py
```

The console will be available at: http://localhost:8501

### Login

**Development Credentials:**

The console uses simple authentication for development. Use any username from the `users` table:

- `admin` / any password (ADMIN role - full access)
- `strategy` / any password (STRATEGY role)
- `tl_north` / any password (TL role)

Password validation is disabled for development. In production, passwords would be verified against bcrypt hashes.

### Role-Based Access

| Role | Pages Access |
|------|--------------|
| ADMIN | All pages (full access) |
| STRATEGY | Command Center, Campaign Manager, Allocation Review, Model Health |
| TL | Command Center, Queue Monitor, PTP Book |
| ACM | Command Center, Queue Monitor, Allocation Review |

## Architecture

### File Structure

```
ops_console/
├── app.py                 # Main Streamlit application
├── auth.py                # Authentication and authorization
├── config.py              # Configuration and constants
├── database.py            # Database connection utilities
├── requirements.txt       # Python dependencies
├── README.md             # This file
└── pages/                # Page modules
    ├── __init__.py
    ├── command_center.py
    ├── campaign_manager.py
    ├── queue_monitor.py
    ├── allocation_review.py
    ├── ptp_book.py
    ├── payments.py
    ├── model_health.py
    └── user_admin.py
```

### Database Connection

The console connects to PostgreSQL using environment variable:

```bash
export DATABASE_URL="postgresql://collectos_user:password@localhost:5432/collectos"
```

Default connection is configured in `config.py` for development.

### Session Management

- Uses Streamlit session state for authentication
- Session persists until logout or browser close
- No server-side session storage (stateless)

### Data Caching

- Query results are cached using `@st.cache_data` with 60-second TTL
- Improves performance for frequently accessed data
- Cache automatically clears on data mutations

## Configuration

### Environment Variables

- `DATABASE_URL` - PostgreSQL connection string (default: localhost)
- `API_URL` - FastAPI endpoint (for future integration)

### Config File

Edit `config.py` to customize:
- Role permissions (ROLES dict)
- Page metadata
- Chart colors
- Date formats
- Pagination settings

## Security

### Development Mode

The current implementation uses simplified security for development:
- Simple password hashing (SHA-256)
- No session expiration
- Minimal input validation

### Production Recommendations

For production deployment:
1. Use bcrypt for password hashing (via passlib)
2. Implement session timeout
3. Add CSRF protection
4. Enable HTTPS/TLS
5. Implement rate limiting
6. Add comprehensive input validation
7. Enable audit logging for all actions
8. Implement password policies (complexity, expiration)
9. Add 2FA/MFA support
10. Use environment-based secrets (not hardcoded)

## Troubleshooting

### Database Connection Failed

**Issue:** Cannot connect to PostgreSQL

**Solution:**
1. Ensure PostgreSQL is running: `docker ps`
2. Start database: `make up`
3. Check DATABASE_URL environment variable
4. Verify credentials in `.env` file

### Module Import Errors

**Issue:** `ModuleNotFoundError: No module named 'streamlit'`

**Solution:**
```bash
pip install -r requirements.txt
```

### Login Not Working

**Issue:** Cannot login with any credentials

**Solution:**
1. Check if `users` table exists: `psql -d collectos -c "\dt users"`
2. Ensure migrations are applied: `make migrate` (if available)
3. Seed test users: `python -m api.seed_users`
4. For dev, password validation is disabled - any password works

### Page Not Loading

**Issue:** Page shows error or blank screen

**Solution:**
1. Check browser console for JavaScript errors
2. Check terminal for Python exceptions
3. Verify database queries in page module
4. Ensure user has permission for the page

### Data Not Showing

**Issue:** Dashboard shows "No data available"

**Solution:**
1. Run daily pipeline: `make daily`
2. Check if synthetic data exists: `psql -d collectos -c "SELECT COUNT(*) FROM mart_account_daily"`
3. Generate history: `python -m synthgen.generate_history`
4. Verify date filters in queries

## Development

### Adding a New Page

1. Create page module in `pages/` directory:
   ```python
   # pages/my_new_page.py
   import streamlit as st
   from auth import require_permission

   @require_permission("my_new_page")
   def render():
       st.title("My New Page")
       # Page implementation
   ```

2. Add page to `pages/__init__.py`:
   ```python
   from . import my_new_page
   __all__ = [..., "my_new_page"]
   ```

3. Add page config to `config.py`:
   ```python
   PAGES = {
       ...,
       "my_new_page": {"title": "My New Page", "icon": "🆕"},
   }

   ROLES = {
       "ADMIN": [..., "my_new_page"],
   }
   ```

4. Add route in `app.py`:
   ```python
   page_functions = {
       ...,
       "my_new_page": my_new_page.render,
   }
   ```

### Database Queries

Use the database utilities in `database.py`:

```python
from database import execute_query, execute_mutation

# SELECT query (cached)
results = execute_query("SELECT * FROM users WHERE role = %s", ("ADMIN",))

# INSERT/UPDATE/DELETE (not cached)
execute_mutation("UPDATE users SET active = false WHERE user_id = %s", (user_id,))
```

### Custom Visualizations

Streamlit supports:
- `st.line_chart()` - Time series
- `st.bar_chart()` - Bar charts
- `st.dataframe()` - Tables
- `st.metric()` - KPI cards

For advanced charts, use Plotly or Altair.

## Future Enhancements

Planned features for future sessions:
- [ ] Integration with FastAPI backend (Session 8 API)
- [ ] Real-time queue updates (WebSocket)
- [ ] Advanced filtering and search
- [ ] Export to Excel/CSV
- [ ] Scheduled reports
- [ ] Mobile-responsive layout
- [ ] Dark mode
- [ ] Custom dashboard builder
- [ ] Notification system
- [ ] Advanced analytics

## Notes

- This console is part of Session 10 (S10) of the CollectOS build
- Designed for internal operations team use (Strategy, TL, ACM, Admin)
- Complements the Field PWA (Session 13) for field agents
- Works with data from dbt marts (Session 4)
- Displays predictions from ML models (Session 5)

## Support

For issues or questions:
1. Check this README
2. Review page-specific documentation in module docstrings
3. Check STATE.md for known issues
4. Review database schema in migrations
