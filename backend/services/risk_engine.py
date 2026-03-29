from __future__ import annotations

"""
Portfolio Risk Management Engine for NSE Signal Engine.

Implements Kelly Criterion, VaR (Historical, Parametric, Monte Carlo),
performance ratios (Sharpe, Sortino, Calmar, Treynor, Information Ratio),
drawdown analysis, correlation matrix, efficient frontier, and position sizing.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
RISK_FREE_RATE = 0.07  # India 10-year government bond yield
TRADING_DAYS_PER_YEAR = 252
DEFAULT_CAPITAL = 100_000  # 1 lakh INR


# ---------------------------------------------------------------------------
# 1. Kelly Criterion Position Sizing
# ---------------------------------------------------------------------------

def kelly_criterion(
    win_probability: float,
    win_loss_ratio: float,
    capital: float = DEFAULT_CAPITAL,
    fraction: str = "half",
) -> Dict:
    """
    Kelly Criterion position sizing.

    Parameters
    ----------
    win_probability : float
        Probability of a winning trade (0-1).
    win_loss_ratio : float
        Ratio of average win to average loss (b = reward/risk).
    capital : float
        Total portfolio capital in INR.
    fraction : str
        'full', 'half', or 'quarter' Kelly.

    Returns
    -------
    dict with full_kelly, half_kelly, quarter_kelly, recommended fraction,
    and position size in INR.
    """
    p = win_probability
    q = 1.0 - p
    b = win_loss_ratio

    # f* = (p*b - q) / b
    f_full = (p * b - q) / b if b != 0 else 0.0

    # Clamp to [0, 1] -- never go negative or above 100%
    f_full = max(0.0, min(f_full, 1.0))
    f_half = f_full / 2.0
    f_quarter = f_full / 4.0

    fraction_map = {"full": f_full, "half": f_half, "quarter": f_quarter}
    f_safe = fraction_map.get(fraction, f_half)

    position_size = capital * f_safe

    return {
        "full_kelly": round(f_full, 6),
        "half_kelly": round(f_half, 6),
        "quarter_kelly": round(f_quarter, 6),
        "recommended_fraction": fraction,
        "f_safe": round(f_safe, 6),
        "position_size_inr": round(position_size, 2),
        "capital": capital,
    }


# ---------------------------------------------------------------------------
# 2. Value at Risk (VaR) and CVaR
# ---------------------------------------------------------------------------

def historical_var(
    returns: pd.Series,
    confidence_levels: List[float] = [0.95, 0.99],
) -> Dict:
    """Historical VaR -- simple percentile of sorted returns."""
    results = {}
    for cl in confidence_levels:
        alpha = 1.0 - cl
        var_value = float(np.percentile(returns.dropna(), alpha * 100))
        # CVaR = mean of returns that are <= VaR
        tail = returns[returns <= var_value]
        cvar_value = float(tail.mean()) if len(tail) > 0 else var_value
        results[f"VaR_{int(cl*100)}"] = round(var_value, 6)
        results[f"CVaR_{int(cl*100)}"] = round(cvar_value, 6)
    return results


def parametric_var(
    returns: pd.Series,
    confidence_levels: List[float] = [0.95, 0.99],
) -> Dict:
    """Parametric (variance-covariance) VaR assuming normal distribution."""
    z_scores = {0.95: 1.6449, 0.99: 2.3263}
    mu = float(returns.mean())
    sigma = float(returns.std())

    results = {"mean": round(mu, 8), "std": round(sigma, 8)}
    for cl in confidence_levels:
        z = z_scores.get(cl, 1.6449)
        var_value = mu - z * sigma
        # CVaR for normal distribution: mu - sigma * phi(z) / (1-cl)
        # where phi is the standard normal PDF
        phi_z = (1.0 / np.sqrt(2 * np.pi)) * np.exp(-0.5 * z ** 2)
        cvar_value = mu - sigma * (phi_z / (1.0 - cl))
        results[f"VaR_{int(cl*100)}"] = round(var_value, 6)
        results[f"CVaR_{int(cl*100)}"] = round(cvar_value, 6)
    return results


def monte_carlo_var(
    returns: pd.Series,
    confidence_levels: List[float] = [0.95, 0.99],
    num_simulations: int = 10_000,
    horizon_days: int = 1,
    initial_price: float = 100.0,
    seed: Optional[int] = 42,
) -> Dict:
    """
    Monte Carlo VaR using Geometric Brownian Motion.

    S(t+dt) = S(t) * exp((mu - sigma^2/2)*dt + sigma*sqrt(dt)*Z)
    """
    if seed is not None:
        np.random.seed(seed)

    mu = float(returns.mean()) * TRADING_DAYS_PER_YEAR
    sigma = float(returns.std()) * np.sqrt(TRADING_DAYS_PER_YEAR)
    dt = horizon_days / TRADING_DAYS_PER_YEAR

    # Generate simulated end prices
    Z = np.random.standard_normal(num_simulations)
    drift = (mu - 0.5 * sigma ** 2) * dt
    diffusion = sigma * np.sqrt(dt) * Z
    simulated_prices = initial_price * np.exp(drift + diffusion)

    # Simulated returns
    simulated_returns = (simulated_prices - initial_price) / initial_price

    results = {
        "num_simulations": num_simulations,
        "horizon_days": horizon_days,
        "annualized_mu": round(mu, 6),
        "annualized_sigma": round(sigma, 6),
    }
    for cl in confidence_levels:
        alpha = 1.0 - cl
        var_value = float(np.percentile(simulated_returns, alpha * 100))
        tail = simulated_returns[simulated_returns <= var_value]
        cvar_value = float(tail.mean()) if len(tail) > 0 else var_value
        results[f"VaR_{int(cl*100)}"] = round(var_value, 6)
        results[f"CVaR_{int(cl*100)}"] = round(cvar_value, 6)

    return results


def compute_var(
    returns: pd.Series,
    confidence_levels: List[float] = [0.95, 0.99],
    num_simulations: int = 10_000,
    horizon_days: int = 1,
    initial_price: float = 100.0,
) -> Dict:
    """Convenience wrapper returning all three VaR methods."""
    return {
        "historical": historical_var(returns, confidence_levels),
        "parametric": parametric_var(returns, confidence_levels),
        "monte_carlo": monte_carlo_var(
            returns, confidence_levels, num_simulations, horizon_days, initial_price
        ),
    }


# ---------------------------------------------------------------------------
# 3. Performance Ratios
# ---------------------------------------------------------------------------

def sharpe_ratio(returns: pd.Series, risk_free_rate: float = RISK_FREE_RATE) -> float:
    """Sharpe = (Rp - Rf) / sigma_p  (annualized)."""
    excess = returns.mean() * TRADING_DAYS_PER_YEAR - risk_free_rate
    sigma = returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    return round(float(excess / sigma) if sigma != 0 else 0.0, 4)


def sortino_ratio(returns: pd.Series, risk_free_rate: float = RISK_FREE_RATE) -> float:
    """Sortino = (Rp - Rf) / sigma_downside  (annualized)."""
    excess = returns.mean() * TRADING_DAYS_PER_YEAR - risk_free_rate
    downside = returns[returns < 0]
    sigma_down = downside.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    return round(float(excess / sigma_down) if sigma_down != 0 else 0.0, 4)


def calmar_ratio(returns: pd.Series) -> float:
    """Calmar = Annualized Return / |Max Drawdown|."""
    ann_return = returns.mean() * TRADING_DAYS_PER_YEAR
    dd_info = max_drawdown(returns)
    mdd = abs(dd_info["max_drawdown"])
    return round(float(ann_return / mdd) if mdd != 0 else 0.0, 4)


def treynor_ratio(
    returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free_rate: float = RISK_FREE_RATE,
) -> float:
    """Treynor = (Rp - Rf) / beta."""
    excess_p = returns.mean() * TRADING_DAYS_PER_YEAR - risk_free_rate
    beta = _compute_beta(returns, benchmark_returns)
    return round(float(excess_p / beta) if beta != 0 else 0.0, 4)


def information_ratio(
    returns: pd.Series,
    benchmark_returns: pd.Series,
) -> float:
    """Information Ratio = (Rp - Rb) / Tracking Error."""
    # Align by index
    aligned = pd.DataFrame({"port": returns, "bench": benchmark_returns}).dropna()
    active = aligned["port"] - aligned["bench"]
    tracking_error = active.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    active_return = active.mean() * TRADING_DAYS_PER_YEAR
    return round(float(active_return / tracking_error) if tracking_error != 0 else 0.0, 4)


def _compute_beta(returns: pd.Series, benchmark_returns: pd.Series) -> float:
    aligned = pd.DataFrame({"port": returns, "bench": benchmark_returns}).dropna()
    cov = aligned.cov()
    bench_var = cov.loc["bench", "bench"]
    if bench_var == 0:
        return 0.0
    return float(cov.loc["port", "bench"] / bench_var)


def compute_performance_ratios(
    returns: pd.Series,
    benchmark_returns: Optional[pd.Series] = None,
    risk_free_rate: float = RISK_FREE_RATE,
) -> Dict:
    """Compute all performance ratios in one call."""
    result = {
        "sharpe": sharpe_ratio(returns, risk_free_rate),
        "sortino": sortino_ratio(returns, risk_free_rate),
        "calmar": calmar_ratio(returns),
        "annualized_return": round(float(returns.mean() * TRADING_DAYS_PER_YEAR), 6),
        "annualized_volatility": round(
            float(returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)), 6
        ),
    }
    if benchmark_returns is not None:
        result["treynor"] = treynor_ratio(returns, benchmark_returns, risk_free_rate)
        result["information_ratio"] = information_ratio(returns, benchmark_returns)
        result["beta"] = round(_compute_beta(returns, benchmark_returns), 4)
    return result


# ---------------------------------------------------------------------------
# 4. Max Drawdown with Recovery Time
# ---------------------------------------------------------------------------

def max_drawdown(returns: pd.Series) -> Dict:
    """
    Compute maximum drawdown, peak/trough dates, and recovery time.

    Parameters
    ----------
    returns : pd.Series
        Daily returns (not cumulative).

    Returns
    -------
    dict with max_drawdown (negative fraction), peak_date, trough_date,
    recovery_date (or None), recovery_days, drawdown_curve.
    """
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown_curve = (cumulative - running_max) / running_max

    # Max drawdown value and location
    max_dd = float(drawdown_curve.min())
    trough_idx = drawdown_curve.idxmin()

    # Peak is the running max just before the trough
    peak_idx = cumulative.loc[:trough_idx].idxmax()

    # Recovery: first time cumulative reaches the peak value after the trough
    peak_value = cumulative.loc[peak_idx]
    post_trough = cumulative.loc[trough_idx:]
    recovered = post_trough[post_trough >= peak_value]
    recovery_idx = recovered.index[0] if len(recovered) > 0 else None

    recovery_days = None
    if recovery_idx is not None and hasattr(trough_idx, "date"):
        recovery_days = (recovery_idx - trough_idx).days

    return {
        "max_drawdown": round(max_dd, 6),
        "peak_date": str(peak_idx),
        "trough_date": str(trough_idx),
        "recovery_date": str(recovery_idx) if recovery_idx is not None else None,
        "recovery_days": recovery_days,
        "drawdown_curve": drawdown_curve,
    }


# ---------------------------------------------------------------------------
# 5. Portfolio Correlation Matrix
# ---------------------------------------------------------------------------

def correlation_matrix(returns_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute pairwise Pearson correlation matrix.

    Parameters
    ----------
    returns_df : pd.DataFrame
        Columns are asset daily returns.

    Returns
    -------
    pd.DataFrame -- correlation matrix.
    """
    return returns_df.corr()


