from __future__ import annotations

"""
NSE Signal Engine - Portfolio API Routes

Provides endpoints for portfolio-level analysis: risk metrics,
efficient frontier, and Monte Carlo simulations.
"""

import asyncio
import logging
from typing import List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from config import NIFTY50_STOCKS
from services.data_fetcher import get_cached_or_fetch
from services.risk_engine import (
    full_risk_report,
    compute_var,
    compute_performance_ratios,
    max_drawdown,
    correlation_matrix,
    efficient_frontier,
    monte_carlo_var,
    kelly_criterion,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class PortfolioRequest(BaseModel):
    stocks: List[str] = Field(..., min_length=1, description="List of NIFTY 50 symbols")
    weights: List[float] = Field(..., min_length=1, description="Portfolio weights (must sum to ~1.0)")
    capital: float = Field(default=100_000, ge=0, description="Portfolio capital in INR")

    @field_validator("stocks")
    @classmethod
    def validate_stocks(cls, v):
        invalid = [s for s in v if s.strip().upper() not in NIFTY50_STOCKS]
        if invalid:
            raise ValueError(f"Invalid NIFTY 50 symbols: {invalid}")
        return [s.strip().upper() for s in v]

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, v):
        if any(w < 0 for w in v):
            raise ValueError("Weights must be non-negative")
        total = sum(v)
        if abs(total - 1.0) > 0.05:
            raise ValueError(f"Weights must sum to approximately 1.0 (got {total:.4f})")
        return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _fetch_portfolio_returns(
    stocks: List[str],
) -> pd.DataFrame:
    """Fetch OHLCV data for all stocks and build a returns DataFrame."""
    tasks = [get_cached_or_fetch(sym) for sym in stocks]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    returns_dict = {}
    for sym, result in zip(stocks, results):
        if isinstance(result, Exception):
            logger.error("Failed to fetch %s: %s", sym, result)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch data for {sym}: {str(result)}",
            )
        if result is None or result.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No OHLCV data available for {sym}",
            )
        returns_dict[sym] = result["Close"].pct_change().dropna()

    returns_df = pd.DataFrame(returns_dict).dropna()
    if returns_df.empty or len(returns_df) < 30:
        raise HTTPException(
            status_code=400,
            detail="Insufficient overlapping data across portfolio stocks (need at least 30 days)",
        )
    return returns_df


