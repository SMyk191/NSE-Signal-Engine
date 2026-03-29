from __future__ import annotations

"""
NSE Signal Engine - Authentication Routes

POST /api/auth/signup  -- Register a new user
POST /api/auth/login   -- Log in and receive a JWT
GET  /api/auth/me      -- Get the current user from the JWT
POST /api/auth/logout  -- (stateless) Acknowledge logout
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from services.auth import (
    authenticate_user,
    create_access_token,
    create_user,
    get_current_user,
    get_setting,
    get_user_by_email,
    is_valid_email,
    record_activity,
    _count_users,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
class SignupRequest(BaseModel):
    email: str
    password: str
    name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str = "user"
    status: str = "active"


class AuthResponse(BaseModel):
    token: str
    user: UserResponse
    message: str = ""


# ---------------------------------------------------------------------------
# Dependency: extract current user from Bearer token (required)
# ---------------------------------------------------------------------------
def require_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = get_current_user(credentials.credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# ---------------------------------------------------------------------------
# Dependency: extract current user optionally (for routes that work with
# or without auth)
# ---------------------------------------------------------------------------
def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if credentials is None:
        return None
    return get_current_user(credentials.credentials)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/signup", response_model=AuthResponse)
def signup(body: SignupRequest, request: Request):
    # Check if signup is allowed
    allow_signup = get_setting("allow_signup")
    if allow_signup == "false":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Signup is currently disabled.",
        )

    # Check max users limit
    max_users_str = get_setting("max_users")
    if max_users_str:
        try:
            max_users = int(max_users_str)
            if _count_users() >= max_users:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Maximum number of users reached. Please contact the administrator.",
                )
        except ValueError:
            pass  # Invalid setting value, skip the check

    # Validate email format
    if not is_valid_email(body.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format",
        )

    # Validate password length
    if len(body.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters",
        )

    # Validate name
    if not body.name or not body.name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name is required",
        )

    # Check if email is already registered
    if get_user_by_email(body.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create user and token
    user = create_user(body.email, body.password, body.name)
    token = create_access_token({"sub": str(user["id"])})

    # Record signup activity
    ip_address = request.client.host if request.client else None
    record_activity(user["id"], "signup", f"New user registered: {user['email']}", ip_address)

    # Build response message based on status
    if user.get("status") == "pending":
        message = "Account created. Pending admin approval."
    else:
        message = "Account created successfully."

    return {"token": token, "user": user, "message": message}


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, request: Request):
    # authenticate_user now raises HTTPException for pending/suspended/banned
    user = authenticate_user(body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token({"sub": str(user["id"])})

    # Record login activity
    ip_address = request.client.host if request.client else None
    record_activity(user["id"], "login", None, ip_address)

    return {"token": token, "user": user, "message": ""}


@router.get("/me", response_model=UserResponse)
def me(user=Depends(require_current_user)):
    return user


@router.post("/logout")
def logout():
    return {"message": "Logged out"}


# ---------------------------------------------------------------------------
# Upstox OAuth2 endpoints
# ---------------------------------------------------------------------------
from services.upstox import upstox_service


@router.get("/upstox/login")
def upstox_login():
    """Return the Upstox OAuth2 authorization URL."""
    url = upstox_service.get_auth_url()
    return {"auth_url": url}


@router.get("/upstox/callback")
def upstox_callback(code: str):
    """Exchange the Upstox authorization code for an access token."""
    try:
        data = upstox_service.exchange_code(code)
        return {"status": "connected", "message": "Upstox connected successfully"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to connect Upstox: {exc}",
        )


@router.get("/upstox/status")
def upstox_status():
    """Check whether Upstox is currently authenticated."""
    return {"connected": upstox_service.is_authenticated()}
