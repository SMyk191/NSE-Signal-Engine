from __future__ import annotations

"""
NSE Signal Engine - Upstox API Integration Service

Handles OAuth2 authentication and option chain data fetching from Upstox.
Used as the primary source for live option chain data (NSE direct is often blocked).
"""

import logging
import os
import time
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config from environment
# ---------------------------------------------------------------------------
UPSTOX_API_KEY: str = os.environ.get("UPSTOX_API_KEY", "")
UPSTOX_API_SECRET: str = os.environ.get("UPSTOX_API_SECRET", "")
UPSTOX_REDIRECT_URL: str = os.environ.get("UPSTOX_REDIRECT_URL", "")
UPSTOX_AUTH_URL: str = "https://api.upstox.com/v2/login/authorization/dialog"
UPSTOX_TOKEN_URL: str = "https://api.upstox.com/v2/login/authorization/token"
UPSTOX_BASE_URL: str = "https://api.upstox.com/v2"


class UpstoxService:
    """Singleton service for Upstox API interactions."""

    def __init__(self) -> None:
        self.access_token: Optional[str] = None
        self.token_expiry: float = 0.0

    def get_auth_url(self) -> str:
        """Generate the OAuth2 authorization URL for user to login."""
        return (
            f"{UPSTOX_AUTH_URL}"
            f"?client_id={UPSTOX_API_KEY}"
            f"&redirect_uri={UPSTOX_REDIRECT_URL}"
            f"&response_type=code"
        )

    def exchange_code(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token.

        Parameters
        ----------
        code : str
            The authorization code received from the OAuth2 callback.

        Returns
        -------
        dict
            The full token response from Upstox.
        """
        resp = requests.post(
            UPSTOX_TOKEN_URL,
            data={
                "code": code,
                "client_id": UPSTOX_API_KEY,
                "client_secret": UPSTOX_API_SECRET,
                "redirect_uri": UPSTOX_REDIRECT_URL,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        self.access_token = data.get("access_token")
        # Upstox tokens typically last ~1 day
        self.token_expiry = time.time() + 86400
        logger.info("Upstox access token acquired successfully")
        return data

    def is_authenticated(self) -> bool:
        """Return True if we have a valid (non-expired) access token."""
        return self.access_token is not None and time.time() < self.token_expiry

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    def fetch_option_chain(
        self, symbol: str, expiry_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch option chain for a stock from Upstox.

        Parameters
        ----------
        symbol : str
            NSE stock symbol (e.g. ``'RELIANCE'``).
        expiry_date : str, optional
            Expiry date in ``YYYY-MM-DD`` format. If omitted, Upstox returns
            the nearest expiry.

        Returns
        -------
        dict
            Parsed option chain data, or empty dict on failure.
        """
        if not self.is_authenticated():
            logger.debug("Upstox not authenticated — skipping option chain fetch")
            return {}

        # Map symbol to Upstox instrument key format
        instrument_key = f"NSE_EQ|{symbol}"

        params: Dict[str, str] = {"instrument_key": instrument_key}
        if expiry_date:
            params["expiry_date"] = expiry_date

        try:
            resp = requests.get(
                f"{UPSTOX_BASE_URL}/option/chain",
                headers=self._headers(),
                params=params,
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("data", {})
        except Exception as e:
            logger.warning("Upstox option chain failed for %s: %s", symbol, e)
            return {}

    def fetch_market_quote(self, symbol: str) -> Dict[str, Any]:
        """Fetch real-time market quote from Upstox.

        Parameters
        ----------
        symbol : str
            NSE stock symbol (e.g. ``'RELIANCE'``).

        Returns
        -------
        dict
            Quote data, or empty dict on failure.
        """
        if not self.is_authenticated():
            return {}
        try:
            instrument_key = f"NSE_EQ|{symbol}"
            resp = requests.get(
                f"{UPSTOX_BASE_URL}/market-quote/quotes",
                headers=self._headers(),
                params={"instrument_key": instrument_key},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("data", {})
        except Exception as e:
            logger.warning("Upstox quote failed for %s: %s", symbol, e)
            return {}


def _parse_upstox_option_chain(raw: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    """Convert Upstox option chain response into the same format used by
    ``analyze_option_chain`` in ``option_chain.py``.

    This normalises the data so the rest of the recommendation engine can
    consume it transparently regardless of source.
    """
    if not raw:
        return {}

    # Upstox returns a list of strike-level entries
    entries = raw if isinstance(raw, list) else raw.get("data", raw.get("options", []))
    if not isinstance(entries, list) or not entries:
        # Try to handle the case where 'raw' is already the data dict
        if isinstance(raw, dict) and "pcr" in raw:
            return raw
        return {}

    strikes = []
    underlying_price = 0.0
    expiry_date = None

    for entry in entries:
        strike_price = entry.get("strike_price", 0.0)
        ce = entry.get("call_options", entry.get("CE", {})) or {}
        pe = entry.get("put_options", entry.get("PE", {})) or {}

        # Try to get underlying price from market data
        if not underlying_price:
            underlying_price = (
                ce.get("underlying_price", 0.0)
                or pe.get("underlying_price", 0.0)
                or entry.get("underlying_spot_price", 0.0)
            )

        if not expiry_date:
            expiry_date = entry.get("expiry", entry.get("expiry_date"))

        ce_market = ce.get("market_data", ce)
        pe_market = pe.get("market_data", pe)

        strikes.append({
            "strike": strike_price,
            "ce_oi": ce_market.get("oi", ce_market.get("open_interest", 0)) or 0,
            "ce_change_oi": ce_market.get("oi_day_change", ce_market.get("change_oi", 0)) or 0,
            "ce_volume": ce_market.get("volume", 0) or 0,
            "ce_iv": ce.get("option_greeks", {}).get("iv", ce_market.get("iv", 0.0)) or 0.0,
            "ce_ltp": ce_market.get("ltp", ce_market.get("last_price", 0.0)) or 0.0,
            "pe_oi": pe_market.get("oi", pe_market.get("open_interest", 0)) or 0,
            "pe_change_oi": pe_market.get("oi_day_change", pe_market.get("change_oi", 0)) or 0,
            "pe_volume": pe_market.get("volume", 0) or 0,
            "pe_iv": pe.get("option_greeks", {}).get("iv", pe_market.get("iv", 0.0)) or 0.0,
            "pe_ltp": pe_market.get("ltp", pe_market.get("last_price", 0.0)) or 0.0,
        })

    if not strikes:
        return {}

    # Import the analysis helpers from option_chain module
    from services.option_chain import (
        _interpret_max_pain,
        _interpret_pcr,
        _iv_analysis,
        _oi_buildup_signal,
        _top_oi_strikes,
        compute_max_pain,
        compute_pcr,
    )

    pcr = compute_pcr(strikes)
    max_pain = compute_max_pain(strikes)

    highest_put_oi = _top_oi_strikes(strikes, "pe_oi")
    highest_call_oi = _top_oi_strikes(strikes, "ce_oi")

    return {
        "underlying_price": underlying_price,
        "nearest_expiry": expiry_date,
        "pcr": pcr,
        "pcr_interpretation": _interpret_pcr(pcr),
        "max_pain": max_pain,
        "max_pain_interpretation": _interpret_max_pain(max_pain, underlying_price) if underlying_price else "",
        "highest_put_oi_strikes": highest_put_oi,
        "highest_call_oi_strikes": highest_call_oi,
        "oi_buildup_signal": _oi_buildup_signal(strikes, underlying_price) if underlying_price else "Underlying price unavailable",
        "iv_analysis": _iv_analysis(strikes, underlying_price) if underlying_price else "Underlying price unavailable",
        "total_ce_oi": sum(s["ce_oi"] for s in strikes),
        "total_pe_oi": sum(s["pe_oi"] for s in strikes),
        "strike_count": len(strikes),
        "source": "upstox",
    }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------
upstox_service = UpstoxService()
