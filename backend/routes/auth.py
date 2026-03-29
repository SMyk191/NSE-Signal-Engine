from __future__ import annotations

"""
NSE Signal Engine - Authentication Routes

POST /api/auth/signup  — Register a new user
POST /api/auth/login   — Log in and receive a JWT
GET  /api/auth/me      — Get the current user from the JWT
POST /api/auth/logout  — (stateless) Acknowledge logout
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from services.auth import (
    authenticate_user,
    create_access_token,
    create_user,
    get_current_user,
    get_user_by_email,
    is_valid_email,
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


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


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
def signup(body: SignupRequest):
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
    return {"token": token, "user": user}


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest):
    user = authenticate_user(body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token({"sub": str(user["id"])})
    return {"token": token, "user": user}


@router.get("/me", response_model=UserResponse)
def me(user=Depends(require_current_user)):
    return user


@router.post("/logout")
def logout():
    return {"message": "Logged out"}
