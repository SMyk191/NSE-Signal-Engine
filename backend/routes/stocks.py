from __future__ import annotations

"""
NSE Signal Engine - Stock API Routes

Provides endpoints for individual stock analysis: prices, indicators,
composite signals, sentiment, earnings, and risk metrics.
"""

import asyncio
import logging
import re
from functools import lru_cache
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request

from config import NIFTY50_STOCKS, to_yfinance_symbol, is_valid_symbol
from services.data_fetcher import fetch_ohlcv, fetch_fundamentals, get_cached_or_fetch
from services.indicators import IndicatorEngine
from services.signal_engine import SignalEngine
from services.sentiment_analyzer import SentimentAnalyzer
from services.earnings_predictor import EarningsPredictor
from services.risk_engine import (
    compute_var,
    compute_performance_ratios,
    max_drawdown,
    position_sizing,
    compute_atr,
)
from services.option_chain import get_action_recommendation
from services.auth import get_current_user, record_activity

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Activity tracking helper
# ---------------------------------------------------------------------------
async def track_activity(request: Request, action: str, details: str = None):
    """Track user activity if authenticated. Non-blocking, doesn't fail the request."""
    try:
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if token:
            user = get_current_user(token)
            if user:
                record_activity(user["id"], action, details, request.client.host)
    except Exception:
        pass  # Never fail the request due to tracking

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

# Shared service instances (initialized once, reused across requests)
signal_engine = SignalEngine()
sentiment_analyzer = SentimentAnalyzer()
earnings_predictor = EarningsPredictor()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def validate_symbol(symbol: str) -> str:
    """Validate symbol format. Accepts ANY NSE/BSE symbol, not just NIFTY 50.

    - If symbol is in the NIFTY50 dict, it's a known-good symbol.
    - Otherwise, accept it as long as the format is plausible (letters,
      digits, &, hyphens). yfinance will handle real validation when data
      is fetched.
    - Reject obviously invalid input (empty, too long, special chars).
    """
    symbol = symbol.strip().upper()
    if symbol in NIFTY50_STOCKS:
        return symbol
    if not is_valid_symbol(symbol):
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol}' has an invalid format. "
                   f"Use a valid NSE/BSE ticker symbol (e.g. RELIANCE, IRCTC, ZOMATO).",
        )
    return symbol


def _safe_float(value) -> Optional[float]:
    """Convert numpy/pandas types to Python float, handling NaN."""
    if value is None:
        return None
    try:
        f = float(value)
        if np.isnan(f) or np.isinf(f):
            return None
        return round(f, 4)
    except (TypeError, ValueError):
        return None


