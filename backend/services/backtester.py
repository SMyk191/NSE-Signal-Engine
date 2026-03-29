from __future__ import annotations

"""
Backtesting Engine for NSE Signal Engine.

Full-featured backtester with Indian market transaction costs (Zerodha model),
slippage, and comprehensive performance reporting.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Indian Market Transaction Cost Calculator
# ---------------------------------------------------------------------------

def calculate_costs(
    buy_price: float,
    sell_price: float,
    quantity: int,
    is_intraday: bool = False,
) -> Dict:
    """
    Full Indian equity market transaction cost model (Zerodha / discount broker).

    Costs on BUY side:
        - Brokerage: min(20, turnover * 0.03%)
        - Stamp duty: 0.015% of buy turnover
        - Exchange txn charges
        - SEBI charges
        - GST on (brokerage + exchange + SEBI)

    Costs on SELL side:
        - Brokerage: min(20, turnover * 0.03%)
        - STT: 0.1% of sell turnover (delivery); 0.025% sell side for intraday
        - Exchange txn charges
        - SEBI charges
        - GST on (brokerage + exchange + SEBI)

    Parameters
    ----------
    buy_price : float
        Price per share at entry.
    sell_price : float
        Price per share at exit.
    quantity : int
        Number of shares traded.
    is_intraday : bool
        True for intraday, False for delivery.

    Returns
    -------
    dict with itemized costs and total.
    """
    buy_turnover = buy_price * quantity
    sell_turnover = sell_price * quantity
    total_turnover = buy_turnover + sell_turnover

    # --- Brokerage (per leg) ---
    buy_brokerage = min(20.0, buy_turnover * 0.0003)
    sell_brokerage = min(20.0, sell_turnover * 0.0003)
    total_brokerage = buy_brokerage + sell_brokerage

    # --- STT ---
    if is_intraday:
        # Intraday: 0.025% on sell side only
        stt = sell_turnover * 0.00025
    else:
        # Delivery: 0.1% on sell side
        stt = sell_turnover * 0.001

    # --- Exchange transaction charges (NSE equity) ---
    exchange_rate = 0.0000297
    buy_exchange = buy_turnover * exchange_rate
    sell_exchange = sell_turnover * exchange_rate
    total_exchange = buy_exchange + sell_exchange

    # --- SEBI turnover fee ---
    sebi_rate = 0.000001
    buy_sebi = buy_turnover * sebi_rate
    sell_sebi = sell_turnover * sebi_rate
    total_sebi = buy_sebi + sell_sebi

    # --- GST @ 18% on (brokerage + exchange charges + SEBI charges) ---
    gst_base = total_brokerage + total_exchange + total_sebi
    gst = gst_base * 0.18

    # --- Stamp duty: 0.015% on buy side ---
    stamp_duty = buy_turnover * 0.00015

    # --- Totals ---
    total_costs = total_brokerage + stt + total_exchange + total_sebi + gst + stamp_duty

    return {
        "buy_turnover": round(buy_turnover, 2),
        "sell_turnover": round(sell_turnover, 2),
        "total_turnover": round(total_turnover, 2),
        "brokerage": round(total_brokerage, 2),
        "stt": round(stt, 2),
        "exchange_charges": round(total_exchange, 4),
        "sebi_charges": round(total_sebi, 4),
        "gst": round(gst, 4),
        "stamp_duty": round(stamp_duty, 4),
        "total_costs": round(total_costs, 2),
        "cost_pct_of_turnover": round((total_costs / total_turnover) * 100, 4)
        if total_turnover > 0
        else 0.0,
    }


# ---------------------------------------------------------------------------
# Backtest Result
# ---------------------------------------------------------------------------

@dataclass
class BacktestResult:
    """Container for all backtest outputs."""

    total_return: float = 0.0
    cagr: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win_loss_ratio: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    equity_curve: pd.Series = field(default_factory=pd.Series)
    drawdown_curve: pd.Series = field(default_factory=pd.Series)
    trade_log: pd.DataFrame = field(default_factory=pd.DataFrame)
    monthly_returns: pd.Series = field(default_factory=pd.Series)
    costs_total: float = 0.0
    slippage_total: float = 0.0

    def summary(self) -> Dict:
        return {
            "total_return_pct": round(self.total_return * 100, 2),
            "cagr_pct": round(self.cagr * 100, 2),
            "max_drawdown_pct": round(self.max_drawdown * 100, 2),
            "sharpe_ratio": round(self.sharpe, 4),
            "win_rate_pct": round(self.win_rate * 100, 2),
            "profit_factor": round(self.profit_factor, 4),
            "avg_win_loss_ratio": round(self.avg_win_loss_ratio, 4),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_costs_inr": round(self.costs_total, 2),
            "total_slippage_inr": round(self.slippage_total, 2),
        }


# ---------------------------------------------------------------------------
# Backtester
# ---------------------------------------------------------------------------

SLIPPAGE_PCT = 0.0005  # 0.05%
RISK_FREE_RATE = 0.07
TRADING_DAYS = 252


class Backtester:
    """
    Event-driven backtester for NSE equities.

    Parameters
    ----------
    initial_capital : float
        Starting capital in INR (default 1,00,000).
    slippage_pct : float
        Slippage per trade as a fraction (default 0.05%).
    is_intraday : bool
        Trade type for cost calculation.
    """

    def __init__(
        self,
        initial_capital: float = 100_000,
        slippage_pct: float = SLIPPAGE_PCT,
        is_intraday: bool = False,
    ):
        self.initial_capital = initial_capital
        self.slippage_pct = slippage_pct
        self.is_intraday = is_intraday

    def run(
        self,
        df: pd.DataFrame,
        signals_df: pd.DataFrame,
        entry_threshold: float = 30,
        exit_threshold: float = -10,
    ) -> BacktestResult:
        """
        Run the backtest.

        Parameters
        ----------
        df : pd.DataFrame
            OHLCV price data with columns: date/index, open, high, low, close, volume.
        signals_df : pd.DataFrame
            Signal data aligned with df. Must contain a 'signal' column with
            numeric scores. Entry when signal >= entry_threshold, exit when
            signal <= exit_threshold.
        entry_threshold : float
            Signal score to trigger a buy.
        exit_threshold : float
            Signal score to trigger a sell.

        Returns
        -------
        BacktestResult
        """
        # Normalize column names to lowercase
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        signals_df = signals_df.copy()
        signals_df.columns = [c.lower() for c in signals_df.columns]

        # Ensure aligned indices
        if "date" in df.columns:
            df = df.set_index("date")
        if "date" in signals_df.columns:
            signals_df = signals_df.set_index("date")

        common_idx = df.index.intersection(signals_df.index)
        df = df.loc[common_idx]
        signals_df = signals_df.loc[common_idx]

        capital = self.initial_capital
        position = 0  # shares held
        entry_price = 0.0

        equity_values = []
        trade_records = []
        total_costs = 0.0
        total_slippage = 0.0

        for i, date in enumerate(df.index):
            close = float(df.loc[date, "close"])
            signal_val = float(signals_df.loc[date, "signal"])
            current_equity = capital + position * close

            # --- ENTRY ---
            if position == 0 and signal_val >= entry_threshold:
                # Apply slippage: buy at slightly higher price
                slipped_price = close * (1 + self.slippage_pct)
                # How many shares can we buy?
                max_shares = int(capital / slipped_price)
                if max_shares > 0:
                    # Calculate expected costs to reserve
                    est_costs = calculate_costs(
                        slipped_price, slipped_price, max_shares, self.is_intraday
                    )["total_costs"]
                    # Adjust for costs
                    affordable = int((capital - est_costs) / slipped_price)
                    if affordable > 0:
                        position = affordable
                        entry_price = slipped_price
                        buy_cost = position * entry_price
                        costs = calculate_costs(
                            entry_price, entry_price, position, self.is_intraday
                        )
                        # Only buy-side costs at entry (stamp duty, half brokerage, etc.)
                        entry_cost = (
                            costs["brokerage"] / 2
                            + costs["stamp_duty"]
                            + costs["exchange_charges"] / 2
                            + costs["sebi_charges"] / 2
                            + costs["gst"] / 2
                        )
                        slip_cost = position * close * self.slippage_pct
                        capital -= buy_cost + entry_cost
                        total_costs += entry_cost
                        total_slippage += slip_cost

            # --- EXIT ---
            elif position > 0 and signal_val <= exit_threshold:
                # Apply slippage: sell at slightly lower price
                slipped_price = close * (1 - self.slippage_pct)
                sell_value = position * slipped_price

                costs = calculate_costs(
                    entry_price, slipped_price, position, self.is_intraday
                )
                # Sell-side costs: brokerage/2 + STT + exchange/2 + sebi/2 + gst/2
                exit_cost = (
                    costs["brokerage"] / 2
                    + costs["stt"]
                    + costs["exchange_charges"] / 2
                    + costs["sebi_charges"] / 2
                    + costs["gst"] / 2
                )
                slip_cost = position * close * self.slippage_pct
                pnl = sell_value - (position * entry_price) - exit_cost

                capital += sell_value - exit_cost
                total_costs += exit_cost
                total_slippage += slip_cost

                trade_records.append(
                    {
                        "entry_date": str(df.index[max(0, i - 1)]),
                        "exit_date": str(date),
                        "entry_price": round(entry_price, 2),
                        "exit_price": round(slipped_price, 2),
                        "quantity": position,
                        "pnl": round(pnl, 2),
                        "return_pct": round(
                            (slipped_price / entry_price - 1) * 100, 2
                        ),
                        "costs": round(exit_cost + (costs["brokerage"] / 2), 2),
                    }
                )

                position = 0
                entry_price = 0.0

            current_equity = capital + position * close
            equity_values.append({"date": date, "equity": current_equity})

        # --- Build equity curve ---
        equity_df = pd.DataFrame(equity_values).set_index("date")
        equity_curve = equity_df["equity"]

        # --- Daily returns from equity curve ---
        daily_returns = equity_curve.pct_change().dropna()

        # --- Drawdown curve ---
        running_max = equity_curve.cummax()
        drawdown_curve = (equity_curve - running_max) / running_max

        # --- Trade statistics ---
        trade_log = pd.DataFrame(trade_records)
        total_trades = len(trade_records)

        if total_trades > 0:
            pnls = trade_log["pnl"]
            wins = pnls[pnls > 0]
            losses = pnls[pnls <= 0]
            winning_trades = len(wins)
            losing_trades = len(losses)
            win_rate = winning_trades / total_trades

            gross_profit = wins.sum() if len(wins) > 0 else 0.0
            gross_loss = abs(losses.sum()) if len(losses) > 0 else 0.0
            profit_factor = (
                gross_profit / gross_loss if gross_loss > 0 else float("inf")
            )

            avg_win = wins.mean() if len(wins) > 0 else 0.0
            avg_loss = abs(losses.mean()) if len(losses) > 0 else 0.0
            avg_win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else float("inf")
        else:
            winning_trades = 0
            losing_trades = 0
            win_rate = 0.0
            profit_factor = 0.0
            avg_win_loss_ratio = 0.0

        # --- Total return ---
        final_equity = float(equity_curve.iloc[-1]) if len(equity_curve) > 0 else self.initial_capital
        total_return = (final_equity / self.initial_capital) - 1

        # --- CAGR ---
        num_days = len(equity_curve)
        num_years = num_days / TRADING_DAYS if num_days > 0 else 1
        cagr = (final_equity / self.initial_capital) ** (1 / num_years) - 1 if num_years > 0 else 0.0

        # --- Sharpe ---
        if len(daily_returns) > 1:
            excess = daily_returns.mean() * TRADING_DAYS - RISK_FREE_RATE
            vol = daily_returns.std() * np.sqrt(TRADING_DAYS)
            sharpe = excess / vol if vol != 0 else 0.0
        else:
            sharpe = 0.0

        # --- Max drawdown ---
        max_dd = float(drawdown_curve.min()) if len(drawdown_curve) > 0 else 0.0

        # --- Monthly returns ---
        if hasattr(equity_curve.index, "to_period"):
            try:
                monthly_equity = equity_curve.resample("ME").last()
            except ValueError:
                monthly_equity = equity_curve.resample("M").last()
            monthly_returns = monthly_equity.pct_change().dropna()
        else:
            monthly_returns = pd.Series(dtype=float)

        return BacktestResult(
            total_return=total_return,
            cagr=cagr,
            max_drawdown=max_dd,
            sharpe=sharpe,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win_loss_ratio=avg_win_loss_ratio,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            equity_curve=equity_curve,
            drawdown_curve=drawdown_curve,
            trade_log=trade_log,
            monthly_returns=monthly_returns,
            costs_total=total_costs,
            slippage_total=total_slippage,
        )


# ---------------------------------------------------------------------------
# Convenience: quick backtest from a single DataFrame
# ---------------------------------------------------------------------------

def quick_backtest(
    df: pd.DataFrame,
    signal_column: str = "signal",
    entry_threshold: float = 30,
    exit_threshold: float = -10,
    initial_capital: float = 100_000,
) -> BacktestResult:
    """
    Run a backtest when signals are already in the price DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: close (price) and a signal column.
    signal_column : str
        Name of the signal column.
    entry_threshold, exit_threshold : float
        Thresholds for entry/exit.
    initial_capital : float
        Starting capital in INR.

    Returns
    -------
    BacktestResult
    """
    price_df = df[["open", "high", "low", "close", "volume"]].copy()
    signals_df = df[[signal_column]].rename(columns={signal_column: "signal"}).copy()

    bt = Backtester(initial_capital=initial_capital)
    return bt.run(price_df, signals_df, entry_threshold, exit_threshold)
