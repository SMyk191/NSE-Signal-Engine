from __future__ import annotations

"""
NSE Signal Engine - Authentication Service

Handles user registration, login, password hashing, JWT token
management, admin functions, activity tracking, and global settings
using SQLite for user storage.
"""

import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext

from config import BASE_DIR

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SECRET_KEY: str = os.environ.get("JWT_SECRET", "nse-signal-engine-secret-key-change-in-production")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

# Use /data/ for Railway persistent volume, fallback to local for dev
_data_dir = Path("/data") if Path("/data").exists() else BASE_DIR
AUTH_DB_PATH: str = str(_data_dir / "auth.db")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    columns = [row["name"] for row in cursor.fetchall()]
    return column in columns


def init_auth_db() -> None:
    """Create/update the users table, activity_log table, and settings table."""
    conn = _get_conn()

    # Create users table if it doesn't exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            email           TEXT    NOT NULL UNIQUE,
            name            TEXT    NOT NULL,
            hashed_password TEXT    NOT NULL,
            role            TEXT    NOT NULL DEFAULT 'user',
            status          TEXT    NOT NULL DEFAULT 'pending',
            last_login      TEXT,
            login_count     INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # ALTER existing table to add new columns if they don't exist
    alter_columns = {
        "role": "TEXT DEFAULT 'user'",
        "status": "TEXT DEFAULT 'pending'",
        "login_count": "INTEGER DEFAULT 0",
        "last_login": "TEXT",
        "created_at": "TEXT DEFAULT (datetime('now'))",
    }
    for col_name, col_def in alter_columns.items():
        if not _column_exists(conn, "users", col_name):
            conn.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")

    # Activity log table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            action      TEXT NOT NULL,
            details     TEXT,
            ip_address  TEXT,
            timestamp   TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Global settings table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key         TEXT PRIMARY KEY,
            value       TEXT,
            updated_at  TEXT DEFAULT (datetime('now'))
        )
    """)

    # Insert default settings if they don't exist
    default_settings = {
        "require_approval": "true",
        "max_users": "100",
        "allow_signup": "true",
    }
    for key, value in default_settings.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )

    # Migration: ensure first user (id=1) is admin+active
    first_user = conn.execute("SELECT id, role, status FROM users WHERE id = 1").fetchone()
    if first_user:
        conn.execute("UPDATE users SET role = 'admin', status = 'active' WHERE id = 1")

    # Also promote any user matching ADMIN_EMAIL env var
    admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    if admin_email:
        conn.execute(
            "UPDATE users SET role = 'admin', status = 'active' WHERE LOWER(email) = ?",
            (admin_email,),
        )

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------
def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Look up a user by email. Returns a dict or None."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Look up a user by id. Returns a dict or None."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def _count_users() -> int:
    """Return total number of users."""
    conn = _get_conn()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return count


def create_user(email: str, password: str, name: str) -> Dict[str, Any]:
    """Hash the password, insert a new user, and return the user dict (no password).

    The FIRST user is automatically admin + active. Subsequent users are
    user + pending (or active if require_approval is false).
    """
    hashed = pwd_context.hash(password)

    # Determine role and status for new user
    is_first_user = _count_users() == 0
    if is_first_user:
        role = "admin"
        user_status = "active"
    else:
        role = "user"
        require_approval = get_setting("require_approval")
        user_status = "pending" if require_approval == "true" else "active"

    conn = _get_conn()
    cursor = conn.execute(
        "INSERT INTO users (email, name, hashed_password, role, status) VALUES (?, ?, ?, ?, ?)",
        (email.lower().strip(), name.strip(), hashed, role, user_status),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return {
        "id": user_id,
        "email": email.lower().strip(),
        "name": name.strip(),
        "role": role,
        "status": user_status,
    }


def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    """Verify email + password. Returns user dict (no password) or None."""
    user = get_user_by_email(email)
    if user is None:
        return None
    if not pwd_context.verify(password, user["hashed_password"]):
        return None

    # Check user status
    user_status = user.get("status", "active")
    if user_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account pending approval. Please wait for an admin to activate your account.",
        )
    if user_status == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account suspended. Please contact the administrator.",
        )
    if user_status == "banned":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account banned. Access denied.",
        )

    # Update last_login and login_count
    conn = _get_conn()
    conn.execute(
        "UPDATE users SET last_login = datetime('now'), login_count = COALESCE(login_count, 0) + 1 WHERE id = ?",
        (user["id"],),
    )
    conn.commit()
    conn.close()
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "role": user.get("role", "user"),
        "status": user.get("status", "active"),
    }


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------
def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str) -> Optional[Dict[str, Any]]:
    """Decode a JWT token and return the user dict, or None if invalid."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str = payload.get("sub")
        if user_id_str is None:
            return None
        user = get_user_by_id(int(user_id_str))
        if user is None:
            return None
        return {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user.get("role", "user"),
            "status": user.get("status", "active"),
        }
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
def is_valid_email(email: str) -> bool:
    """Basic email format validation."""
    return bool(re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", email))


# ---------------------------------------------------------------------------
# Admin helpers
# ---------------------------------------------------------------------------
def require_admin(user: Dict[str, Any]) -> None:
    """Raise HTTPException(403) if user is not an admin."""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )


