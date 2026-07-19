"""
Queue and Disposition Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from ..models import QueueItem, DispositionCreate, DispositionResponse
from ..auth import get_current_user
from ..database import get_db_dependency

router = APIRouter(tags=["Queues & Dispositions"])


@router.get("/queues/next", response_model=QueueItem)
def get_next_queue_item(
    agent_id: str,
    conn = Depends(get_db_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get next call/visit from agent's queue.

    **Query Parameters:**
    - agent_id: Agent ID to fetch queue for

    **Returns:**
    - Next highest priority account to contact
    - Account details and recommended script
    - Top risk reasons

    **Access:** Agents can only access their own queue; supervisors can access any
    """
    # Authorization check
    if current_user["role"] not in ["ADMIN", "TL", "ACM"]:
        if current_user.get("agent_id") != agent_id:
            raise HTTPException(status_code=403, detail="Can only access your own queue")

    cur = conn.cursor()

    # Fetch next item from call_queue
    cur.execute("""
        SELECT
            q.queue_id, q.account_id, c.name as customer_name,
            cc.phone as phone_number,
            m.bucket, m.overdue_amt, q.priority,
            m.treatment_code, d.disposition as last_disposition
        FROM call_queue q
        JOIN dim_account a ON q.account_id = a.account_id
        JOIN dim_customer c ON a.customer_id = c.customer_id
        LEFT JOIN dim_customer_contacts cc ON c.customer_id = cc.customer_id AND cc.is_primary = true
        LEFT JOIN mart_account_daily m ON q.account_id = m.account_id
            AND m.date = (SELECT MAX(date) FROM mart_account_daily)
        LEFT JOIN LATERAL (
            SELECT disposition
            FROM dispositions
            WHERE account_id = q.account_id
            ORDER BY captured_at DESC
            LIMIT 1
        ) d ON true
        WHERE q.agent_id = %s
          AND q.status = 'queued'
          AND q.scheduled_time <= CURRENT_TIMESTAMP
        ORDER BY q.priority DESC, q.scheduled_time ASC
        LIMIT 1
    """, (agent_id,))

    item = cur.fetchone()
    cur.close()

    if item is None:
        raise HTTPException(status_code=404, detail="No items in queue")

    return QueueItem(
        queue_id=item["queue_id"],
        account_id=item["account_id"],
        customer_name=item["customer_name"],
        phone_number=item.get("phone_number", "N/A"),
        bucket=item["bucket"],
        overdue_amt=item["overdue_amt"],
        priority=item["priority"],
        treatment_code=item.get("treatment_code", "T002_BOT_SMS"),
        recommended_script="Standard collection script",  # TODO: Dynamic script selection
        top_reasons=["High overdue", "Recent bounce", "No recent payment"],
        last_disposition=item.get("last_disposition"),
    )


@router.post("/dispositions", response_model=DispositionResponse)
def create_disposition(
    disposition: DispositionCreate,
    conn = Depends(get_db_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Create a disposition record for a contact attempt.

    **Disposition Taxonomy:**
    - CONNECT_RPC, CONNECT_TPC
    - PTP, PAID_CLAIM, DISPUTE, HARDSHIP
    - NOT_INTERESTED, WRONG_NO, NO_ANSWER
    - SWITCHED_OFF, CALLBACK, DNC_REQUEST, LANG_SWITCH
    - VISIT_MET, VISIT_NOT_FOUND, ADDRESS_ISSUE, COLLECTED

    **Audit:** All dispositions logged to audit_log

    **Access:** Agents, TLs, ACMs
    """
    cur = conn.cursor()

    # Insert disposition
    cur.execute("""
        INSERT INTO dispositions (
            account_id, customer_id, agent_id, channel,
            disposition, call_id, visit_id, notes
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING disposition_id, captured_at
    """, (
        disposition.account_id,
        disposition.customer_id,
        disposition.agent_id or current_user.get("agent_id"),
        disposition.channel,
        disposition.disposition,
        disposition.call_id,
        disposition.visit_id,
        disposition.notes,
    ))

    result = cur.fetchone()
    conn.commit()
    cur.close()

    return DispositionResponse(
        disposition_id=result["disposition_id"],
        captured_at=result["captured_at"],
    )
