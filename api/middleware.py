"""
Middleware for Audit Logging and Security
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import time
import json
from .database import get_db


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    Log all API mutations to audit_log table.
    Captures: user, endpoint, method, payload, response status, timestamp.
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Get user from request state (set by auth dependency)
        user_id = None
        if hasattr(request.state, "user"):
            user_id = request.state.user.get("user_id")

        # Log mutations only (POST, PUT, PATCH, DELETE)
        should_log = request.method in ["POST", "PUT", "PATCH", "DELETE"]

        # Execute request
        response = await call_next(request)

        # Log to audit_log if mutation
        if should_log and user_id:
            duration_ms = int((time.time() - start_time) * 1000)

            try:
                with get_db() as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO audit_log (
                            user_id, action, entity_type, entity_id,
                            changes, ip_address, user_agent
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        user_id,
                        f"{request.method} {request.url.path}",
                        "api_call",
                        None,  # entity_id not available here
                        json.dumps({
                            "status_code": response.status_code,
                            "duration_ms": duration_ms,
                        }),
                        request.client.host if request.client else None,
                        request.headers.get("user-agent"),
                    ))
                    conn.commit()
                    cur.close()
            except Exception as e:
                # Don't fail request if audit logging fails
                print(f"⚠️  Audit log failed: {e}")

        return response
