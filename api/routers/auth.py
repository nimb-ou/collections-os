"""
Authentication Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from ..models import LoginRequest, TokenResponse
from ..auth import authenticate_user, create_access_token, update_last_login, increment_failed_login
from ..database import get_db_dependency

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest,
    conn = Depends(get_db_dependency)
):
    """
    Authenticate user and return JWT access token.

    **Process:**
    1. Validate username/password against database
    2. Generate JWT token with user_id, role, agent_id
    3. Update last_login timestamp
    4. Return token and user info

    **Security:**
    - Passwords hashed with bcrypt
    - Failed login attempts tracked
    - Inactive users cannot log in
    """
    user = authenticate_user(credentials.username, credentials.password, conn)

    if user is None:
        # Increment failed login attempts
        increment_failed_login(credentials.username, conn)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token = create_access_token(
        data={
            "sub": user["user_id"],
            "username": user["username"],
            "role": user["role"],
            "agent_id": user.get("agent_id"),
        }
    )

    # Update last login
    update_last_login(user["user_id"], conn)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user["user_id"],
        username=user["username"],
        role=user["role"],
        agent_id=user.get("agent_id"),
    )


@router.get("/me")
def get_current_user_info(
    conn = Depends(get_db_dependency),
    current_user: dict = Depends(lambda: None)  # Will be replaced by actual auth dependency
):
    """
    Get current authenticated user's information.

    Requires valid JWT token in Authorization header.
    """
    from ..auth import get_current_user

    user = get_current_user(conn=conn)
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "email": user.get("email"),
        "role": user["role"],
        "agent_id": user.get("agent_id"),
        "active": user["active"],
    }
