from __future__ import annotations

"""
NSE Signal Engine - Screener & Backtest Routes

Provides endpoints for stock screening with filters, backtesting strategies,
active alerts, and market overview.
"""

import asyncio
import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from config import NIFTY50_STOCKS, SECTORS, to_yfinance_symbol
from services.data_fetcher import get_cached_or_fetch, fetch_ohlcv
from services.indicators import IndicatorEngine
from services.signal_engine import SignalEngine
from services.backtester import Backtester
from routes.stocks import _map_indicators_for_signal, track_activity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["screener"])

# Shared signal engine
signal_engine = SignalEngine()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ScreenerRequest(BaseModel):
    rsi_min: Optional[float] = Field(default=None, ge=0, le=100, description="Minimum RSI value")
    rsi_max: Optional[float] = Field(default=None, ge=0, le=100, description="Maximum RSI value")
    macd_signal: Optional[str] = Field(
        default=None, description="MACD filter: 'bullish' (MACD > signal) or 'bearish'"
    )
    sector: Optional[str] = Field(default=None, description="Filter by sector")
    sectors: Optional[List[str]] = Field(default=None, description="Filter by multiple sectors")
    score_min: Optional[float] = Field(default=None, ge=-100, le=100, description="Minimum composite score")
    score_max: Optional[float] = Field(default=None, ge=-100, le=100, description="Maximum composite score")
    signal_type: Optional[str] = Field(
        default=None,
        description="Signal filter: STRONG BUY, BUY, HOLD, SELL, STRONG SELL",
    )
    above_sma200: Optional[bool] = Field(default=None, description="Price above SMA 200")
    min_volume_avg: Optional[float] = Field(default=None, ge=0, description="Minimum 20-day average volume")
    sort_by: str = Field(default="composite_score", description="Sort field: composite_score, rsi, change_pct")
    sort_order: str = Field(default="desc", description="Sort order: asc or desc")


class BacktestRequest(BaseModel):
    symbol: str = Field(..., description="NSE symbol to backtest")
    entry_threshold: float = Field(default=30, description="Signal score to trigger buy")
    exit_threshold: float = Field(default=-10, description="Signal score to trigger sell")
    initial_capital: float = Field(default=100_000, ge=1000, description="Starting capital in INR")
    period: str = Field(default="2y", description="Data period for backtest")
    slippage_pct: float = Field(default=0.0005, ge=0, le=0.01, description="Slippage per trade")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
        if np.isnan(f) or np.isinf(f):
            return None
        return round(f, 4)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/screener")