def _map_indicators_for_signal(latest: dict, df: pd.DataFrame) -> dict:
    """Map IndicatorEngine output keys to the lowercase keys expected by SignalEngine."""
    sf = lambda k: _safe_float(latest.get(k))

    close = float(df["Close"].iloc[-1])
    prev_close = float(df["Close"].iloc[-2]) if len(df) >= 2 else close

    # Ichimoku cloud detection
    senkou_a = sf("Ichimoku_SenkouA")
    senkou_b = sf("Ichimoku_SenkouB")
    above_cloud = None
    if senkou_a is not None and senkou_b is not None:
        cloud_top = max(senkou_a, senkou_b)
        above_cloud = close > cloud_top

    # Supertrend direction
    st_dir = sf("Supertrend_Direction")
    supertrend_bullish = st_dir == 1.0 if st_dir is not None else None

    # OBV vs SMA of OBV
    obv = sf("OBV")
    obv_sma20 = None
    if "OBV" in latest and hasattr(df, "columns"):
        try:
            engine_tmp = IndicatorEngine(df)
            obv_series = engine_tmp.obv()
            obv_sma20 = float(obv_series.rolling(20).mean().iloc[-1])
        except Exception:
            pass

    # Volume ratio
    vol = float(df["Volume"].iloc[-1]) if "Volume" in df.columns else None
    avg_vol_20 = float(df["Volume"].tail(20).mean()) if "Volume" in df.columns else None
    vol_ratio = vol / avg_vol_20 if vol and avg_vol_20 and avg_vol_20 > 0 else None

    # Candlestick patterns as sub-dict for pattern scorer
    candlestick_patterns = {}
    pattern_map = {
        "Doji": "doji", "Hammer": "hammer", "Inverted_Hammer": "inverted_hammer",
        "Bullish_Engulfing": "bullish_engulfing", "Bearish_Engulfing": "bearish_engulfing",
        "Morning_Star": "morning_star", "Evening_Star": "evening_star",
        "Three_White_Soldiers": "three_white_soldiers", "Three_Black_Crows": "three_black_crows",
        "Spinning_Top": "spinning_top", "Marubozu_Bullish": "marubozu_bullish",
        "Marubozu_Bearish": "marubozu_bearish", "Harami_Bullish": "harami_bullish",
        "Harami_Bearish": "harami_bearish",
    }
    for indicator_key, pattern_key in pattern_map.items():
        val = latest.get(indicator_key)
        if val and val != 0:
            candlestick_patterns[pattern_key] = True

    return {
        "price": close,
        "prev_close": prev_close,
        # Trend
        "sma20": sf("SMA_20"),
        "sma50": sf("SMA_50"),
        "sma200": sf("SMA_200"),
        "ema12": sf("EMA_12"),
        "ema26": sf("EMA_26"),
        "macd": sf("MACD"),
        "macd_signal": sf("MACD_Signal"),
        "macd_hist": sf("MACD_Histogram"),
        "macd_hist_prev": None,
        "above_ichimoku_cloud": above_cloud,
        "supertrend_bullish": supertrend_bullish,
        "adx": sf("ADX"),
        "plus_di": sf("Plus_DI"),
        "minus_di": sf("Minus_DI"),
        # Momentum
        "rsi": sf("RSI"),
        "stoch_k": sf("Stoch_K"),
        "stoch_d": sf("Stoch_D"),
        "stoch_k_prev": None,
        "stoch_d_prev": None,
        "williams_r": sf("Williams_R"),
        "cci": sf("CCI"),
        "cci_prev": None,
        "bullish_divergence": False,
        "bearish_divergence": False,
        # Volatility
        "atr": sf("ATR"),
        "bb_upper": sf("BB_Upper"),
        "bb_mid": sf("BB_Middle"),
        "bb_lower": sf("BB_Lower"),
        "bb_width": sf("BB_Bandwidth"),
        "bb_width_prev": None,
        "atr_prev": None,
        "historical_volatility": sf("HV_20"),
        # Volume
        "obv": obv,
        "obv_sma20": obv_sma20,
        "cmf": sf("CMF"),
        "mfi": sf("MFI"),
        "vroc": sf("Volume_ROC"),
        "volume_ratio": vol_ratio,
        # Patterns
        "candlestick_patterns": candlestick_patterns,
        "chart_patterns": {},
        # Statistical
        "price_zscore": sf("Z_Score"),
        "hurst_exponent": sf("Hurst"),
        "linear_reg_slope": sf("LinReg_Angle"),
        "linreg_r2": sf("LinReg_R2"),
    }


def _series_to_json(series: pd.Series, max_points: int = 500) -> list:
    """Convert a pandas Series to a JSON-serializable list of {date, value} dicts."""
    if series is None or series.empty:
        return []
    clean = series.dropna().tail(max_points)
    return [
        {"date": str(idx.date()) if hasattr(idx, "date") else str(idx), "value": _safe_float(v)}
        for idx, v in clean.items()
    ]


