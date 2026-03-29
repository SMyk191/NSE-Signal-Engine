from __future__ import annotations

"""
NSE Signal Engine - Configuration

Contains NIFTY 50 stock universe with sector mappings,
API configuration constants, and database settings.
"""

from typing import Dict, List
from pathlib import Path

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
BASE_DIR: Path = Path(__file__).resolve().parent
_DATA_DIR: Path = Path("/data") if Path("/data").exists() else BASE_DIR
DATABASE_PATH: str = str(_DATA_DIR / "nse_signal_engine.db")

# ---------------------------------------------------------------------------
# Cache TTL (seconds) - 1 trading day = 86 400 seconds
# ---------------------------------------------------------------------------
CACHE_TTL_SECONDS: int = 86_400

# ---------------------------------------------------------------------------
# yfinance settings
# ---------------------------------------------------------------------------
YFINANCE_DEFAULT_PERIOD: str = "2y"
YFINANCE_DEFAULT_INTERVAL: str = "1d"
YFINANCE_RETRY_ATTEMPTS: int = 3
YFINANCE_RETRY_DELAY_SECONDS: float = 2.0

# ---------------------------------------------------------------------------
# API server
# ---------------------------------------------------------------------------
API_HOST: str = "0.0.0.0"
API_PORT: int = 8000

# ---------------------------------------------------------------------------
# Sector definitions
# ---------------------------------------------------------------------------
SECTORS: List[str] = [
    "IT",
    "Banking",
    "FMCG",
    "Pharma",
    "Auto",
    "Energy",
    "Metals",
    "Infra",
    "Cement",
    "Insurance",
]

# ---------------------------------------------------------------------------
# NIFTY 50 stock universe  -  symbol -> sector
# ---------------------------------------------------------------------------
NIFTY50_STOCKS: Dict[str, str] = {
    "RELIANCE": "Energy",
    "TCS": "IT",
    "HDFCBANK": "Banking",
    "INFY": "IT",
    "ICICIBANK": "Banking",
    "HINDUNILVR": "FMCG",
    "ITC": "FMCG",
    "SBIN": "Banking",
    "BHARTIARTL": "IT",
    "KOTAKBANK": "Banking",
    "LT": "Infra",
    "AXISBANK": "Banking",
    "ASIANPAINT": "FMCG",
    "MARUTI": "Auto",
    "SUNPHARMA": "Pharma",
    "TITAN": "FMCG",
    "ULTRACEMCO": "Cement",
    "BAJFINANCE": "Banking",
    "WIPRO": "IT",
    "HCLTECH": "IT",
    "NESTLEIND": "FMCG",
    "SHRIRAMFIN": "Banking",
    "NTPC": "Energy",
    "POWERGRID": "Energy",
    "ONGC": "Energy",
    "TATASTEEL": "Metals",
    "JSWSTEEL": "Metals",
    "ADANIENT": "Infra",
    "ADANIPORTS": "Infra",
    "COALINDIA": "Energy",
    "BPCL": "Energy",
    "GRASIM": "Cement",
    "DIVISLAB": "Pharma",
    "DRREDDY": "Pharma",
    "CIPLA": "Pharma",
    "APOLLOHOSP": "Pharma",
    "EICHERMOT": "Auto",
    "HEROMOTOCO": "Auto",
    "BAJAJFINSV": "Banking",
    "TECHM": "IT",
    "TATACONSUM": "FMCG",
    "BRITANNIA": "FMCG",
    "HINDALCO": "Metals",
    "INDUSINDBK": "Banking",
    "SBILIFE": "Insurance",
    "HDFCLIFE": "Insurance",
    "M&M": "Auto",
    "UPL": "FMCG",
    "SHREECEM": "Cement",
    "VEDL": "Metals",
}

# ---------------------------------------------------------------------------
# Helper: convert bare NSE symbol to yfinance ticker (append .NS)
# ---------------------------------------------------------------------------
def is_valid_symbol(symbol: str) -> bool:
    """Return True for any plausible stock symbol (basic format check).

    We intentionally accept anything that *looks* like a ticker and let
    yfinance do the real validation when data is fetched.
    """
    import re
    symbol = symbol.strip().upper()
    if not symbol or len(symbol) > 15:
        return False
    # Allow alphanumeric, ampersand, hyphen, dot (for .NS / .BO suffixes)
    return bool(re.match(r"^[A-Z0-9&.\-]+$", symbol))


def to_yfinance_symbol(symbol: str) -> str:
    """Convert a bare NSE/BSE symbol to a yfinance ticker.

    If the symbol already ends with .NS or .BO, return as-is.
    Otherwise append .NS (NSE is the default exchange).
    """
    symbol = symbol.strip().upper()
    if symbol.endswith(".NS") or symbol.endswith(".BO"):
        return symbol
    return f"{symbol}.NS"


def get_all_symbols() -> List[str]:
    """Return a sorted list of all NIFTY 50 symbols (without .NS suffix)."""
    return sorted(NIFTY50_STOCKS.keys())


def get_sector(symbol: str) -> str:
    """Return the sector for a given symbol, or 'Unknown' if not found."""
    return NIFTY50_STOCKS.get(symbol.strip().upper(), "Unknown")


def get_symbols_by_sector(sector: str) -> List[str]:
    """Return all symbols belonging to a given sector."""
    return sorted(
        sym for sym, sec in NIFTY50_STOCKS.items() if sec.lower() == sector.lower()
    )