def _clean_for_json(obj):
    """Recursively clean numpy/pandas types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_clean_for_json(v) for v in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64)):
        f = float(obj)
        if np.isnan(f) or np.isinf(f):
            return None
        return round(f, 6)
    elif isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    elif isinstance(obj, pd.Series):
        return obj.to_dict()
    elif isinstance(obj, pd.DataFrame):
        return obj.to_dict()
    return obj


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/analyze")
async def analyze_portfolio(req: PortfolioRequest):
    """
    POST /api/portfolio/analyze
    Full portfolio analysis: weighted returns, performance ratios, VaR, drawdown.
    """
    if len(req.stocks) != len(req.weights):
        raise HTTPException(
            status_code=400,
            detail=f"Number of stocks ({len(req.stocks)}) must match number of weights ({len(req.weights)})",
        )

    try:
        returns_df = await _fetch_portfolio_returns(req.stocks)

        # Compute weighted portfolio returns
        weights = np.array(req.weights)
        portfolio_returns = (returns_df * weights).sum(axis=1)

        # Full risk report
        report = full_risk_report(
            returns=portfolio_returns,
            portfolio_returns_df=returns_df,
            capital=req.capital,
        )

        # Per-stock summary
        stock_summaries = []
        for i, sym in enumerate(req.stocks):
            sym_returns = returns_df[sym]
            stock_summaries.append({
                "symbol": sym,
                "weight": round(req.weights[i], 4),
                "annualized_return": round(float(sym_returns.mean() * 252), 6),
                "annualized_volatility": round(float(sym_returns.std() * np.sqrt(252)), 6),
                "allocation_inr": round(req.capital * req.weights[i], 2),
            })

        return _clean_for_json({
            "portfolio": {
                "stocks": req.stocks,
                "weights": req.weights,
                "capital": req.capital,
                "data_points": len(portfolio_returns),
            },
            "stock_summaries": stock_summaries,
            "performance": report.get("performance"),
            "var": report.get("var"),
            "drawdown": report.get("drawdown"),
            "efficient_frontier_summary": report.get("efficient_frontier"),
            "correlation_matrix": report.get("correlation_matrix"),
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error analyzing portfolio: %s", e)
        raise HTTPException(status_code=500, detail=f"Error analyzing portfolio: {str(e)}")


@router.get("/risk")
async def get_portfolio_risk(
    stocks: str = "RELIANCE,TCS,HDFCBANK",
    weights: str = "0.34,0.33,0.33",
):
    """
    GET /api/portfolio/risk
    Portfolio risk metrics including VaR, Sharpe, correlation matrix.
    Accepts comma-separated stocks and weights as query parameters.
    """
    try:
        stock_list = [s.strip().upper() for s in stocks.split(",")]
        weight_list = [float(w.strip()) for w in weights.split(",")]

        if len(stock_list) != len(weight_list):
            raise HTTPException(
                status_code=400,
                detail="Number of stocks must match number of weights",
            )

        # Validate symbols
        invalid = [s for s in stock_list if s not in NIFTY50_STOCKS]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid symbols: {invalid}")

        returns_df = await _fetch_portfolio_returns(stock_list)
        weights_arr = np.array(weight_list)
        portfolio_returns = (returns_df * weights_arr).sum(axis=1)

        # VaR
        var_results = compute_var(portfolio_returns)

        # Performance
        perf = compute_performance_ratios(portfolio_returns)

        # Drawdown
        dd = max_drawdown(portfolio_returns)
        dd_summary = {k: v for k, v in dd.items() if k != "drawdown_curve"}

        # Correlation
        corr = correlation_matrix(returns_df)

        return _clean_for_json({
            "stocks": stock_list,
            "weights": weight_list,
            "var": var_results,
            "performance": perf,
            "drawdown": dd_summary,
            "correlation_matrix": corr.to_dict(),
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error computing portfolio risk: %s", e)
        raise HTTPException(status_code=500, detail=f"Error computing portfolio risk: {str(e)}")


@router.get("/efficient-frontier")
async def get_efficient_frontier(
    stocks: str = "RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK",
    num_portfolios: int = 5000,
):
    """
    GET /api/portfolio/efficient-frontier
    Efficient frontier data for the given stocks.
    """
    try:
        stock_list = [s.strip().upper() for s in stocks.split(",")]

        if len(stock_list) < 2:
            raise HTTPException(
                status_code=400,
                detail="At least 2 stocks are required for efficient frontier analysis",
            )

        invalid = [s for s in stock_list if s not in NIFTY50_STOCKS]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid symbols: {invalid}")

        returns_df = await _fetch_portfolio_returns(stock_list)

        ef = efficient_frontier(
            returns_df,
            num_portfolios=min(num_portfolios, 10000),
        )

        # Return summary (strip large arrays to keep response manageable)
        return _clean_for_json({
            "stocks": stock_list,
            "num_portfolios": ef["num_portfolios"],
            "max_sharpe_portfolio": ef["max_sharpe_portfolio"],
            "min_variance_portfolio": ef["min_variance_portfolio"],
            "asset_names": ef["asset_names"],
            "frontier_data": {
                "returns": ef["portfolio_returns"],
                "volatilities": ef["portfolio_volatilities"],
                "sharpes": ef["portfolio_sharpes"],
            },
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error computing efficient frontier: %s", e)
        raise HTTPException(status_code=500, detail=f"Error computing efficient frontier: {str(e)}")


@router.get("/monte-carlo")
async def get_monte_carlo(
    stocks: str = "RELIANCE,TCS,HDFCBANK",
    weights: str = "0.34,0.33,0.33",
    num_simulations: int = 10000,
    horizon_days: int = 30,
    capital: float = 100000,
):
    """
    GET /api/portfolio/monte-carlo
    Monte Carlo simulation results for the portfolio.
    """
    try:
        stock_list = [s.strip().upper() for s in stocks.split(",")]
        weight_list = [float(w.strip()) for w in weights.split(",")]

        if len(stock_list) != len(weight_list):
            raise HTTPException(
                status_code=400,
                detail="Number of stocks must match number of weights",
            )

        invalid = [s for s in stock_list if s not in NIFTY50_STOCKS]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid symbols: {invalid}")

        returns_df = await _fetch_portfolio_returns(stock_list)
        weights_arr = np.array(weight_list)
        portfolio_returns = (returns_df * weights_arr).sum(axis=1)

        mc_result = monte_carlo_var(
            portfolio_returns,
            num_simulations=min(num_simulations, 50000),
            horizon_days=horizon_days,
            initial_price=capital,
        )

        return _clean_for_json({
            "stocks": stock_list,
            "weights": weight_list,
            "capital": capital,
            "monte_carlo": mc_result,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error running Monte Carlo: %s", e)
        raise HTTPException(status_code=500, detail=f"Error running Monte Carlo simulation: {str(e)}")
