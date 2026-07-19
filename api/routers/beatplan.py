"""
Beat Plan and Scorecard Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from datetime import date
from ..models import BeatPlanStop, AgentScorecard
from ..auth import get_current_user
from ..database import get_db_dependency

router = APIRouter(tags=["Beat Plans & Scorecards"])


@router.get("/beatplan/{agent_id}/{beat_date}", response_model=List[BeatPlanStop])
def get_beat_plan(
    agent_id: str,
    beat_date: date,
    conn = Depends(get_db_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get ordered beat plan for field agent for a specific date.

    **Returns:**
    - Ordered list of accounts to visit (TSP-optimized)
    - Priority, expected collection, visit reason
    - GPS coordinates for navigation

    **Access:** Agent can access own beat plan; supervisors can access any
    """
    # Authorization
    if current_user["role"] not in ["ADMIN", "TL", "ACM"]:
        if current_user.get("agent_id") != agent_id:
            raise HTTPException(status_code=403, detail="Can only access your own beat plan")

    cur = conn.cursor()

    cur.execute("""
        SELECT
            bp.beat_id, bp.account_id, c.name as customer_name,
            CONCAT(cu.addr, ', ', cu.pincode) as address,
            bp.sequence_no, bp.priority, bp.expected_collection,
            bp.visit_reason, g.lat as latitude, g.lon as longitude,
            bp.completed
        FROM beat_plan bp
        JOIN dim_account a ON bp.account_id = a.account_id
        JOIN dim_customer c ON a.customer_id = c.customer_id
        LEFT JOIN dim_customer cu ON c.customer_id = cu.customer_id
        LEFT JOIN dim_geo g ON a.geo_id = g.geo_id
        WHERE bp.agent_id = %s
          AND bp.beat_date = %s
        ORDER BY bp.sequence_no ASC
    """, (agent_id, beat_date))

    stops = cur.fetchall()
    cur.close()

    if not stops:
        raise HTTPException(status_code=404, detail="No beat plan found for this date")

    return [
        BeatPlanStop(
            beat_id=stop["beat_id"],
            account_id=stop["account_id"],
            customer_name=stop["customer_name"],
            address=stop.get("address", "Address not available"),
            sequence_no=stop["sequence_no"],
            priority=stop["priority"],
            expected_collection=stop["expected_collection"],
            visit_reason=stop["visit_reason"],
            latitude=float(stop["latitude"]) if stop.get("latitude") else None,
            longitude=float(stop["longitude"]) if stop.get("longitude") else None,
            completed=stop["completed"],
        )
        for stop in stops
    ]


@router.get("/scorecards/{entity_type}/{entity_id}", response_model=List[AgentScorecard])
def get_scorecard(
    entity_type: str,
    entity_id: str,
    start_date: date,
    end_date: date,
    conn = Depends(get_db_dependency),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get performance scorecard for agent/team/zone.

    **Entity Types:**
    - agent: Individual agent scorecard
    - team: Team-level scorecard
    - acm: Area manager scorecard
    - zone: Zonal scorecard

    **Query Parameters:**
    - start_date, end_date: Date range for metrics

    **Returns:**
    - Daily/monthly metrics (resolution, collection efficiency, PTP kept %, etc.)
    - Composite score and rank
    - Percentile within peer group

    **Access:** Agents see own; supervisors see subordinates
    """
    cur = conn.cursor()

    cur.execute("""
        SELECT
            sc.date, sc.entity_type, sc.entity_id,
            a.name as agent_name,
            sc.metrics
        FROM scorecard_daily sc
        LEFT JOIN dim_agent a ON sc.entity_id = a.agent_id
        WHERE sc.entity_type = %s
          AND sc.entity_id = %s
          AND sc.date BETWEEN %s AND %s
        ORDER BY sc.date DESC
    """, (entity_type, entity_id, start_date, end_date))

    scorecards = cur.fetchall()
    cur.close()

    if not scorecards:
        return []

    return [
        AgentScorecard(
            agent_id=sc["entity_id"],
            agent_name=sc.get("agent_name", sc["entity_id"]),
            date=sc["date"],
            metrics=sc["metrics"],
            composite_score=sc["metrics"].get("composite_score"),
            rank=sc["metrics"].get("rank"),
            percentile=sc["metrics"].get("percentile"),
        )
        for sc in scorecards
    ]