def _df_to_ohlcv_json(df: pd.DataFrame) -> list:
    """Convert OHLCV DataFrame to a list of dicts."""
    records = []
    for idx, row in df.iterrows():
        records.append({
            "date": str(idx.date()) if hasattr(idx, "date") else str(idx),
            "open": _safe_float(row.get("Open")),
            "high": _safe_float(row.get("High")),
            "low": _safe_float(row.get("Low")),
            "close": _safe_float(row.get("Close")),
            "volume": int(row.get("Volume", 0)),
            "adj_close": _safe_float(row.get("Adj Close", row.get("Close"))),
        })
    return records


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_all_stocks():
    """
    GET /api/stocks
    List all NIFTY 50 stocks with current price, change%, and composite signal.
    """
    results = []
    loop = asyncio.get_running_loop()

    async def _process_symbol(sym: str):
        try:
            df = await get_cached_or_fetch(sym)
            if df is None or df.empty or len(df) < 2:
                return None

            latest_close = float(df["Close"].iloc[-1])
            prev_close = float(df["Close"].iloc[-2])
            change_pct = ((latest_close - prev_close) / prev_close) * 100

            # Compute indicators and signal
            engine = IndicatorEngine(df)
            all_indicators = engine.compute_all()
            latest_vals = all_indicators["latest"]
            signal_result = signal_engine.compute_signal(sym, _map_indicators_for_signal(latest_vals, df))

            return {
                "symbol": sym,
                "sector": NIFTY50_STOCKS.get(sym, "Unknown"),
                "price": round(latest_close, 2),
                "change_pct": round(change_pct, 2),
                "composite_score": signal_result.composite_score,
                "signal": signal_result.signal,
            }
        except Exception as e:
            logger.error("Error processing %s: %s", sym, e)
            return {
                "symbol": sym,
                "sector": NIFTY50_STOCKS.get(sym, "Unknown"),
                "price": None,
                "change_pct": None,
                "composite_score": None,
                "signal": "ERROR",
                "error": str(e),
            }

    tasks = [_process_symbol(sym) for sym in sorted(NIFTY50_STOCKS.keys())]
    processed = await asyncio.gather(*tasks, return_exceptions=True)

    for item in processed:
        if isinstance(item, Exception):
            logger.error("Gather exception: %s", item)
            continue
        if item is not None:
            results.append(item)

    return {"count": len(results), "stocks": results}


# ---------------------------------------------------------------------------
# In-memory cache for yfinance symbol lookups (avoids repeated API calls)
# ---------------------------------------------------------------------------
_search_cache: Dict[str, Optional[Dict]] = {}


def _yf_lookup(query: str) -> Optional[Dict]:
    """Look up a symbol via yfinance. Returns {symbol, name, exchange} or None."""
    if query in _search_cache:
        return _search_cache[query]
    try:
        import yfinance as yf
        ticker = yf.Ticker(query + ".NS")
        info = ticker.info or {}
        short_name = info.get("shortName")
        if short_name:
            result = {
                "symbol": query.upper(),
                "name": short_name,
                "exchange": "NSE",
            }
            _search_cache[query] = result
            return result
    except Exception:
        pass
    _search_cache[query] = None
    return None


# ---------------------------------------------------------------------------
# All-NSE stock cache
# ---------------------------------------------------------------------------
import requests as _requests
import time as _time

_all_nse_stocks: List[Dict] = []
_all_nse_fetched_at: float = 0
_ALL_NSE_TTL = 86400  # refresh once per day


def _fetch_all_nse_stocks() -> List[Dict]:
    """Fetch all NSE-listed equities from NSE India pre-open API. Cached for 24h."""
    global _all_nse_stocks, _all_nse_fetched_at

    if _all_nse_stocks and (_time.time() - _all_nse_fetched_at) < _ALL_NSE_TTL:
        return _all_nse_stocks

    try:
        session = _requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        })
        session.get("https://www.nseindia.com", timeout=10)
        resp = session.get(
            "https://www.nseindia.com/api/market-data-pre-open?key=ALL",
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])

        stocks = []
        seen = set()
        for item in data:
            meta = item.get("metadata", {})
            sym = meta.get("symbol", "").strip()
            name = meta.get("companyName") or meta.get("identifier") or sym
            if sym and sym not in seen:
                seen.add(sym)
                stocks.append({
                    "symbol": sym,
                    "name": name,
                    "exchange": "NSE",
                    "in_nifty50": sym in NIFTY50_STOCKS,
                })

        if stocks:
            _all_nse_stocks = stocks
            _all_nse_fetched_at = _time.time()
            logger.info("Loaded %d NSE stocks from market data", len(stocks))
        return _all_nse_stocks
    except Exception as e:
        logger.warning("Failed to fetch NSE stock list: %s", e)
        # Fallback: return whatever we have cached, or NIFTY 50
        if _all_nse_stocks:
            return _all_nse_stocks
        return [
            {"symbol": sym, "name": sym, "exchange": "NSE", "in_nifty50": True}
            for sym in NIFTY50_STOCKS
        ]


