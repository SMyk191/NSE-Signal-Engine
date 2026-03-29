from __future__ import annotations

"""
NSE Signal Engine - Database Layer

Async SQLite database for caching OHLCV data, fundamentals,
computed signals, and sentiment analysis results.
All caches use a 1-day TTL to avoid redundant API calls during
market hours while staying fresh across trading sessions.
"""

import json
import time
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite
import pandas as pd

from config import CACHE_TTL_SECONDS, DATABASE_PATH

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_SCHEMA_SQL: str = """
CREATE TABLE IF NOT EXISTS ohlcv_cache (
    symbol      TEXT    NOT NULL,
    date        TEXT    NOT NULL,
    open        REAL    NOT NULL,
    high        REAL    NOT NULL,
    low         REAL    NOT NULL,
    close       REAL    NOT NULL,
    volume      INTEGER NOT NULL,
    adj_close   REAL    NOT NULL,
    fetched_at  REAL    NOT NULL,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS fundamentals_cache (
    symbol      TEXT PRIMARY KEY NOT NULL,
    data_json   TEXT    NOT NULL,
    fetched_at  REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS signals_cache (
    symbol      TEXT PRIMARY KEY NOT NULL,
    signal_json TEXT    NOT NULL,
    computed_at REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS sentiment_cache (
    symbol         TEXT PRIMARY KEY NOT NULL,
    sentiment_json TEXT    NOT NULL,
    analyzed_at    REAL    NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------
async def init_db() -> None:
    """Create all tables if they do not exist yet."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript(_SCHEMA_SQL)
        await db.commit()


# ---------------------------------------------------------------------------
# TTL helper
# ---------------------------------------------------------------------------
def is_cache_fresh(fetched_at: float, ttl: int = CACHE_TTL_SECONDS) -> bool:
    """Return True if *fetched_at* epoch timestamp is within *ttl* seconds of now."""
    return (time.time() - fetched_at) < ttl


# ---------------------------------------------------------------------------
# OHLCV helpers
# ---------------------------------------------------------------------------
async def get_cached_ohlcv(symbol: str) -> Optional[pd.DataFrame]:
    """Return cached OHLCV DataFrame for *symbol*, or None if stale / missing.

    The cache is considered fresh if **any** row for the symbol was fetched
    within the TTL window (we store ``fetched_at`` per-row but they are all
    written in the same batch, so checking MIN is sufficient).
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Check freshness first
        cursor = await db.execute(
            "SELECT MIN(fetched_at) AS oldest FROM ohlcv_cache WHERE symbol = ?",
            (symbol,),
        )
        row = await cursor.fetchone()
        if row is None or row["oldest"] is None:
            return None
        if not is_cache_fresh(row["oldest"]):
            return None

        # Fetch all rows
        cursor = await db.execute(
            """
            SELECT date, open, high, low, close, volume, adj_close
            FROM ohlcv_cache
            WHERE symbol = ?
            ORDER BY date ASC
            """,
            (symbol,),
        )
        rows = await cursor.fetchall()

    if not rows:
        return None

    records: List[Dict[str, Any]] = [
        {
            "Date": r["date"],
            "Open": r["open"],
            "High": r["high"],
            "Low": r["low"],
            "Close": r["close"],
            "Volume": r["volume"],
            "Adj Close": r["adj_close"],
        }
        for r in rows
    ]
    df = pd.DataFrame(records)
    df["Date"] = pd.to_datetime(df["Date"])
    df.set_index("Date", inplace=True)
    df.sort_index(inplace=True)
    return df


async def save_ohlcv(symbol: str, df: pd.DataFrame) -> None:
    """Persist an OHLCV DataFrame into the cache (full replace for the symbol)."""
    now = time.time()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Remove stale rows for this symbol
        await db.execute("DELETE FROM ohlcv_cache WHERE symbol = ?", (symbol,))

        rows: List[Tuple[str, str, float, float, float, float, int, float, float]] = []
        for date_idx, row in df.iterrows():
            date_str = str(date_idx.date()) if hasattr(date_idx, "date") else str(date_idx)
            rows.append((
                symbol,
                date_str,
                float(row.get("Open", 0)),
                float(row.get("High", 0)),
                float(row.get("Low", 0)),
                float(row.get("Close", 0)),
                int(row.get("Volume", 0)),
                float(row.get("Adj Close", row.get("Close", 0))),
                now,
            ))

        await db.executemany(
            """
            INSERT OR REPLACE INTO ohlcv_cache
                (symbol, date, open, high, low, close, volume, adj_close, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Fundamentals helpers
# ---------------------------------------------------------------------------
async def get_cached_fundamentals(symbol: str) -> Optional[Dict[str, Any]]:
    """Return cached fundamentals dict, or None if stale / missing."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT data_json, fetched_at FROM fundamentals_cache WHERE symbol = ?",
            (symbol,),
        )
        row = await cursor.fetchone()

    if row is None or not is_cache_fresh(row["fetched_at"]):
        return None
    return json.loads(row["data_json"])


async def save_fundamentals(symbol: str, data: Dict[str, Any]) -> None:
    """Persist fundamentals dict into the cache."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO fundamentals_cache (symbol, data_json, fetched_at)
            VALUES (?, ?, ?)
            """,
            (symbol, json.dumps(data, default=str), time.time()),
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Signals helpers
# ---------------------------------------------------------------------------
async def get_cached_signals(symbol: str) -> Optional[Dict[str, Any]]:
    """Return cached signal dict, or None if stale / missing."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT signal_json, computed_at FROM signals_cache WHERE symbol = ?",
            (symbol,),
        )
        row = await cursor.fetchone()

    if row is None or not is_cache_fresh(row["computed_at"]):
        return None
    return json.loads(row["signal_json"])


async def save_signals(symbol: str, data: Dict[str, Any]) -> None:
    """Persist computed signal dict into the cache."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO signals_cache (symbol, signal_json, computed_at)
            VALUES (?, ?, ?)
            """,
            (symbol, json.dumps(data, default=str), time.time()),
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Sentiment helpers
# ---------------------------------------------------------------------------
async def get_cached_sentiment(symbol: str) -> Optional[Dict[str, Any]]:
    """Return cached sentiment dict, or None if stale / missing."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT sentiment_json, analyzed_at FROM sentiment_cache WHERE symbol = ?",
            (symbol,),
        )
        row = await cursor.fetchone()

    if row is None or not is_cache_fresh(row["analyzed_at"]):
        return None
    return json.loads(row["sentiment_json"])


async def save_sentiment(symbol: str, data: Dict[str, Any]) -> None:
    """Persist sentiment analysis dict into the cache."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO sentiment_cache (symbol, sentiment_json, analyzed_at)
            VALUES (?, ?, ?)
            """,
            (symbol, json.dumps(data, default=str), time.time()),
        )
        await db.commit()
