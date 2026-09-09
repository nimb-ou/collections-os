"""
CollectOS FastAPI Application
Main entry point for the API server.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .middleware import AuditLogMiddleware
from .routers import auth, accounts, queues, beatplan, campaigns

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
CollectOS API - End-to-end collections operating system for CV/CE loan portfolio.

## Features
- **JWT Authentication**: Secure role-based access control
- **Account Management**: Full account insight cards with SHAP reasons
- **Queue Management**: Priority-based calling/field queues
- **Beat Planning**: TSP-optimized field agent routes
- **Scorecards**: Agent performance metrics
- **Audit Trail**: All mutations logged for compliance

## Roles
- **ADMIN**: Full system access
- **STRATEGY**: View analytics, manage campaigns
- **TL/ACM**: Supervise team performance
- **AGENT**: Access assigned accounts, queues, beat plans
- **AUDITOR**: Read-only access with PII masking
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.api_prefix}/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Audit logging middleware
app.add_middleware(AuditLogMiddleware)

# Include routers
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(accounts.router, prefix=settings.api_prefix)
app.include_router(queues.router, prefix=settings.api_prefix)
app.include_router(beatplan.router, prefix=settings.api_prefix)
app.include_router(campaigns.router, prefix=settings.api_prefix)


@app.get("/")
def root():
    """API root - health check."""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "status": "healthy",
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    """Health check endpoint for monitoring."""
    from .database import get_db

    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "version": settings.app_version,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