@router.get("/all")
async def get_all_nse_stocks():
    """
    GET /api/stocks/all
    Returns all NSE-listed stocks (2000+). Cached for 24 hours.
    """
    loop = asyncio.get_running_loop()
    stocks = await loop.run_in_executor(None, _fetch_all_nse_stocks)
    return {"count": len(stocks), "stocks": stocks}


@router.get("/search")
async def search_stocks(
    q: str = Query(..., min_length=1, description="Search query (symbol or company name)"),
):
    """
    GET /api/stocks/search?q=IRCTC
    Search across ALL 2000+ NSE-listed stocks by symbol or company name.
    Returns up to 20 matches.
    """
    query = q.strip().upper()
    query_lower = q.strip().lower()

    # Get the full stock list
    loop = asyncio.get_running_loop()
    all_stocks = await loop.run_in_executor(None, _fetch_all_nse_stocks)

    # Score-based search: exact prefix match > contains symbol > contains name
    exact = []
    prefix = []
    contains = []

    for stock in all_stocks:
        sym = stock["symbol"].upper()
        name_lower = stock.get("name", "").lower()

        if sym == query:
            exact.append(stock)
        elif sym.startswith(query):
            prefix.append(stock)
        elif query in sym or query_lower in name_lower:
            contains.append(stock)

    matches = exact + prefix + contains

    # If no matches in NSE list and looks valid, try yfinance as fallback
    if not matches and is_valid_symbol(query):
        result = await loop.run_in_executor(None, _yf_lookup, query)
        if result:
            result["in_nifty50"] = False
            matches.append(result)

    return {"query": q, "count": len(matches[:20]), "results": matches[:20]}


