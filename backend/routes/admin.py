from __future__ import annotations

"""
NSE Signal Engine - Admin Routes

Provides admin-only endpoints for user management, activity tracking,
and global settings.

All endpoints require admin role via the require_admin_user dependency.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from services.auth import (
    delete_user,
    get_activity_log,
    get_all_settings,
    get_all_users,
    get_current_user,
    get_user_by_id,
    get_user_stats,
    record_activity,
    require_admin,
    update_setting,
    update_user_role,
    update_user_status,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])

security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Dependency: require admin user
# ---------------------------------------------------------------------------
def require_admin_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Extract JWT, verify token, and check admin role."""
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
    require_admin(user)
    return user


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class StatusUpdateRequest(BaseModel):
    status: str


class RoleUpdateRequest(BaseModel):
    role: str


class SettingsUpdateRequest(BaseModel):
    settings: dict


# ---------------------------------------------------------------------------
# User management endpoints
# ---------------------------------------------------------------------------
@router.get("/users")
def list_users(admin=Depends(require_admin_user)):
    """GET /api/admin/users - List all users with stats."""
    users = get_all_users()
    stats = get_user_stats()
    return {"users": users, "stats": stats}


@router.get("/users/{user_id}")
def get_user_detail(user_id: int, admin=Depends(require_admin_user)):
    """GET /api/admin/users/{user_id} - Get single user detail + their activity."""
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    # Remove hashed_password from response
    user_data = {k: v for k, v in user.items() if k != "hashed_password"}
    activity = get_activity_log(limit=50, user_id=user_id)
    return {"user": user_data, "activity": activity}


@router.put("/users/{user_id}/status")
def change_user_status(
    user_id: int,
    body: StatusUpdateRequest,
    admin=Depends(require_admin_user),
):
    """PUT /api/admin/users/{user_id}/status - Update user status."""
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    updated = update_user_status(user_id, body.status)
    record_activity(
        admin["id"],
        "admin_update_status",
        f"Changed user {user_id} status to {body.status}",
        None,
    )
    return {"user": {k: v for k, v in updated.items() if k != "hashed_password"}}


@router.put("/users/{user_id}/role")
def change_user_role(
    user_id: int,
    body: RoleUpdateRequest,
    admin=Depends(require_admin_user),
):
    """PUT /api/admin/users/{user_id}/role - Update user role."""
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    updated = update_user_role(user_id, body.role)
    record_activity(
        admin["id"],
        "admin_update_role",
        f"Changed user {user_id} role to {body.role}",
        None,
    )
    return {"user": {k: v for k, v in updated.items() if k != "hashed_password"}}


@router.delete("/users/{user_id}")
def remove_user(user_id: int, admin=Depends(require_admin_user)):
    """DELETE /api/admin/users/{user_id} - Delete user (cannot delete self)."""
    if user_id == admin["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account.",
        )
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    deleted = delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    record_activity(
        admin["id"],
        "admin_delete_user",
        f"Deleted user {user_id} ({user.get('email', 'unknown')})",
        None,
    )
    return {"message": f"User {user_id} deleted."}


# ---------------------------------------------------------------------------
# Stats & activity endpoints
# ---------------------------------------------------------------------------
@router.get("/stats")
def dashboard_stats(admin=Depends(require_admin_user)):
    """GET /api/admin/stats - Dashboard stats."""
    return get_user_stats()


@router.get("/activity")
def activity_log(
    limit: int = Query(default=100, ge=1, le=1000),
    user_id: Optional[int] = Query(default=None),
    action: Optional[str] = Query(default=None),
    admin=Depends(require_admin_user),
):
    """GET /api/admin/activity - Activity log with optional filters."""
    entries = get_activity_log(limit=limit, user_id=user_id, action=action)
    return {"activity": entries, "count": len(entries)}


# ---------------------------------------------------------------------------
# Settings endpoints
# ---------------------------------------------------------------------------
@router.get("/settings")
def get_settings(admin=Depends(require_admin_user)):
    """GET /api/admin/settings - Get current global settings."""
    return {"settings": get_all_settings()}


@router.put("/settings")
def update_settings(body: SettingsUpdateRequest, admin=Depends(require_admin_user)):
    """PUT /api/admin/settings - Update global settings."""
    allowed_keys = {"require_approval", "max_users", "allow_signup"}
    for key, value in body.settings.items():
        if key not in allowed_keys:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown setting: {key}. Allowed: {', '.join(sorted(allowed_keys))}",
            )
        update_setting(key, str(value))
    record_activity(
        admin["id"],
        "admin_update_settings",
        str(body.settings),
        None,
    )
    return {"settings": get_all_settings()}
