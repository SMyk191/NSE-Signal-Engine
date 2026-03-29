from __future__ import annotations

"""
NSE Signal Engine - Authentication Service

Handles user registration, login, password hashing, and JWT token
management using SQLite for user storage.
"""

import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from config import BASE_DIR

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SECRET_KEY: str = os.environ.get("JWT_SECRET", "nse-signal-engine-secret-key-change-in-production")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

AUTH_DB_PATH: str = str(BASE_DIR / "auth.db")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db() -> None:
    """Create the users table if it does not exist."""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            email           TEXT    NOT NULL UNIQUE,
            name            TEXT    NOT NULL,
            hashed_password TEXT    NOT NULL,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
            last_login      TEXT
        )
    """)
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


def create_user(email: str, password: str, name: str) -> Dict[str, Any]:
    """Hash the password, insert a new user, and return the user dict (no password)."""
    hashed = pwd_context.hash(password)
    conn = _get_conn()
    cursor = conn.execute(
        "INSERT INTO users (email, name, hashed_password) VALUES (?, ?, ?)",
        (email.lower().strip(), name.strip(), hashed),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return {"id": user_id, "email": email.lower().strip(), "name": name.strip()}


def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    """Verify email + password. Returns user dict (no password) or None."""
    user = get_user_by_email(email)
    if user is None:
        return None
    if not pwd_context.verify(password, user["hashed_password"]):
        return None
    # Update last_login
    conn = _get_conn()
    conn.execute(
        "UPDATE users SET last_login = datetime('now') WHERE id = ?",
        (user["id"],),
    )
    conn.commit()
    conn.close()
    return {"id": user["id"], "email": user["email"], "name": user["name"]}


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
        return {"id": user["id"], "email": user["email"], "name": user["name"]}
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
def is_valid_email(email: str) -> bool:
    """Basic email format validation."""
    return bool(re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", email))
