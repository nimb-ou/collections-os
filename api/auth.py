"""
Authentication and Authorization
JWT token generation, password hashing, and user verification.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .config import settings
from .database import get_db_dependency

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token scheme
security = HTTPBearer()


def hash_password(password: str) -> str:
    """Hash a plain-text password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload to encode (should include 'sub' for user_id)
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    conn = Depends(get_db_dependency)
) -> Dict[str, Any]:
    """
    FastAPI dependency to get the current authenticated user.

    Args:
        credentials: HTTP Bearer token from request header
        conn: Database connection

    Returns:
        User dict with user_id, username, role, agent_id

    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    # Fetch user from database
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, username, email, role, agent_id, active
        FROM users
        WHERE user_id = %s AND active = true
    """, (user_id,))

    user = cur.fetchone()
    cur.close()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return dict(user)


def require_roles(*allowed_roles: str):
    """
    Decorator factory for role-based access control.

    Usage:
        @router.get("/admin-only")
        def admin_endpoint(current_user: dict = Depends(require_roles("ADMIN"))):
            ...

    Args:
        *allowed_roles: Variable number of allowed role names

    Returns:
        Dependency function that checks user role
    """
    def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}",
            )
        return current_user

    return role_checker


def authenticate_user(username: str, password: str, conn) -> Optional[Dict[str, Any]]:
    """
    Authenticate a user by username and password.

    Args:
        username: Username
        password: Plain-text password
        conn: Database connection

    Returns:
        User dict if authentication successful, None otherwise
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, username, email, password_hash, role, agent_id, active
        FROM users
        WHERE username = %s AND active = true
    """, (username,))

    user = cur.fetchone()
    cur.close()

    if user is None:
        return None

    # Verify password
    if not user["password_hash"]:
        # SSO user - cannot authenticate with password
        return None

    if not verify_password(password, user["password_hash"]):
        return None

    return dict(user)


def update_last_login(user_id: str, conn) -> None:
    """Update user's last login timestamp."""
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET last_login = CURRENT_TIMESTAMP,
            failed_login_attempts = 0
        WHERE user_id = %s
    """, (user_id,))
    conn.commit()
    cur.close()


def increment_failed_login(username: str, conn) -> None:
    """Increment failed login attempts for a user."""
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET failed_login_attempts = failed_login_attempts + 1
        WHERE username = %s
    """, (username,))
    conn.commit()
    cur.close()