async def screen_stocks(req: ScreenerRequest, request: Request):
    """
    POST /api/screener
    Screen NIFTY 50 stocks with filter criteria.
    """
    await track_activity(request, "run_screener", str(req.sectors or []))
    try:
        # Determine which symbols to process
        # Merge sector (singular) and sectors (plural) into a single list
        sector_filters: List[str] = []
        if req.sectors:
            sector_filters.extend(req.sectors)
        if req.sector and req.sector not in sector_filters:
            sector_filters.append(req.sector)

        if sector_filters:
            sector_lower = [s.lower() for s in sector_filters]
            symbols = [
                sym for sym, sec in NIFTY50_STOCKS.items()
                if sec.lower() in sector_lower
            ]
            if not symbols:
                raise HTTPException(
                    status_code=400,
                    detail=f"No stocks found for sectors {sector_filters}. Valid sectors: {SECTORS}",
                )
        else:
            symbols = sorted(NIFTY50_STOCKS.keys())

        results = []

        async def _screen_symbol(sym: str) -> Optional[dict]:
            try:
                df = await get_cached_or_fetch(sym)
                if df is None or df.empty or len(df) < 30:
                    return None

                engine = IndicatorEngine(df)
                all_indicators = engine.compute_all()
                latest = all_indicators["latest"]

                mapped = _map_indicators_for_signal(latest, df)
                signal_result = signal_engine.compute_signal(sym, mapped)

                latest_close = float(df["Close"].iloc[-1])
                prev_close = float(df["Close"].iloc[-2]) if len(df) >= 2 else latest_close
                change_pct = ((latest_close - prev_close) / prev_close) * 100

                rsi = _safe_float(latest.get("RSI"))
                macd_val = _safe_float(latest.get("MACD"))
                macd_sig = _safe_float(latest.get("MACD_Signal"))
                sma200 = _safe_float(latest.get("SMA_200"))
                avg_vol_20 = _safe_float(latest.get("Volume_ROC"))  # approximation

                # Compute 20-day average volume directly
                vol_series = df["Volume"].tail(20)
                avg_volume = float(vol_series.mean()) if len(vol_series) > 0 else 0

                # --- Apply filters ---

                # RSI filter
                if req.rsi_min is not None and (rsi is None or rsi < req.rsi_min):
                    return None
                if req.rsi_max is not None and (rsi is None or rsi > req.rsi_max):
                    return None

                # MACD signal filter
                if req.macd_signal is not None and macd_val is not None and macd_sig is not None:
                    if req.macd_signal.lower() == "bullish" and macd_val <= macd_sig:
                        return None
                    if req.macd_signal.lower() == "bearish" and macd_val >= macd_sig:
                        return None

                # Composite score filter
                if req.score_min is not None and signal_result.composite_score < req.score_min:
                    return None
                if req.score_max is not None and signal_result.composite_score > req.score_max:
                    return None

                # Signal type filter
                if req.signal_type is not None and signal_result.signal != req.signal_type.upper():
                    return None

                # SMA 200 filter
                if req.above_sma200 is not None and sma200 is not None:
                    if req.above_sma200 and latest_close <= sma200:
                        return None
                    if not req.above_sma200 and latest_close > sma200:
                        return None

                # Volume filter
                if req.min_volume_avg is not None and avg_volume < req.min_volume_avg:
                    return None

                return {
                    "symbol": sym,
                    "sector": NIFTY50_STOCKS.get(sym, "Unknown"),
                    "price": round(latest_close, 2),
                    "change_pct": round(change_pct, 2),
                    "composite_score": signal_result.composite_score,
                    "signal": signal_result.signal,
                    "rsi": rsi,
                    "macd": macd_val,
                    "macd_signal": macd_sig,
                    "sma_200": sma200,
                    "avg_volume_20d": round(avg_volume),
                    "alerts_count": len(signal_result.alerts),
                }

            except Exception as e:
                logger.error("Screener error for %s: %s", sym, e)
                return None

        tasks = [_screen_symbol(sym) for sym in symbols]
        processed = await asyncio.gather(*tasks, return_exceptions=True)

        for item in processed:
            if isinstance(item, Exception):
                continue
            if item is not None:
                results.append(item)

        # Sort results
        reverse = req.sort_order.lower() == "desc"
        sort_key = req.sort_by
        results.sort(
            key=lambda x: x.get(sort_key, 0) or 0,
            reverse=reverse,
        )

        return {
            "filters_applied": {
                k: v for k, v in req.model_dump().items()
                if v is not None and k not in ("sort_by", "sort_order")
            },
            "count": len(results),
            "stocks": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Screener error: %s", e)
        raise HTTPException(status_code=500, detail=f"Screener error: {str(e)}")


@router.post("/backtest")
async def run_backtest(req: BacktestRequest, request: Request):
    """
    POST /api/backtest
    Run a backtest with signal-based entry/exit on a single stock.
    """
    await track_activity(request, "run_backtest", req.symbol.strip().upper())
    symbol = req.symbol.strip().upper()
    if symbol not in NIFTY50_STOCKS:
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol}' is not in the NIFTY 50 universe.",
        )

    try:
        # Fetch OHLCV data
        loop = asyncio.get_running_loop()
        df = await loop.run_in_executor(None, fetch_ohlcv, symbol, req.period, "1d")
        if df is None or df.empty or len(df) < 50:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient data for backtesting {symbol} (need at least 50 data points)",
            )

        # Compute indicators and generate signal scores for each day
        engine = IndicatorEngine(df)
        all_indicators = engine.compute_all()

        # Build a signal series: for each row, compute the composite signal
        # We'll use a rolling approach - compute signal from the latest values
        # For simplicity, compute signal from the full indicator latest values
        # and create a signal column
        signal_scores = []
        for i in range(len(df)):
            if i < 50:
                signal_scores.append(0.0)
                continue

            window = df.iloc[: i + 1]
            try:
                win_engine = IndicatorEngine(window)
                win_all = win_engine.compute_all()
                win_latest = win_all["latest"]
                win_mapped = _map_indicators_for_signal(win_latest, window)
                sig_result = signal_engine.compute_signal(symbol, win_mapped)
                signal_scores.append(sig_result.composite_score)
            except Exception:
                signal_scores.append(0.0)

        signals_df = pd.DataFrame({"signal": signal_scores}, index=df.index)

        # Run backtest
        backtester = Backtester(
            initial_capital=req.initial_capital,
            slippage_pct=req.slippage_pct,
        )
        result = backtester.run(
            df, signals_df,
            entry_threshold=req.entry_threshold,
            exit_threshold=req.exit_threshold,
        )

        # Build response
        summary = result.summary()

        # Equity curve (sampled for JSON)
        equity_data = []
        if not result.equity_curve.empty:
            sampled = result.equity_curve
            if len(sampled) > 500:
                step = len(sampled) // 500
                sampled = sampled.iloc[::step]
            for idx, val in sampled.items():
                equity_data.append({
                    "date": str(idx.date()) if hasattr(idx, "date") else str(idx),
                    "equity": round(float(val), 2),
                })

        # Trade log
        trades = []
        if not result.trade_log.empty:
            trades = result.trade_log.to_dict(orient="records")

        return {
            "symbol": symbol,
            "period": req.period,
            "entry_threshold": req.entry_threshold,
            "exit_threshold": req.exit_threshold,
            "initial_capital": req.initial_capital,
            "summary": summary,
            "equity_curve": equity_data,
            "trades": trades,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Backtest error for %s: %s", symbol, e)
        raise HTTPException(status_code=500, detail=f"Backtest error for {symbol}: {str(e)}")


@router.get("/alerts")
async def get_active_alerts():
    """
    GET /api/alerts
    Get current active alerts across all NIFTY 50 stocks.
    """
    try:
        all_alerts = []

        async def _check_symbol(sym: str):
            try:
                df = await get_cached_or_fetch(sym)
                if df is None or df.empty or len(df) < 30:
                    return []

                engine = IndicatorEngine(df)
                all_indicators = engine.compute_all()
                latest = all_indicators["latest"]

                mapped = _map_indicators_for_signal(latest, df)
                signal_result = signal_engine.compute_signal(sym, mapped)

                return [
                    {
                        "symbol": sym,
                        "sector": NIFTY50_STOCKS.get(sym, "Unknown"),
                        "alert_type": a.alert_type,
                        "message": a.message,
                        "severity": a.severity,
                        "score": _safe_float(a.score),
                        "timestamp": str(a.timestamp),
                    }
                    for a in signal_result.alerts
                ]
            except Exception as e:
                logger.error("Alert check error for %s: %s", sym, e)
                return []

        tasks = [_check_symbol(sym) for sym in sorted(NIFTY50_STOCKS.keys())]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for item in results:
            if isinstance(item, list):
                all_alerts.extend(item)

        # Sort by severity (critical first) then by timestamp
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        all_alerts.sort(key=lambda a: (severity_order.get(a["severity"], 3), a["timestamp"]))

        return {
            "count": len(all_alerts),
            "alerts": all_alerts,
        }

    except Exception as e:
        logger.error("Alerts error: %s", e)
        raise HTTPException(status_code=500, detail=f"Error fetching alerts: {str(e)}")


@router.get("/market/overview")
async def get_market_overview():
    """
    GET /api/market/overview
    NIFTY 50 index level, advance/decline ratio, sector performance.
    """
    try:
        # Fetch all NIFTY 50 stock data
        advancing = 0
        declining = 0
        unchanged = 0
        sector_performance: Dict[str, List[float]] = {s: [] for s in SECTORS}
        stock_data = []

        async def _process_symbol(sym: str):
            try:
                df = await get_cached_or_fetch(sym)
                if df is None or df.empty or len(df) < 2:
                    return None

                latest_close = float(df["Close"].iloc[-1])
                prev_close = float(df["Close"].iloc[-2])
                change_pct = ((latest_close - prev_close) / prev_close) * 100

                return {
                    "symbol": sym,
                    "sector": NIFTY50_STOCKS.get(sym, "Unknown"),
                    "price": round(latest_close, 2),
                    "change_pct": round(change_pct, 4),
                }
            except Exception as e:
                logger.error("Market overview error for %s: %s", sym, e)
                return None

        tasks = [_process_symbol(sym) for sym in sorted(NIFTY50_STOCKS.keys())]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for item in results:
            if isinstance(item, Exception) or item is None:
                continue
            stock_data.append(item)

            change = item["change_pct"]
            if change > 0.01:
                advancing += 1
            elif change < -0.01:
                declining += 1
            else:
                unchanged += 1

            sector = item["sector"]
            if sector in sector_performance:
                sector_performance[sector].append(change)

        # Compute sector averages
        sector_summary = []
        for sector_name in SECTORS:
            changes = sector_performance.get(sector_name, [])
            if changes:
                avg_change = round(sum(changes) / len(changes), 4)
                sector_summary.append({
                    "sector": sector_name,
                    "avg_change_pct": avg_change,
                    "stock_count": len(changes),
                    "advancing": sum(1 for c in changes if c > 0.01),
                    "declining": sum(1 for c in changes if c < -0.01),
                })

        sector_summary.sort(key=lambda x: x["avg_change_pct"], reverse=True)

        # Top gainers and losers
        stock_data.sort(key=lambda x: x["change_pct"], reverse=True)
        top_gainers = stock_data[:5]
        top_losers = stock_data[-5:][::-1] if len(stock_data) >= 5 else []

        # Market breadth
        total = advancing + declining + unchanged
        ad_ratio = round(advancing / declining, 2) if declining > 0 else float(advancing)

        total_requested = len(NIFTY50_STOCKS)

        return {
            "market_breadth": {
                "total_stocks": total,
                "advancing": advancing,
                "declining": declining,
                "unchanged": unchanged,
                "advance_decline_ratio": ad_ratio,
            },
            "data_quality": {
                "total_stocks": total_requested,
                "loaded": len(stock_data),
                "failed": total_requested - len(stock_data),
            },
            "sector_performance": sector_summary,
            "top_gainers": top_gainers,
            "top_losers": top_losers,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Market overview error: %s", e)
        raise HTTPException(status_code=500, detail=f"Error generating market overview: {str(e)}")