@router.get("/{symbol}")
async def get_stock_detail(symbol: str):
    """
    GET /api/stocks/{symbol}
    Full analysis for a single stock: price, indicators summary, signal, fundamentals.
    """
    symbol = validate_symbol(symbol)

    try:
        df = await get_cached_or_fetch(symbol)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No OHLCV data available for {symbol}")

        # Price info
        latest_close = float(df["Close"].iloc[-1])
        prev_close = float(df["Close"].iloc[-2]) if len(df) >= 2 else latest_close
        change_pct = ((latest_close - prev_close) / prev_close) * 100

        # Indicators
        engine = IndicatorEngine(df)
        all_indicators = engine.compute_all()
        latest_vals = all_indicators["latest"]

        # Signal
        signal_result = signal_engine.compute_signal(symbol, _map_indicators_for_signal(latest_vals, df))

        # Fundamentals (run in thread pool since it's blocking)
        loop = asyncio.get_running_loop()
        try:
            fundamentals = await loop.run_in_executor(None, fetch_fundamentals, symbol)
        except Exception:
            logger.warning("Fundamentals fetch failed for %s — returning partial data", symbol)
            fundamentals = {}

        # Prepare key indicators summary
        indicators_summary = {
            "rsi": _safe_float(latest_vals.get("RSI")),
            "macd": _safe_float(latest_vals.get("MACD")),
            "macd_signal": _safe_float(latest_vals.get("MACD_Signal")),
            "sma_20": _safe_float(latest_vals.get("SMA_20")),
            "sma_50": _safe_float(latest_vals.get("SMA_50")),
            "sma_200": _safe_float(latest_vals.get("SMA_200")),
            "ema_20": _safe_float(latest_vals.get("EMA_20")),
            "bb_upper": _safe_float(latest_vals.get("BB_Upper")),
            "bb_lower": _safe_float(latest_vals.get("BB_Lower")),
            "atr": _safe_float(latest_vals.get("ATR")),
            "obv": _safe_float(latest_vals.get("OBV")),
            "adx": _safe_float(latest_vals.get("ADX")),
        }

        return {
            "symbol": symbol,
            "sector": NIFTY50_STOCKS.get(symbol, "Unknown"),
            "price": {
                "current": round(latest_close, 2),
                "previous_close": round(prev_close, 2),
                "change_pct": round(change_pct, 2),
                "high_52w": _safe_float(df["High"].tail(252).max()),
                "low_52w": _safe_float(df["Low"].tail(252).min()),
            },
            "indicators_summary": indicators_summary,
            "signal": {
                "composite_score": signal_result.composite_score,
                "signal": signal_result.signal,
                "trend_score": signal_result.trend_score,
                "momentum_score": signal_result.momentum_score,
                "volatility_score": signal_result.volatility_score,
                "volume_score": signal_result.volume_score,
            },
            "fundamentals": fundamentals,
            "alerts": [
                {
                    "type": a.alert_type,
                    "message": a.message,
                    "severity": a.severity,
                    "timestamp": str(a.timestamp),
                }
                for a in signal_result.alerts
            ],
        }

    except HTTPException:
        raise
    except (ValueError, RuntimeError) as e:
        if "No data" in str(e) or "failed" in str(e).lower():
            raise HTTPException(status_code=404, detail=f"No data available for symbol '{symbol}'. It may be invalid or delisted.")
        logger.error("Error fetching detail for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=f"Error analyzing {symbol}: {str(e)}")
    except Exception as e:
        logger.error("Error fetching detail for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=f"Error analyzing {symbol}: {str(e)}")


@router.get("/{symbol}/ohlcv")
async def get_stock_ohlcv(
    symbol: str,
    period: str = Query(default="2y", description="yfinance period string (e.g. 1mo, 6mo, 1y, 2y, 5y)"),
    interval: str = Query(default="1d", description="yfinance interval string (e.g. 1d, 1wk, 1mo)"),
):
    """
    GET /api/stocks/{symbol}/ohlcv
    OHLCV data with configurable period and interval.
    """
    symbol = validate_symbol(symbol)

    try:
        loop = asyncio.get_running_loop()
        df = await loop.run_in_executor(None, fetch_ohlcv, symbol, period, interval)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No OHLCV data for {symbol}")

        return {
            "symbol": symbol,
            "period": period,
            "interval": interval,
            "count": len(df),
            "data": _df_to_ohlcv_json(df),
        }

    except HTTPException:
        raise
    except (ValueError, RuntimeError) as e:
        if "No data" in str(e) or "failed" in str(e).lower():
            raise HTTPException(status_code=404, detail=f"No data available for symbol '{symbol}'. It may be invalid or delisted.")
        logger.error("Error fetching OHLCV for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=f"Error fetching OHLCV for {symbol}: {str(e)}")
    except Exception as e:
        logger.error("Error fetching OHLCV for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=f"Error fetching OHLCV for {symbol}: {str(e)}")


@router.get("/{symbol}/indicators")
async def get_stock_indicators(
    symbol: str,
    include_series: bool = Query(default=False, description="Include full time series data for each indicator"),
):
    """
    GET /api/stocks/{symbol}/indicators
    All 50 indicator values (latest + optional series data).
    """
    symbol = validate_symbol(symbol)

    try:
        df = await get_cached_or_fetch(symbol)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No data for {symbol}")

        engine = IndicatorEngine(df)
        all_indicators = engine.compute_all()

        # Clean latest values for JSON serialization
        latest_clean = {}
        for key, val in all_indicators["latest"].items():
            latest_clean[key] = _safe_float(val)

        response = {
            "symbol": symbol,
            "data_points": len(df),
            "latest": latest_clean,
        }

        if include_series:
            series_data = {}
            for key, val in all_indicators["series"].items():
                if isinstance(val, pd.Series):
                    series_data[key] = _series_to_json(val)
                elif isinstance(val, pd.DataFrame):
                    for col in val.columns:
                        series_data[f"{key}_{col}"] = _series_to_json(val[col])
            response["series"] = series_data

        return response

    except HTTPException:
        raise
    except (ValueError, RuntimeError) as e:
        if "No data" in str(e) or "failed" in str(e).lower():
            raise HTTPException(status_code=404, detail=f"No data available for symbol '{symbol}'. It may be invalid or delisted.")
        logger.error("Error computing indicators for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=f"Error computing indicators for {symbol}: {str(e)}")
    except Exception as e:
        logger.error("Error computing indicators for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=f"Error computing indicators for {symbol}: {str(e)}")


@router.get("/{symbol}/signal")
async def get_stock_signal(symbol: str, request: Request):
    """
    GET /api/stocks/{symbol}/signal
    Composite signal with full factor breakdown.
    """
    symbol = validate_symbol(symbol)
    await track_activity(request, "view_stock", symbol)

    try:
        df = await get_cached_or_fetch(symbol)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No data for {symbol}")

        engine = IndicatorEngine(df)
        all_indicators = engine.compute_all()
        latest_vals = all_indicators["latest"]

        mapped = _map_indicators_for_signal(latest_vals, df)
        signal_result = signal_engine.compute_signal(symbol, mapped)

        latest_close = float(df["Close"].iloc[-1])
        prev_close = float(df["Close"].iloc[-2]) if len(df) >= 2 else latest_close
        change_pct = ((latest_close - prev_close) / prev_close) * 100

        macd_val = _safe_float(latest_vals.get("MACD"))
        macd_sig = _safe_float(latest_vals.get("MACD_Signal"))
        macd_direction = None
        if macd_val is not None and macd_sig is not None:
            macd_direction = "bullish" if macd_val > macd_sig else "bearish"

        vol = float(df["Volume"].iloc[-1]) if "Volume" in df.columns else None
        avg_vol = float(df["Volume"].tail(20).mean()) if "Volume" in df.columns else None
        vol_ratio = round(vol / avg_vol, 2) if vol and avg_vol and avg_vol > 0 else None

        # Fetch fundamentals for PE, PB, market cap, dividend yield
        loop = asyncio.get_running_loop()
        try:
            fundamentals = await loop.run_in_executor(None, fetch_fundamentals, symbol)
        except Exception:
            fundamentals = {}

        return {
            "symbol": symbol,
            "price": round(latest_close, 2),
            "prev_close": round(prev_close, 2),
            "change_pct": round(change_pct, 2),
            "rsi": _safe_float(latest_vals.get("RSI")),
            "macd": _safe_float(latest_vals.get("MACD")),
            "macd_signal": macd_direction,
            "macd_histogram": _safe_float(latest_vals.get("MACD_Histogram")),
            "volume_ratio": vol_ratio,
            "stochastic_k": _safe_float(latest_vals.get("Stoch_K")),
            "williams_r": _safe_float(latest_vals.get("Williams_R")),
            "adx": _safe_float(latest_vals.get("ADX")),
            "bollinger_pctb": _safe_float(latest_vals.get("BB_PctB")),
            "high_52w": _safe_float(df["High"].tail(252).max()),
            "low_52w": _safe_float(df["Low"].tail(252).min()),
            "pe_ratio": _safe_float(fundamentals.get("trailingPE")),
            "pb_ratio": _safe_float(fundamentals.get("priceToBook")),
            "market_cap": _safe_float(fundamentals.get("marketCap")),
            "dividend_yield": _safe_float(fundamentals.get("dividendYield")),
            "composite_score": signal_result.composite_score,
            "signal": signal_result.signal,
            "breakdown": {
                "trend_score": signal_result.trend_score,
                "momentum_score": signal_result.momentum_score,
                "volatility_score": signal_result.volatility_score,
                "volume_score": signal_result.volume_score,
                "pattern_score": signal_result.pattern_score,
                "statistical_score": signal_result.statistical_score,
                "sentiment_score": signal_result.sentiment_score,
                "earnings_score": signal_result.earnings_score,
            },
            "weights": signal_engine.weights,
            "alerts": [
                {
                    "type": a.alert_type,
                    "message": a.message,
                    "severity": a.severity,
                    "timestamp": str(a.timestamp),
                }
                for a in signal_result.alerts
            ],
            "timestamp": str(signal_result.timestamp),
        }

    except HTTPException:
        raise
    except (ValueError, RuntimeError) as e:
        if "No data" in str(e) or "failed" in str(e).lower():
            raise HTTPException(status_code=404, detail=f"No data available for symbol '{symbol}'. It may be invalid or delisted.")
        logger.error("Error computing signal for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=f"Error computing signal for {symbol}: {str(e)}")
    except Exception as e:
        logger.error("Error computing signal for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=f"Error computing signal for {symbol}: {str(e)}")


@router.get("/{symbol}/sentiment")
async def get_stock_sentiment(symbol: str, request: Request, force_refresh: bool = Query(default=False)):
    """
    GET /api/stocks/{symbol}/sentiment
    Sentiment analysis results (calls Claude API).
    """
    symbol = validate_symbol(symbol)
    await track_activity(request, "view_sentiment", symbol)

    try:
        yf_symbol = to_yfinance_symbol(symbol)
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, sentiment_analyzer.get_stock_sentiment, yf_symbol, force_refresh
        )

        return {
            "symbol": symbol,
            "sentiment_score": result.get("sentiment_score", 0.0),
            "key_themes": result.get("key_themes", []),
            "price_impact": result.get("price_impact", {}),
            "risk_factors": result.get("risk_factors", []),
            "catalysts": result.get("catalysts", []),
            "article_count": result.get("article_count", 0),
            "timestamp": result.get("timestamp"),
            "note": result.get("note"),
            "error": result.get("error"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error analyzing sentiment for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=f"Error analyzing sentiment for {symbol}: {str(e)}")


@router.get("/{symbol}/earnings")
async def get_stock_earnings(symbol: str):
    """
    GET /api/stocks/{symbol}/earnings
    Earnings, fundamental data, and key financial ratios.
    """
    symbol = validate_symbol(symbol)

    try:
        yf_symbol = to_yfinance_symbol(symbol)
        loop = asyncio.get_running_loop()

        # Run earnings analysis and fundamentals fetch concurrently in the thread pool
        earnings_future = loop.run_in_executor(
            None, earnings_predictor.get_full_earnings_analysis, yf_symbol
        )
        fundamentals_future = loop.run_in_executor(
            None, fetch_fundamentals, symbol
        )

        result, fundamentals_raw = await asyncio.gather(
            earnings_future, fundamentals_future, return_exceptions=True
        )
        # If earnings_predictor raised, re-raise; if fundamentals failed, use empty dict
        if isinstance(result, Exception):
            raise result
        fundamentals = fundamentals_raw if isinstance(fundamentals_raw, dict) else {}

        peg_ratio = result.get("peg_ratio")

        # Compute ROCE: EBIT / (Total Assets - Current Liabilities)
        roce = None
        try:
            import yfinance as yf
            ticker = yf.Ticker(yf_symbol)
            financials = ticker.financials
            balance = ticker.balance_sheet
            if financials is not None and not financials.empty and balance is not None and not balance.empty:
                ebit = None
                for key in ["EBIT", "Operating Income"]:
                    if key in financials.index:
                        val = financials.loc[key].iloc[0]
                        if val is not None and str(val) != "nan":
                            ebit = float(val)
                            break
                total_assets = None
                if "Total Assets" in balance.index:
                    val = balance.loc["Total Assets"].iloc[0]
                    if val is not None and str(val) != "nan":
                        total_assets = float(val)
                current_liabilities = None
                if "Current Liabilities" in balance.index:
                    val = balance.loc["Current Liabilities"].iloc[0]
                    if val is not None and str(val) != "nan":
                        current_liabilities = float(val)
                if ebit is not None and total_assets is not None and current_liabilities is not None:
                    capital_employed = total_assets - current_liabilities
                    if capital_employed > 0:
                        roce = round(ebit / capital_employed, 4)
        except Exception as e:
            logger.debug("Could not compute ROCE for %s: %s", symbol, e)

        # Build key_ratios from yfinance fundamentals
        roe = fundamentals.get("returnOnEquity")
        roa = fundamentals.get("returnOnAssets")

        # Fallback: compute ROE and ROA from financial statements if info is null
        if roe is None or roa is None:
            try:
                import yfinance as yf
                _ticker = yf.Ticker(yf_symbol)
                _financials = _ticker.financials
                _balance = _ticker.balance_sheet
                if _financials is not None and not _financials.empty and _balance is not None and not _balance.empty:
                    net_income = None
                    for _key in ["Net Income", "Net Income Common Stockholders"]:
                        if _key in _financials.index:
                            _val = _financials.loc[_key].iloc[0]
                            if _val is not None and str(_val) != "nan":
                                net_income = float(_val)
                                break

                    if net_income is not None:
                        if roe is None:
                            for _key in ["Total Stockholder Equity", "Stockholders Equity", "Total Equity Gross Minority Interest"]:
                                if _key in _balance.index:
                                    _val = _balance.loc[_key].iloc[0]
                                    if _val is not None and str(_val) != "nan" and float(_val) != 0:
                                        roe = round(net_income / float(_val), 4)
                                        break

                        if roa is None:
                            if "Total Assets" in _balance.index:
                                _val = _balance.loc["Total Assets"].iloc[0]
                                if _val is not None and str(_val) != "nan" and float(_val) != 0:
                                    roa = round(net_income / float(_val), 4)
            except Exception as e:
                logger.debug("Could not compute fallback ROE/ROA for %s: %s", symbol, e)

        key_ratios = {
            "pe": fundamentals.get("trailingPE"),
            "pb": fundamentals.get("priceToBook"),
            "peg": fundamentals.get("pegRatio") or peg_ratio,  # prefer yfinance's PEG if available
            "debt_to_equity": fundamentals.get("debtToEquity"),
            "current_ratio": fundamentals.get("currentRatio"),
            "roe": roe,
            "roa": roa,
            "roce": roce,  # computed as EBIT / (Total Assets - Current Liabilities)
            "dividend_yield": fundamentals.get("dividendYield"),
            "eps": fundamentals.get("trailingEps"),
            "forward_pe": fundamentals.get("forwardPE"),
            "target_price": fundamentals.get("targetMeanPrice"),
        }

        return {
            "symbol": symbol,
            "earnings_history": result.get("earnings_history"),
            "margin_analysis": result.get("margin_analysis"),
            "eps_growth": result.get("eps_growth"),
            "earnings_growth": result.get("earnings_growth"),
            "peg_ratio": peg_ratio,
            "accrual_ratio": result.get("accrual_ratio"),
            "altman_z_score": result.get("altman_z_score"),
            "piotroski_f_score": result.get("piotroski_f_score"),
            "earnings_score_inputs": result.get("earnings_score_inputs"),
            "key_ratios": key_ratios,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching earnings for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=f"Error fetching earnings for {symbol}: {str(e)}")


@router.get("/{symbol}/risk")
async def get_stock_risk(symbol: str):
    """
    GET /api/stocks/{symbol}/risk
    Risk metrics for the stock: VaR, Sharpe, drawdown, position sizing.
    """
    symbol = validate_symbol(symbol)

    try:
        df = await get_cached_or_fetch(symbol)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No data for {symbol}")

        # Compute daily returns
        returns = df["Close"].pct_change().dropna()

        if len(returns) < 30:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient data for risk analysis on {symbol} (need at least 30 days)",
            )

        latest_close = float(df["Close"].iloc[-1])

        # VaR
        var_results = compute_var(returns, initial_price=latest_close)

        # Performance ratios
        perf = compute_performance_ratios(returns)

        # Drawdown
        dd = max_drawdown(returns)
        dd_summary = {k: v for k, v in dd.items() if k != "drawdown_curve"}

        # Position sizing using ATR
        atr_series = compute_atr(df["High"], df["Low"], df["Close"])
        atr_latest = float(atr_series.dropna().iloc[-1]) if not atr_series.dropna().empty else 0.0
        sizing = position_sizing(latest_close, atr_latest)

        return {
            "symbol": symbol,
            "data_points": len(returns),
            "current_price": round(latest_close, 2),
            "var": var_results,
            "performance": perf,
            "drawdown": dd_summary,
            "position_sizing": sizing,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error computing risk for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=f"Error computing risk for {symbol}: {str(e)}")


@router.get("/{symbol}/action")
async def get_stock_action(symbol: str):
    """
    GET /api/stocks/{symbol}/action
    Full action recommendation with option chain analysis, buy/sell targets,
    support/resistance levels, and confidence score.
    """
    symbol = validate_symbol(symbol)

    try:
        df = await get_cached_or_fetch(symbol)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No OHLCV data available for {symbol}")

        # Compute indicators
        engine = IndicatorEngine(df)
        all_indicators = engine.compute_all()
        latest_vals = all_indicators["latest"]

        # Compute composite signal
        signal_result = signal_engine.compute_signal(symbol, _map_indicators_for_signal(latest_vals, df))

        # Generate action recommendation (includes option chain fetch)
        loop = asyncio.get_running_loop()
        recommendation = await loop.run_in_executor(
            None,
            get_action_recommendation,
            symbol,
            df,
            signal_result,
            latest_vals,
        )

        return {
            "symbol": symbol,
            "sector": NIFTY50_STOCKS.get(symbol, "Unknown"),
            **recommendation,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error generating action recommendation for %s: %s", symbol, e)
        raise HTTPException(
            status_code=500,
            detail=f"Error generating action recommendation for {symbol}: {str(e)}",
        )
