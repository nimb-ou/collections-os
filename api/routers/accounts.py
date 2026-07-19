"""
Account Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from ..models import AccountCard, AccountHistory
from ..auth import get_current_user
from ..database import get_db_dependency

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.get("/{account_id}", response_model=AccountCard)
def get_account_card(
    account_id: str,
    conn = Depends(get_db_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get account insight card with collection reasons.

    **Returns:**
    - Account details (bucket, DPD, overdue amount, POS)
    - Model scores (bounce_p, selfcure_p)
    - Treatment assignment
    - Owner agent
    - Top 3 SHAP reasons for risk
    - Contact information

    **Access:** All authenticated users
    """
    cur = conn.cursor()

    # Fetch account details from latest mart_account_daily
    cur.execute("""
        SELECT
            m.account_id, a.customer_id, c.name as customer_name,
            a.product_type, m.bucket, m.dpd, m.overdue_amt,
            m.pos, a.emi_amt,
            m.bounce_p, m.selfcure_p, m.treatment_code,
            m.owner_agent_id, m.last_contact_date
        FROM mart_account_daily m
        JOIN dim_account a ON m.account_id = a.account_id
        LEFT JOIN dim_customer c ON a.customer_id = c.customer_id
        WHERE m.account_id = %s
          AND m.date = (SELECT MAX(date) FROM mart_account_daily)
        LIMIT 1
    """, (account_id,))

    account = cur.fetchone()

    if account is None:
        cur.close()
        raise HTTPException(status_code=404, detail="Account not found")

    # Fetch contact numbers
    cur.execute("""
        SELECT phone
        FROM dim_customer_contacts
        WHERE customer_id = %s AND is_primary = true
        ORDER BY phone
        LIMIT 3
    """, (account["customer_id"],))

    phones = [row["phone"] for row in cur.fetchall()]

    # Fetch address
    cur.execute("""
        SELECT addr, pincode
        FROM dim_customer
        WHERE customer_id = %s
    """, (account["customer_id"],))

    address_row = cur.fetchone()
    address = f"{address_row['addr']}, {address_row['pincode']}" if address_row else None

    cur.close()

    # TODO: Fetch SHAP top reasons (requires model artifact loading)
    top_reasons = [
        {"feature": "overdue_amt", "value": float(account["overdue_amt"]), "impact": "high"},
        {"feature": "dpd", "value": account["dpd"], "impact": "medium"},
        {"feature": "bounce_p", "value": account["bounce_p"] or 0, "impact": "medium"},
    ]

    return AccountCard(
        account_id=account["account_id"],
        customer_id=account["customer_id"],
        customer_name=account.get("customer_name"),
        product_type=account["product_type"],
        bucket=account["bucket"],
        dpd=account["dpd"],
        overdue_amt=account["overdue_amt"],
        pos=account["pos"],
        emi_amt=account["emi_amt"],
        bounce_p=account.get("bounce_p"),
        selfcure_p=account.get("selfcure_p"),
        treatment_code=account.get("treatment_code"),
        owner_agent_id=account.get("owner_agent_id"),
        last_contact_date=account.get("last_contact_date"),
        top_reasons=top_reasons,
        phone_numbers=phones,
        address=address,
    )


@router.get("/{account_id}/history", response_model=AccountHistory)
def get_account_history(
    account_id: str,
    conn = Depends(get_db_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get account historical events (last 90 days).

    **Returns:**
    - Presentations (EMI attempts)
    - Payments
    - Call history
    - Field visits
    - PTPs

    **Access:** All authenticated users
    """
    cur = conn.cursor()

    # Presentations
    cur.execute("""
        SELECT
            present_date, amount, status, bounce_reason
        FROM fct_presentations
        WHERE account_id = %s
          AND present_date >= CURRENT_DATE - INTERVAL '90 days'
        ORDER BY present_date DESC
        LIMIT 20
    """, (account_id,))
    presentations = [dict(row) for row in cur.fetchall()]

    # Payments
    cur.execute("""
        SELECT
            pay_date, amount, mode, alloc_to_inst
        FROM fct_payments
        WHERE account_id = %s
          AND pay_date >= CURRENT_DATE - INTERVAL '90 days'
        ORDER BY pay_date DESC
        LIMIT 20
    """, (account_id,))
    payments = [dict(row) for row in cur.fetchall()]

    # Calls
    cur.execute("""
        SELECT
            call_date, call_time, channel, outcome, disposition
        FROM fct_calls
        WHERE account_id = %s
          AND call_date >= CURRENT_DATE - INTERVAL '90 days'
        ORDER BY call_date DESC, call_time DESC
        LIMIT 30
    """, (account_id,))
    calls = [dict(row) for row in cur.fetchall()]

    # Visits
    cur.execute("""
        SELECT
            visit_date, visit_time, outcome, collected_amt, disposition
        FROM fct_visits
        WHERE account_id = %s
          AND visit_date >= CURRENT_DATE - INTERVAL '90 days'
        ORDER BY visit_date DESC, visit_time DESC
        LIMIT 20
    """, (account_id,))
    visits = [dict(row) for row in cur.fetchall()]

    # PTPs
    cur.execute("""
        SELECT
            ptp_date, promise_date, promise_amt, status, made_by_channel
        FROM fct_ptp
        WHERE account_id = %s
          AND ptp_date >= CURRENT_DATE - INTERVAL '90 days'
        ORDER BY ptp_date DESC
        LIMIT 20
    """, (account_id,))
    ptps = [dict(row) for row in cur.fetchall()]

    cur.close()

    return AccountHistory(
        presentations=presentations,
        payments=payments,
        calls=calls,
        visits=visits,
        ptps=ptps,
    )