# ---------------------------------------------------------------------------
# 6. Efficient Frontier
# ---------------------------------------------------------------------------

def efficient_frontier(
    returns_df: pd.DataFrame,
    num_portfolios: int = 5000,
    risk_free_rate: float = RISK_FREE_RATE,
    seed: Optional[int] = 42,
) -> Dict:
    """
    Generate random portfolios and identify max-Sharpe and min-variance.

    Parameters
    ----------
    returns_df : pd.DataFrame
        Columns = asset daily returns.
    num_portfolios : int
        Number of random weight combinations.
    risk_free_rate : float
        Annualized risk-free rate.

    Returns
    -------
    dict with portfolio_returns, portfolio_volatilities, portfolio_sharpes,
    portfolio_weights, max_sharpe_portfolio, min_variance_portfolio.
    """
    if seed is not None:
        np.random.seed(seed)

    num_assets = returns_df.shape[1]
    mean_returns = returns_df.mean() * TRADING_DAYS_PER_YEAR
    cov_matrix = returns_df.cov() * TRADING_DAYS_PER_YEAR

    all_returns = np.zeros(num_portfolios)
    all_volatilities = np.zeros(num_portfolios)
    all_sharpes = np.zeros(num_portfolios)
    all_weights = np.zeros((num_portfolios, num_assets))

    for i in range(num_portfolios):
        # Random weights that sum to 1
        w = np.random.random(num_assets)
        w /= w.sum()

        port_return = float(np.dot(w, mean_returns))
        port_vol = float(np.sqrt(np.dot(w.T, np.dot(cov_matrix.values, w))))
        port_sharpe = (port_return - risk_free_rate) / port_vol if port_vol != 0 else 0.0

        all_returns[i] = port_return
        all_volatilities[i] = port_vol
        all_sharpes[i] = port_sharpe
        all_weights[i] = w

    max_sharpe_idx = int(np.argmax(all_sharpes))
    min_var_idx = int(np.argmin(all_volatilities))

    asset_names = list(returns_df.columns)

    def _portfolio_summary(idx: int) -> Dict:
        return {
            "return": round(float(all_returns[idx]), 6),
            "volatility": round(float(all_volatilities[idx]), 6),
            "sharpe": round(float(all_sharpes[idx]), 4),
            "weights": {
                asset_names[j]: round(float(all_weights[idx][j]), 4)
                for j in range(num_assets)
            },
        }

    return {
        "num_portfolios": num_portfolios,
        "portfolio_returns": all_returns.tolist(),
        "portfolio_volatilities": all_volatilities.tolist(),
        "portfolio_sharpes": all_sharpes.tolist(),
        "portfolio_weights": all_weights.tolist(),
        "max_sharpe_portfolio": _portfolio_summary(max_sharpe_idx),
        "min_variance_portfolio": _portfolio_summary(min_var_idx),
        "asset_names": asset_names,
    }


