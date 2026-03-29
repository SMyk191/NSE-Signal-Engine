from __future__ import annotations

"""
NSE Signal Engine - Option Chain Analysis & Action Recommendation Service

Fetches live option chain data from NSE India, computes max pain, PCR,
support/resistance from OI, IV skew, and combines everything with technical
indicators and the composite signal score to produce an actionable
BUY / SELL / HOLD recommendation with entry zone, targets, and stop loss.
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NSE_BASE_URL = "https://www.nseindia.com"
NSE_OPTION_CHAIN_URL = (
    "https://www.nseindia.com/api/option-chain-equities?symbol={symbol}"
)
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/option-chain",
    "Connection": "keep-alive",
}

# How many top strikes to report for OI analysis
TOP_OI_STRIKES = 5

# Session timeout (seconds)
REQUEST_TIMEOUT = 15


# ---------------------------------------------------------------------------
# 1.  NSE Session & Data Fetcher
# ---------------------------------------------------------------------------

class NSESession:
    """Maintains cookies required by NSE India's API.

    NSE requires a valid session cookie obtained by first visiting the
    homepage. This class wraps a ``requests.Session`` that handles that
    handshake transparently.
    """

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(NSE_HEADERS)
        self._cookies_set = False

    def _ensure_cookies(self) -> None:
        """Hit the NSE homepage to obtain session cookies if not yet done."""
        if self._cookies_set:
            return
        try:
            resp = self._session.get(
                NSE_BASE_URL, timeout=REQUEST_TIMEOUT
            )
            resp.raise_for_status()
            self._cookies_set = True
            logger.info("NSE session cookies acquired")
        except requests.RequestException as exc:
            logger.error("Failed to obtain NSE session cookies: %s", exc)
            raise RuntimeError(
                "Could not establish a session with NSE India. "
                "The site may be temporarily unavailable."
            ) from exc

    def get(self, url: str) -> requests.Response:
        """GET *url* with valid NSE cookies, retrying cookie fetch once on 401/403."""
        self._ensure_cookies()
        resp = self._session.get(url, timeout=REQUEST_TIMEOUT)

        # If NSE returns 401/403 the cookies may have expired; retry once.
        if resp.status_code in (401, 403):
            logger.warning("NSE returned %s - refreshing cookies", resp.status_code)
            self._cookies_set = False
            self._ensure_cookies()
            resp = self._session.get(url, timeout=REQUEST_TIMEOUT)

        resp.raise_for_status()
        return resp


# Module-level session (reused across calls within the same process)
_nse_session: Optional[NSESession] = None


def _get_nse_session() -> NSESession:
    global _nse_session
    if _nse_session is None:
        _nse_session = NSESession()
    return _nse_session


def fetch_option_chain(symbol: str) -> Dict[str, Any]:
    """Fetch raw option chain JSON from NSE India for *symbol*.

    Returns the parsed JSON dict. Raises ``RuntimeError`` on failure.
    """
    symbol = symbol.strip().upper()
    url = NSE_OPTION_CHAIN_URL.format(symbol=symbol)
    session = _get_nse_session()

    try:
        resp = session.get(url)
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.error("Option chain fetch failed for %s: %s", symbol, exc)
        raise RuntimeError(
            f"Failed to fetch option chain for {symbol} from NSE India"
        ) from exc

    if "records" not in data or "data" not in data["records"]:
        raise RuntimeError(
            f"Unexpected option chain response structure for {symbol}"
        )

    return data


# ---------------------------------------------------------------------------
# 2.  Option Chain Analysis
# ---------------------------------------------------------------------------

def _parse_strikes(data: Dict[str, Any]) -> Tuple[
    List[Dict[str, Any]], float, List[float]
]:
    """Parse the NSE option chain response into a usable list.

    Returns:
        (strike_rows, underlying_price, expiry_dates)

    Each strike_row is a dict with keys:
        strike, ce_oi, ce_change_oi, ce_volume, ce_iv, ce_ltp, ce_bid, ce_ask,
        pe_oi, pe_change_oi, pe_volume, pe_iv, pe_ltp, pe_bid, pe_ask
    """
    records = data["records"]
    underlying = records.get("underlyingValue", 0.0)
    expiry_dates = records.get("expiryDates", [])

    rows: List[Dict[str, Any]] = []
    # Use the nearest expiry only (first in the expiryDates list)
    nearest_expiry = expiry_dates[0] if expiry_dates else None

    for entry in records["data"]:
        # Filter to nearest expiry for focused analysis
        if nearest_expiry and entry.get("expiryDate") != nearest_expiry:
            continue

        strike = entry.get("strikePrice", 0.0)
        ce = entry.get("CE", {})
        pe = entry.get("PE", {})

        rows.append({
            "strike": strike,
            "ce_oi": ce.get("openInterest", 0),
            "ce_change_oi": ce.get("changeinOpenInterest", 0),
            "ce_volume": ce.get("totalTradedVolume", 0),
            "ce_iv": ce.get("impliedVolatility", 0.0),
            "ce_ltp": ce.get("lastPrice", 0.0),
            "ce_bid": ce.get("bidprice", 0.0),
            "ce_ask": ce.get("askPrice", 0.0),
            "pe_oi": pe.get("openInterest", 0),
            "pe_change_oi": pe.get("changeinOpenInterest", 0),
            "pe_volume": pe.get("totalTradedVolume", 0),
            "pe_iv": pe.get("impliedVolatility", 0.0),
            "pe_ltp": pe.get("lastPrice", 0.0),
            "pe_bid": pe.get("bidprice", 0.0),
            "pe_ask": pe.get("askPrice", 0.0),
        })

    return rows, underlying, expiry_dates


def compute_max_pain(strikes: List[Dict[str, Any]]) -> float:
    """Calculate the max pain strike price.

    Max pain = the strike where the total value of in-the-money options
    (for both CE and PE buyers) is minimised — i.e., where option writers
    lose the least.
    """
    if not strikes:
        return 0.0

    min_pain = float("inf")
    max_pain_strike = 0.0

    for candidate in strikes:
        candidate_strike = candidate["strike"]
        total_pain = 0.0

        for row in strikes:
            strike = row["strike"]
            # CE buyer pain: if candidate > strike, CE is ITM
            if candidate_strike > strike:
                total_pain += (candidate_strike - strike) * row["ce_oi"]
            # PE buyer pain: if candidate < strike, PE is ITM
            if candidate_strike < strike:
                total_pain += (strike - candidate_strike) * row["pe_oi"]

        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = candidate_strike

    return max_pain_strike


def compute_pcr(strikes: List[Dict[str, Any]]) -> float:
    """Put-Call Ratio based on total open interest."""
    total_put_oi = sum(s["pe_oi"] for s in strikes)
    total_call_oi = sum(s["ce_oi"] for s in strikes)
    if total_call_oi == 0:
        return 0.0
    return round(total_put_oi / total_call_oi, 4)


def _top_oi_strikes(
    strikes: List[Dict[str, Any]], key: str, n: int = TOP_OI_STRIKES
) -> List[Dict[str, Any]]:
    """Return top *n* strikes sorted by *key* descending."""
    sorted_strikes = sorted(strikes, key=lambda s: s.get(key, 0), reverse=True)
    return [
        {"strike": s["strike"], "oi": s[key], "change_oi": s.get(key.replace("_oi", "_change_oi"), 0)}
        for s in sorted_strikes[:n]
    ]


def _interpret_pcr(pcr: float) -> str:
    if pcr >= 1.5:
        return "Very Bullish — heavy put writing indicates strong support from option sellers"
    if pcr >= 1.0:
        return "Bullish — more puts than calls suggests writers are providing support"
    if pcr >= 0.7:
        return "Neutral — balanced put-call activity"
    if pcr >= 0.5:
        return "Bearish — low put writing suggests weak downside support"
    return "Very Bearish — extremely low put interest, no downside cushion"


def _interpret_max_pain(max_pain: float, current_price: float) -> str:
    diff_pct = ((max_pain - current_price) / current_price) * 100 if current_price else 0
    if abs(diff_pct) < 1.0:
        return f"Max pain at {max_pain:.0f} is near current price — price likely to stay range-bound near expiry"
    if diff_pct > 0:
        return f"Max pain at {max_pain:.0f} is {diff_pct:.1f}% above current price — upward pull expected towards expiry"
    return f"Max pain at {max_pain:.0f} is {abs(diff_pct):.1f}% below current price — downward pressure expected towards expiry"


def _oi_buildup_signal(strikes: List[Dict[str, Any]], current_price: float) -> str:
    """Analyze change in OI to determine where smart money is positioning."""
    # Find the biggest CE OI buildup above current price (resistance building)
    ce_above = [s for s in strikes if s["strike"] > current_price and s["ce_change_oi"] > 0]
    pe_below = [s for s in strikes if s["strike"] < current_price and s["pe_change_oi"] > 0]

    ce_buildup = sum(s["ce_change_oi"] for s in ce_above)
    pe_buildup = sum(s["pe_change_oi"] for s in pe_below)

    if ce_buildup > pe_buildup * 1.5:
        return "Heavy call writing above CMP — strong resistance being built, bearish bias"
    if pe_buildup > ce_buildup * 1.5:
        return "Heavy put writing below CMP — strong support being built, bullish bias"
    if ce_buildup > 0 and pe_buildup > 0:
        return "Balanced OI buildup on both sides — range-bound movement expected"
    return "Low OI change — no strong directional signal from option writers"


def _iv_analysis(strikes: List[Dict[str, Any]], current_price: float) -> str:
    """Analyze IV skew for directional bias."""
    # Find ATM strike
    atm_strike = min(strikes, key=lambda s: abs(s["strike"] - current_price)) if strikes else None
    if atm_strike is None:
        return "Insufficient data for IV analysis"

    atm_iv_ce = atm_strike["ce_iv"]
    atm_iv_pe = atm_strike["pe_iv"]

    # OTM puts (below current price) and OTM calls (above current price)
    otm_puts = [s for s in strikes if s["strike"] < current_price and s["pe_iv"] > 0]
    otm_calls = [s for s in strikes if s["strike"] > current_price and s["ce_iv"] > 0]

    avg_otm_put_iv = np.mean([s["pe_iv"] for s in otm_puts]) if otm_puts else 0
    avg_otm_call_iv = np.mean([s["ce_iv"] for s in otm_calls]) if otm_calls else 0

    parts = []
    if atm_iv_ce > 0 or atm_iv_pe > 0:
        atm_avg = (atm_iv_ce + atm_iv_pe) / 2 if (atm_iv_ce > 0 and atm_iv_pe > 0) else max(atm_iv_ce, atm_iv_pe)
        parts.append(f"ATM IV: {atm_avg:.1f}%")

    if avg_otm_put_iv > avg_otm_call_iv * 1.2:
        parts.append("Put IV skew detected — market pricing in downside risk (fear premium)")
    elif avg_otm_call_iv > avg_otm_put_iv * 1.2:
        parts.append("Call IV skew detected — market pricing in upside move")
    else:
        parts.append("IV skew is balanced — no strong directional fear")

    return ". ".join(parts)


def analyze_option_chain(symbol: str) -> Dict[str, Any]:
    """Full option chain analysis for *symbol*.

    Returns a dict with: pcr, max_pain, supports, resistances,
    oi_buildup_signal, iv_analysis, and raw strike data.
    """
    data = fetch_option_chain(symbol)
    strikes, underlying, expiry_dates = _parse_strikes(data)

    if not strikes:
        raise RuntimeError(f"No option chain strike data available for {symbol}")

    pcr = compute_pcr(strikes)
    max_pain = compute_max_pain(strikes)

    highest_put_oi = _top_oi_strikes(strikes, "pe_oi")
    highest_call_oi = _top_oi_strikes(strikes, "ce_oi")

    return {
        "underlying_price": underlying,
        "nearest_expiry": expiry_dates[0] if expiry_dates else None,
        "pcr": pcr,
        "pcr_interpretation": _interpret_pcr(pcr),
        "max_pain": max_pain,
        "max_pain_interpretation": _interpret_max_pain(max_pain, underlying),
        "highest_put_oi_strikes": highest_put_oi,
        "highest_call_oi_strikes": highest_call_oi,
        "oi_buildup_signal": _oi_buildup_signal(strikes, underlying),
        "iv_analysis": _iv_analysis(strikes, underlying),
        "total_ce_oi": sum(s["ce_oi"] for s in strikes),
        "total_pe_oi": sum(s["pe_oi"] for s in strikes),
        "strike_count": len(strikes),
    }


# ---------------------------------------------------------------------------
# 3.  Action Recommendation Engine
# ---------------------------------------------------------------------------

def _safe_val(d: dict, key: str, default: float = 0.0) -> float:
    """Safely extract a float from a dict, handling None/NaN."""
    v = d.get(key)
    if v is None:
        return default
    try:
        f = float(v)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return default


def _collect_supports(
    indicators: Dict[str, Any],
    oc_analysis: Dict[str, Any],
    current_price: float,
) -> List[Dict[str, Any]]:
    """Gather support levels from multiple sources, filtered below current price."""
    supports: List[Dict[str, Any]] = []

    # Pivot point supports
    for key, label in [("S1", "Pivot S1"), ("S2", "Pivot S2"), ("S3", "Pivot S3")]:
        val = _safe_val(indicators, key)
        if 0 < val < current_price:
            strength = "strong" if "S3" in key else ("moderate" if "S2" in key else "weak")
            supports.append({"level": round(val, 2), "strength": strength, "source": label})

    # Fibonacci supports (Fib_S1, Fib_S2, Fib_S3)
    for key, label in [("Fib_S1", "Fibonacci S1"), ("Fib_S2", "Fibonacci S2"), ("Fib_S3", "Fibonacci S3")]:
        val = _safe_val(indicators, key)
        if 0 < val < current_price:
            supports.append({"level": round(val, 2), "strength": "moderate", "source": label})

    # Fibonacci retracement levels
    for key in ["Fib_23_6", "Fib_38_2", "Fib_50_0", "Fib_61_8", "Fib_78_6"]:
        val = _safe_val(indicators, key)
        if 0 < val < current_price:
            supports.append({"level": round(val, 2), "strength": "moderate", "source": f"Fibonacci {key.replace('Fib_', '').replace('_', '.')}%"})

    # Bollinger lower band
    bb_lower = _safe_val(indicators, "BB_Lower")
    if 0 < bb_lower < current_price:
        supports.append({"level": round(bb_lower, 2), "strength": "moderate", "source": "Bollinger Lower Band"})

    # SMA supports (key moving averages acting as support)
    for key, label in [("SMA_20", "SMA 20"), ("SMA_50", "SMA 50"), ("SMA_200", "SMA 200")]:
        val = _safe_val(indicators, key)
        if 0 < val < current_price:
            strength = "strong" if "200" in key else "moderate"
            supports.append({"level": round(val, 2), "strength": strength, "source": label})

    # Option chain: highest put OI strikes (where put writers provide support)
    for entry in oc_analysis.get("highest_put_oi_strikes", []):
        strike = entry["strike"]
        if 0 < strike < current_price:
            oi = entry.get("oi", 0)
            strength = "strong" if oi > 0 else "moderate"
            supports.append({"level": round(strike, 2), "strength": strength, "source": f"Put OI ({oi:,})"})

    # If no supports below CMP found, include nearby levels slightly above CMP
    # (within 5%) as "recovery zone" supports — price may bounce back to these
    if not supports:
        all_candidates: List[Dict[str, Any]] = []
        threshold = current_price * 1.05
        for key, label in [("S1", "Pivot S1"), ("S2", "Pivot S2"), ("S3", "Pivot S3")]:
            val = _safe_val(indicators, key)
            if 0 < val <= threshold:
                all_candidates.append({"level": round(val, 2), "strength": "weak", "source": f"{label} (nearby)"})
        for key, label in [("BB_Lower", "Bollinger Lower Band"), ("SMA_20", "SMA 20"), ("SMA_50", "SMA 50")]:
            val = _safe_val(indicators, key)
            if 0 < val <= threshold:
                all_candidates.append({"level": round(val, 2), "strength": "weak", "source": f"{label} (nearby)"})
        for key in ["Fib_23_6", "Fib_38_2", "Fib_50_0"]:
            val = _safe_val(indicators, key)
            if 0 < val <= threshold:
                all_candidates.append({"level": round(val, 2), "strength": "weak", "source": f"Fibonacci {key.replace('Fib_', '').replace('_', '.')}% (nearby)"})
        supports.extend(all_candidates)

    # Always add ATR-based estimated supports as a fallback
    atr = _safe_val(indicators, "ATR", current_price * 0.02)
    if not supports and atr > 0:
        supports.append({"level": round(current_price - atr, 2), "strength": "weak", "source": "ATR-based S1"})
        supports.append({"level": round(current_price - 2 * atr, 2), "strength": "weak", "source": "ATR-based S2"})
        supports.append({"level": round(current_price - 3 * atr, 2), "strength": "moderate", "source": "ATR-based S3"})

    # Sort by level descending (nearest support first)
    supports.sort(key=lambda s: s["level"], reverse=True)

    # Deduplicate close levels (within 0.5%)
    deduped: List[Dict[str, Any]] = []
    for s in supports:
        if not deduped or abs(s["level"] - deduped[-1]["level"]) / deduped[-1]["level"] > 0.005:
            deduped.append(s)

    return deduped


def _collect_resistances(
    indicators: Dict[str, Any],
    oc_analysis: Dict[str, Any],
    current_price: float,
) -> List[Dict[str, Any]]:
    """Gather resistance levels from multiple sources, filtered above current price."""
    resistances: List[Dict[str, Any]] = []

    # Pivot point resistances
    for key, label in [("R1", "Pivot R1"), ("R2", "Pivot R2"), ("R3", "Pivot R3")]:
        val = _safe_val(indicators, key)
        if val > current_price:
            strength = "strong" if "R3" in key else ("moderate" if "R2" in key else "weak")
            resistances.append({"level": round(val, 2), "strength": strength, "source": label})

    # Fibonacci resistances (Fib_R1, Fib_R2, Fib_R3)
    for key, label in [("Fib_R1", "Fibonacci R1"), ("Fib_R2", "Fibonacci R2"), ("Fib_R3", "Fibonacci R3")]:
        val = _safe_val(indicators, key)
        if val > current_price:
            resistances.append({"level": round(val, 2), "strength": "moderate", "source": label})

    # Fibonacci retracement levels above price
    for key in ["Fib_23_6", "Fib_38_2", "Fib_50_0", "Fib_61_8", "Fib_78_6"]:
        val = _safe_val(indicators, key)
        if val > current_price:
            resistances.append({"level": round(val, 2), "strength": "moderate", "source": f"Fibonacci {key.replace('Fib_', '').replace('_', '.')}%"})

    # Bollinger upper band
    bb_upper = _safe_val(indicators, "BB_Upper")
    if bb_upper > current_price:
        resistances.append({"level": round(bb_upper, 2), "strength": "moderate", "source": "Bollinger Upper Band"})

    # Option chain: highest call OI strikes (where call writers cap upside)
    for entry in oc_analysis.get("highest_call_oi_strikes", []):
        strike = entry["strike"]
        if strike > current_price:
            oi = entry.get("oi", 0)
            strength = "strong" if oi > 0 else "moderate"
            resistances.append({"level": round(strike, 2), "strength": strength, "source": f"Call OI ({oi:,})"})

    # Sort ascending (nearest resistance first)
    resistances.sort(key=lambda s: s["level"])

    # Deduplicate close levels (within 0.5%)
    deduped: List[Dict[str, Any]] = []
    for r in resistances:
        if not deduped or abs(r["level"] - deduped[-1]["level"]) / deduped[-1]["level"] > 0.005:
            deduped.append(r)

    return deduped


def _compute_action(
    composite_score: float,
    pcr: float,
    current_price: float,
    max_pain: float,
    supports: List[Dict[str, Any]],
    resistances: List[Dict[str, Any]],
    rsi: float,
    macd: float,
    macd_signal: float,
) -> Tuple[str, float, List[str]]:
    """Determine action (BUY/SELL/HOLD), confidence 0-100, and reasoning bullets.

    Combines:
    - Composite signal score (-100 to +100)
    - PCR interpretation
    - Max pain pull direction
    - RSI / MACD conditions
    - Price position relative to supports / resistances
    """
    score = 0.0  # -100 to +100 internal tally
    reasoning: List[str] = []

    # --- Composite signal (40% weight) ---
    score += composite_score * 0.4
    if composite_score >= 60:
        reasoning.append(f"Strong bullish composite signal ({composite_score:.1f})")
    elif composite_score >= 30:
        reasoning.append(f"Bullish composite signal ({composite_score:.1f})")
    elif composite_score <= -60:
        reasoning.append(f"Strong bearish composite signal ({composite_score:.1f})")
    elif composite_score <= -30:
        reasoning.append(f"Bearish composite signal ({composite_score:.1f})")
    else:
        reasoning.append(f"Neutral composite signal ({composite_score:.1f})")

    # --- PCR (15% weight) ---
    if pcr >= 1.0:
        pcr_score = min((pcr - 0.7) * 100, 100)  # bullish
        reasoning.append(f"PCR {pcr:.2f} — put writers providing support (bullish)")
    elif pcr >= 0.7:
        pcr_score = 0
        reasoning.append(f"PCR {pcr:.2f} — neutral put-call balance")
    else:
        pcr_score = max((pcr - 0.7) * 150, -100)  # bearish
        reasoning.append(f"PCR {pcr:.2f} — low put support (bearish)")
    score += pcr_score * 0.15

    # --- Max pain direction (10% weight) ---
    if current_price > 0:
        mp_diff_pct = ((max_pain - current_price) / current_price) * 100
        if mp_diff_pct > 1:
            score += 10
            reasoning.append(f"Max pain {max_pain:.0f} is above CMP — upward pull likely")
        elif mp_diff_pct < -1:
            score -= 10
            reasoning.append(f"Max pain {max_pain:.0f} is below CMP — downward pressure likely")
        else:
            reasoning.append(f"Max pain {max_pain:.0f} near CMP — range-bound near expiry")

    # --- RSI (15% weight) ---
    if rsi > 0:
        if rsi < 30:
            score += 15
            reasoning.append(f"RSI {rsi:.1f} — oversold, bounce potential")
        elif rsi > 70:
            score -= 15
            reasoning.append(f"RSI {rsi:.1f} — overbought, correction risk")
        elif rsi < 45:
            score += 5
            reasoning.append(f"RSI {rsi:.1f} — mildly oversold")
        elif rsi > 55:
            score -= 5
            reasoning.append(f"RSI {rsi:.1f} — mildly overbought")
        else:
            reasoning.append(f"RSI {rsi:.1f} — neutral zone")

    # --- MACD (10% weight) ---
    if macd != 0 and macd_signal != 0:
        if macd > macd_signal:
            score += 10
            reasoning.append("MACD above signal line — bullish momentum")
        else:
            score -= 10
            reasoning.append("MACD below signal line — bearish momentum")

    # --- Support / Resistance proximity (10% weight) ---
    if supports:
        nearest_sup = supports[0]["level"]
        dist_to_support = ((current_price - nearest_sup) / current_price) * 100
        if dist_to_support < 2:
            score += 10
            reasoning.append(f"Price near support {nearest_sup:.0f} ({dist_to_support:.1f}% away) — good risk-reward for buying")
        elif dist_to_support < 5:
            score += 5
            reasoning.append(f"Support at {nearest_sup:.0f} provides a safety net")

    if resistances:
        nearest_res = resistances[0]["level"]
        dist_to_resistance = ((nearest_res - current_price) / current_price) * 100
        if dist_to_resistance < 1:
            score -= 10
            reasoning.append(f"Price near resistance {nearest_res:.0f} — limited upside in short term")
        elif dist_to_resistance > 5:
            score += 5
            reasoning.append(f"Good upside room to resistance at {nearest_res:.0f} ({dist_to_resistance:.1f}% away)")

    # Clamp final score
    score = max(-100, min(100, score))

    # Map score to action
    if score >= 25:
        action = "BUY"
    elif score <= -25:
        action = "SELL"
    else:
        action = "HOLD"

    # Confidence: distance from zero in the score, mapped 0-100
    confidence = min(abs(score), 100)

    return action, round(confidence, 1), reasoning


def _compute_targets(
    action: str,
    current_price: float,
    supports: List[Dict[str, Any]],
    resistances: List[Dict[str, Any]],
    atr: float,
) -> Dict[str, Any]:
    """Compute buy range, sell targets, and stop loss."""
    # Default fallbacks using ATR
    atr_val = atr if atr > 0 else current_price * 0.02  # fallback 2%

    # --- Buy range ---
    if supports:
        buy_low = supports[0]["level"]
    else:
        buy_low = round(current_price - atr_val, 2)

    buy_high = round(current_price, 2)
    if action == "SELL":
        # For sell, buy range is less meaningful; still provide it
        buy_low = round(current_price - 2 * atr_val, 2)
        buy_high = round(current_price - atr_val, 2)

    # --- Sell targets ---
    sell_targets: List[Dict[str, Any]] = []
    if resistances:
        for i, r in enumerate(resistances[:3]):
            sell_targets.append({"target": r["level"], "label": f"Target {i + 1} ({r['source']})"})

    # If fewer than 3 targets, add Fibonacci extension estimates
    if len(sell_targets) < 3 and current_price > 0:
        if supports:
            swing_range = current_price - supports[0]["level"]
        else:
            swing_range = atr_val * 3

        extensions = [1.272, 1.618, 2.0]
        idx = len(sell_targets) + 1
        for ext in extensions:
            if len(sell_targets) >= 3:
                break
            target = round(current_price + swing_range * ext, 2)
            # Only add if not too close to existing targets
            if not sell_targets or target > sell_targets[-1]["target"] * 1.005:
                sell_targets.append({"target": target, "label": f"Target {idx} (Fib Ext {ext}x)"})
                idx += 1

    # --- Stop loss ---
    if supports:
        # Place stop just below nearest strong support or 2xATR below entry
        strong_supports = [s for s in supports if s["strength"] == "strong"]
        if strong_supports:
            stop_loss = round(strong_supports[0]["level"] - atr_val * 0.5, 2)
        else:
            stop_loss = round(supports[0]["level"] - atr_val * 0.5, 2)
    else:
        stop_loss = round(current_price - 2 * atr_val, 2)

    return {
        "buy_range": {"low": round(buy_low, 2), "high": round(buy_high, 2)},
        "sell_targets": sell_targets,
        "stop_loss": round(stop_loss, 2),
    }


# ---------------------------------------------------------------------------
# 4.  Main Public API — get_action_recommendation
# ---------------------------------------------------------------------------

def get_action_recommendation(
    symbol: str,
    df,  # pandas DataFrame with OHLCV
    signal_result,  # SignalResult from signal_engine
    indicator_values: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate a full action recommendation for *symbol*.

    Parameters
    ----------
    symbol : str
        NSE stock symbol (e.g. ``'RELIANCE'``).
    df : pd.DataFrame
        OHLCV DataFrame (used for ATR and current price).
    signal_result : SignalResult
        Output from ``SignalEngine.compute_signal()``.
    indicator_values : dict
        The ``latest`` dict from ``IndicatorEngine.compute_all()``.

    Returns
    -------
    dict
        Full recommendation payload with action, confidence, targets,
        supports, resistances, option chain analysis, reasoning, and
        disclaimer.
    """
    current_price = float(df["Close"].iloc[-1])
    atr = _safe_val(indicator_values, "ATR", current_price * 0.02)

    # Fetch and analyse option chain
    try:
        oc_analysis = analyze_option_chain(symbol)
    except Exception as exc:
        logger.warning("Option chain analysis failed for %s: %s — proceeding without it", symbol, exc)
        oc_analysis = {
            "underlying_price": current_price,
            "nearest_expiry": None,
            "pcr": 0.0,
            "pcr_interpretation": "Option chain data unavailable",
            "max_pain": 0.0,
            "max_pain_interpretation": "Option chain data unavailable",
            "highest_put_oi_strikes": [],
            "highest_call_oi_strikes": [],
            "oi_buildup_signal": "Option chain data unavailable",
            "iv_analysis": "Option chain data unavailable",
            "total_ce_oi": 0,
            "total_pe_oi": 0,
            "strike_count": 0,
        }

    # Collect supports & resistances
    supports = _collect_supports(indicator_values, oc_analysis, current_price)
    resistances = _collect_resistances(indicator_values, oc_analysis, current_price)

    # Extract key indicators
    rsi = _safe_val(indicator_values, "RSI")
    macd = _safe_val(indicator_values, "MACD")
    macd_signal = _safe_val(indicator_values, "MACD_Signal")

    # Determine action, confidence, reasoning
    action, confidence, reasoning = _compute_action(
        composite_score=signal_result.composite_score,
        pcr=oc_analysis["pcr"],
        current_price=current_price,
        max_pain=oc_analysis["max_pain"],
        supports=supports,
        resistances=resistances,
        rsi=rsi,
        macd=macd,
        macd_signal=macd_signal,
    )

    # Compute targets
    targets = _compute_targets(action, current_price, supports, resistances, atr)

    # Compute holding period based on action and confidence
    if action == "BUY":
        if confidence < 50:
            holding_period = "Short-term (1-2 weeks)"
        elif confidence <= 75:
            holding_period = "Medium-term (2-4 weeks)"
        else:
            holding_period = "Swing (1-3 months)"
    elif action == "SELL":
        holding_period = "Exit within 1-3 days"
    else:
        holding_period = "Continue holding"

    return {
        "action": action,
        "confidence": confidence,
        "holding_period": holding_period,
        "current_price": round(current_price, 2),
        "buy_range": targets["buy_range"],
        "sell_targets": targets["sell_targets"],
        "stop_loss": targets["stop_loss"],
        "supports": supports,
        "resistances": resistances,
        "option_chain_analysis": {
            "pcr": oc_analysis["pcr"],
            "pcr_interpretation": oc_analysis["pcr_interpretation"],
            "max_pain": oc_analysis["max_pain"],
            "max_pain_interpretation": oc_analysis["max_pain_interpretation"],
            "highest_put_oi_strikes": oc_analysis["highest_put_oi_strikes"],
            "highest_call_oi_strikes": oc_analysis["highest_call_oi_strikes"],
            "oi_buildup_signal": oc_analysis["oi_buildup_signal"],
            "iv_analysis": oc_analysis["iv_analysis"],
        },
        "signal_summary": {
            "composite_score": signal_result.composite_score,
            "signal": signal_result.signal,
            "trend_score": signal_result.trend_score,
            "momentum_score": signal_result.momentum_score,
        },
        "key_indicators": {
            "rsi": round(rsi, 2) if rsi else None,
            "macd": round(macd, 4) if macd else None,
            "macd_signal": round(macd_signal, 4) if macd_signal else None,
            "atr": round(atr, 2),
            "bb_upper": round(_safe_val(indicator_values, "BB_Upper"), 2) or None,
            "bb_lower": round(_safe_val(indicator_values, "BB_Lower"), 2) or None,
        },
        "reasoning": reasoning,
        "disclaimer": (
            "This is for educational purposes only. Not SEBI-registered investment advice."
        ),
    }
