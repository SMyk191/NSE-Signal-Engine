from __future__ import annotations

"""
NSE Signal Engine - Data Fetcher Service

Fetches OHLCV price data, fundamentals, and financial statements for
NSE-listed stocks via yfinance. Uses SQLite caching (1-day TTL) to
minimise redundant network calls.
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

import pandas as pd
import yfinance as yf

from config import (
    NIFTY50_STOCKS,
    YFINANCE_DEFAULT_INTERVAL,
    YFINANCE_DEFAULT_PERIOD,
    YFINANCE_RETRY_ATTEMPTS,
    YFINANCE_RETRY_DELAY_SECONDS,
    to_yfinance_symbol,
)
from database import get_cached_ohlcv, save_ohlcv

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Clean raw yfinance OHLCV DataFrame.

    Steps:
        1. Forward-fill then backward-fill missing values.
        2. Remove rows where volume is zero (non-trading days / bad data).
        3. Prefer 'Adj Close' column; create it from 'Close' if absent.
        4. Ensure the index is a DatetimeIndex named 'Date'.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    # Normalise column names (yfinance sometimes returns MultiIndex for bulk)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Ensure Adj Close exists
    if "Adj Close" not in df.columns and "Close" in df.columns:
        df["Adj Close"] = df["Close"]

    # Forward-fill then backward-fill
    df = df.ffill().bfill()

    # Drop zero-volume rows
    if "Volume" in df.columns:
        df = df[df["Volume"] > 0]

    # Guarantee DatetimeIndex
    if not isinstance(df.index, pd.DatetimeIndex):
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
            df.set_index("Date", inplace=True)

    df.index.name = "Date"
    df.sort_index(inplace=True)
    return df


def _retry_fetch(func, *args, **kwargs) -> Any:
    """Call *func* up to YFINANCE_RETRY_ATTEMPTS times, sleeping between failures."""
    last_error: Optional[Exception] = None
    for attempt in range(1, YFINANCE_RETRY_ATTEMPTS + 1):
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Attempt %d/%d failed for %s: %s",
                attempt,
                YFINANCE_RETRY_ATTEMPTS,
                func.__name__,
                exc,
            )
            if attempt < YFINANCE_RETRY_ATTEMPTS:
                time.sleep(YFINANCE_RETRY_DELAY_SECONDS * attempt)
    raise RuntimeError(
        f"All {YFINANCE_RETRY_ATTEMPTS} attempts failed for {func.__name__}"
    ) from last_error


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def fetch_ohlcv(
    symbol: str,
    period: str = YFINANCE_DEFAULT_PERIOD,
    interval: str = YFINANCE_DEFAULT_INTERVAL,
) -> pd.DataFrame:
    """Fetch OHLCV price history for *symbol* from yfinance.

    Args:
        symbol: NSE symbol (e.g. ``'RELIANCE'``). ``.NS`` is appended automatically.
        period: yfinance period string (default ``'2y'``).
        interval: yfinance interval string (default ``'1d'``).

    Returns:
        Cleaned ``pd.DataFrame`` with columns
        ``Open, High, Low, Close, Volume, Adj Close`` indexed by ``Date``.
    """
    yf_symbol = to_yfinance_symbol(symbol)
    ticker = yf.Ticker(yf_symbol)

    def _download() -> pd.DataFrame:
        df = ticker.history(period=period, interval=interval)
        if df is None or df.empty:
            raise ValueError(f"No data returned for {yf_symbol}")
        return df

    raw_df = _retry_fetch(_download)
    return _clean_ohlcv(raw_df)


def fetch_fundamentals(symbol: str) -> Dict[str, Any]:
    """Fetch key fundamental data for *symbol*.

    Returns a dict with fields like ``marketCap``, ``trailingPE``,
    ``bookValue``, ``dividendYield``, ``sector``, ``industry``, etc.
    """
    yf_symbol = to_yfinance_symbol(symbol)
    ticker = yf.Ticker(yf_symbol)

    def _get_info() -> Dict[str, Any]:
        info = ticker.info
        if not info:
            raise ValueError(f"No fundamentals for {yf_symbol}")
        return info

    raw_info: Dict[str, Any] = _retry_fetch(_get_info)

    # Pick the fields most useful for analysis
    keys_of_interest = [
        "shortName",
        "longName",
        "sector",
        "industry",
        "marketCap",
        "enterpriseValue",
        "trailingPE",
        "forwardPE",
        "priceToBook",
        "bookValue",
        "trailingEps",
        "forwardEps",
        "dividendYield",
        "dividendRate",
        "payoutRatio",
        "beta",
        "fiftyTwoWeekHigh",
        "fiftyTwoWeekLow",
        "fiftyDayAverage",
        "twoHundredDayAverage",
        "returnOnEquity",
        "returnOnAssets",
        "debtToEquity",
        "currentRatio",
        "quickRatio",
        "revenueGrowth",
        "earningsGrowth",
        "grossMargins",
        "operatingMargins",
        "profitMargins",
        "totalRevenue",
        "totalDebt",
        "totalCash",
        "freeCashflow",
        "operatingCashflow",
        "recommendationKey",
        "recommendationMean",
        "numberOfAnalystOpinions",
        "targetMeanPrice",
        "targetHighPrice",
        "targetLowPrice",
    ]
    return {k: raw_info.get(k) for k in keys_of_interest}


def fetch_financials(symbol: str) -> Dict[str, Any]:
    """Fetch quarterly and annual financial statements for *symbol*.

    Returns a dict with keys:
        ``quarterly_income``, ``annual_income``,
        ``quarterly_balance``, ``annual_balance``,
        ``quarterly_cashflow``, ``annual_cashflow``
    Each value is a dict-of-dicts (JSON-serialisable) representation of the
    corresponding ``pd.DataFrame``.
    """
    yf_symbol = to_yfinance_symbol(symbol)
    ticker = yf.Ticker(yf_symbol)

    def _safe_to_dict(df: Optional[pd.DataFrame]) -> Dict[str, Any]:
        if df is None or df.empty:
            return {}
        return df.reset_index().to_dict(orient="records")

    def _get_financials() -> Dict[str, Any]:
        return {
            "quarterly_income": _safe_to_dict(ticker.quarterly_income_stmt),
            "annual_income": _safe_to_dict(ticker.income_stmt),
            "quarterly_balance": _safe_to_dict(ticker.quarterly_balance_sheet),
            "annual_balance": _safe_to_dict(ticker.balance_sheet),
            "quarterly_cashflow": _safe_to_dict(ticker.quarterly_cashflow),
            "annual_cashflow": _safe_to_dict(ticker.cashflow),
        }

    return _retry_fetch(_get_financials)


async def get_cached_or_fetch(symbol: str) -> pd.DataFrame:
    """Return OHLCV data for *symbol*, using SQLite cache when fresh.

    If the cache is stale or missing, fetches fresh data from yfinance,
    stores it in the cache, and returns the cleaned DataFrame.
    """
    symbol = symbol.strip().upper()

    # Try cache first
    cached_df = await get_cached_ohlcv(symbol)
    if cached_df is not None and not cached_df.empty:
        logger.info("Cache hit for %s (%d rows)", symbol, len(cached_df))
        return cached_df

    # Fetch from yfinance (blocking call, run in thread pool)
    logger.info("Cache miss for %s - fetching from yfinance", symbol)
    loop = asyncio.get_running_loop()
    df = await loop.run_in_executor(None, fetch_ohlcv, symbol)

    if df is not None and not df.empty:
        await save_ohlcv(symbol, df)
        logger.info("Saved %d rows for %s to cache", len(df), symbol)

    return df


async def fetch_bulk_nifty50() -> Dict[str, pd.DataFrame]:
    """Fetch OHLCV data for all NIFTY 50 stocks, using cache where available.

    Returns a dict mapping each NSE symbol (e.g. ``'RELIANCE'``) to its
    cleaned OHLCV DataFrame. Symbols that fail to download are logged and
    skipped.
    """
    results: Dict[str, pd.DataFrame] = {}
    symbols = sorted(NIFTY50_STOCKS.keys())

    tasks = [get_cached_or_fetch(sym) for sym in symbols]
    fetched = await asyncio.gather(*tasks, return_exceptions=True)

    for sym, result in zip(symbols, fetched):
        if isinstance(result, Exception):
            logger.error("Failed to fetch %s: %s", sym, result)
            continue
        if result is not None and not result.empty:
            results[sym] = result

    logger.info(
        "Bulk fetch complete: %d/%d symbols loaded", len(results), len(symbols)
    )
    return results