def get_all_users() -> List[Dict[str, Any]]:
    """Return a list of all users (no passwords)."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, email, name, role, status, last_login, login_count, created_at FROM users ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_user_role(user_id: int, role: str) -> Optional[Dict[str, Any]]:
    """Change a user's role. Returns updated user or None if not found."""
    if role not in ("admin", "user", "premium"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {role}. Must be 'admin', 'user', or 'premium'.",
        )
    conn = _get_conn()
    conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    conn.commit()
    conn.close()
    return get_user_by_id(user_id)


def update_user_status(user_id: int, new_status: str) -> Optional[Dict[str, Any]]:
    """Change a user's status. Returns updated user or None if not found."""
    if new_status not in ("active", "pending", "suspended", "banned"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status: {new_status}. Must be 'active', 'pending', 'suspended', or 'banned'.",
        )
    conn = _get_conn()
    conn.execute("UPDATE users SET status = ? WHERE id = ?", (new_status, user_id))
    conn.commit()
    conn.close()
    return get_user_by_id(user_id)


def delete_user(user_id: int) -> bool:
    """Delete a user by id. Returns True if deleted, False if not found."""
    conn = _get_conn()
    cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def get_user_stats() -> Dict[str, Any]:
    """Return aggregate user statistics."""
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM users WHERE status = 'active'").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM users WHERE status = 'pending'").fetchone()[0]
    suspended = conn.execute("SELECT COUNT(*) FROM users WHERE status = 'suspended'").fetchone()[0]
    banned = conn.execute("SELECT COUNT(*) FROM users WHERE status = 'banned'").fetchone()[0]
    signups_today = conn.execute(
        "SELECT COUNT(*) FROM users WHERE date(created_at) = date('now')"
    ).fetchone()[0]
    signups_this_week = conn.execute(
        "SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-7 days')"
    ).fetchone()[0]
    conn.close()
    return {
        "total_users": total,
        "active": active,
        "pending": pending,
        "suspended": suspended,
        "banned": banned,
        "signups_today": signups_today,
        "signups_this_week": signups_this_week,
    }


# ---------------------------------------------------------------------------
# Activity tracking
# ---------------------------------------------------------------------------
def record_activity(
    user_id: Optional[int],
    action: str,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Log a user activity entry."""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO activity_log (user_id, action, details, ip_address) VALUES (?, ?, ?, ?)",
        (user_id, action, details, ip_address),
    )
    conn.commit()
    conn.close()


def get_activity_log(
    limit: int = 100,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return recent activity entries, optionally filtered by user_id and/or action."""
    conn = _get_conn()
    query = "SELECT a.*, u.email, u.name as user_name FROM activity_log a LEFT JOIN users u ON a.user_id = u.id"
    conditions: List[str] = []
    params: List[Any] = []

    if user_id is not None:
        conditions.append("a.user_id = ?")
        params.append(user_id)
    if action is not None:
        conditions.append("a.action = ?")
        params.append(action)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY a.timestamp DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Global settings
# ---------------------------------------------------------------------------
def get_setting(key: str) -> Optional[str]:
    """Get a single setting value by key."""
    conn = _get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    if row is None:
        return None
    return row["value"]


def get_all_settings() -> Dict[str, str]:
    """Return all settings as a dict."""
    conn = _get_conn()
    rows = conn.execute("SELECT key, value, updated_at FROM settings").fetchall()
    conn.close()
    return {row["key"]: {"value": row["value"], "updated_at": row["updated_at"]} for row in rows}


def update_setting(key: str, value: str) -> None:
    """Update or insert a setting."""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now')) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')",
        (key, value),
    )
    conn.commit()
    conn.close()