# ---------------------------------------------------------------------------
# 7. Position Sizing for INR 1 Lakh Capital
# ---------------------------------------------------------------------------

def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range (ATR) over *period* days."""
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.rolling(window=period).mean()


def position_sizing(
    entry_price: float,
    atr_value: float,
    capital: float = DEFAULT_CAPITAL,
    risk_pct: float = 0.02,
    atr_multiplier: float = 2.0,
) -> Dict:
    """
    Position sizing based on ATR stop-loss.

    Stop loss = Entry - atr_multiplier * ATR(14)
    Risk per trade = Capital * risk_pct
    Position size (shares) = Risk amount / Stop distance
    Position value = shares * entry_price

    Parameters
    ----------
    entry_price : float
        Entry price per share.
    atr_value : float
        Current ATR(14) value.
    capital : float
        Total portfolio capital (default 1,00,000).
    risk_pct : float
        Maximum risk per trade as fraction (default 0.02 = 2%).
    atr_multiplier : float
        Stop-loss distance in ATR multiples (default 2).

    Returns
    -------
    dict with all sizing details.
    """
    stop_distance = atr_multiplier * atr_value
    stop_loss_price = entry_price - stop_distance
    risk_amount = capital * risk_pct
    shares = int(risk_amount / stop_distance) if stop_distance > 0 else 0
    position_value = shares * entry_price
    position_pct = (position_value / capital) * 100 if capital > 0 else 0.0

    return {
        "capital": capital,
        "risk_pct": risk_pct,
        "risk_amount_inr": round(risk_amount, 2),
        "entry_price": round(entry_price, 2),
        "atr_value": round(atr_value, 2),
        "atr_multiplier": atr_multiplier,
        "stop_loss_price": round(stop_loss_price, 2),
        "stop_distance": round(stop_distance, 2),
        "shares": shares,
        "position_value_inr": round(position_value, 2),
        "position_pct_of_capital": round(position_pct, 2),
    }


# ---------------------------------------------------------------------------
# Master function: full portfolio risk report
# ---------------------------------------------------------------------------

def full_risk_report(
    returns: pd.Series,
    benchmark_returns: Optional[pd.Series] = None,
    portfolio_returns_df: Optional[pd.DataFrame] = None,
    capital: float = DEFAULT_CAPITAL,
) -> Dict:
    """
    Generate a comprehensive risk report.

    Parameters
    ----------
    returns : pd.Series
        Daily portfolio returns.
    benchmark_returns : pd.Series, optional
        Daily benchmark returns (e.g., Nifty 50).
    portfolio_returns_df : pd.DataFrame, optional
        Multi-asset returns for correlation and efficient frontier.
    capital : float
        Portfolio capital in INR.

    Returns
    -------
    dict with all risk metrics.
    """
    report: Dict = {}

    # Performance ratios
    report["performance"] = compute_performance_ratios(
        returns, benchmark_returns
    )

    # VaR
    report["var"] = compute_var(returns)

    # Drawdown
    dd = max_drawdown(returns)
    # Remove the curve from the summary (it's a Series)
    dd_summary = {k: v for k, v in dd.items() if k != "drawdown_curve"}
    report["drawdown"] = dd_summary

    # Correlation matrix and efficient frontier (need multi-asset data)
    if portfolio_returns_df is not None and portfolio_returns_df.shape[1] >= 2:
        report["correlation_matrix"] = correlation_matrix(portfolio_returns_df).to_dict()
        ef = efficient_frontier(portfolio_returns_df)
        # Strip large arrays for summary
        report["efficient_frontier"] = {
            "max_sharpe_portfolio": ef["max_sharpe_portfolio"],
            "min_variance_portfolio": ef["min_variance_portfolio"],
            "num_portfolios": ef["num_portfolios"],
            "asset_names": ef["asset_names"],
        }

    return report
