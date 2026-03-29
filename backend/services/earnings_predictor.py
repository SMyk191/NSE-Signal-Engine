from __future__ import annotations

"""
Earnings & Fundamentals Analysis
Provides earnings history, margin analysis, growth metrics, and financial health scores.
"""

import logging
from typing import Optional

import yfinance as yf

logger = logging.getLogger(__name__)


def _safe_div(numerator, denominator, default=None):
    """Safe division that returns default on zero/None."""
    if numerator is None or denominator is None:
        return default
    try:
        if denominator == 0:
            return default
        return numerator / denominator
    except (TypeError, ZeroDivisionError):
        return default


def _get_item(df, key, col_index=0):
    """Safely get a value from a yfinance DataFrame (financials/balance_sheet/cashflow)."""
    try:
        if df is None or df.empty:
            return None
        if key in df.index:
            val = df.iloc[df.index.get_loc(key), col_index]
            if val is not None and str(val) != "nan":
                return float(val)
    except (KeyError, IndexError, ValueError, TypeError):
        pass
    return None


class EarningsPredictor:
    """Earnings and fundamentals analysis using yfinance data."""

    def __init__(self):
        self._ticker_cache: dict[str, yf.Ticker] = {}

    def _get_ticker(self, symbol: str) -> yf.Ticker:
        if symbol not in self._ticker_cache:
            self._ticker_cache[symbol] = yf.Ticker(symbol)
        return self._ticker_cache[symbol]

    # ------------------------------------------------------------------ #
    #  1. Earnings History — last 8 quarters EPS estimate vs actual
    # ------------------------------------------------------------------ #
    def get_earnings_history(self, symbol: str) -> Optional[list[dict]]:
        """
        Returns last 8 quarters of EPS data:
        [{quarter, estimate, actual, surprise, surprise_pct}, ...]
        """
        try:
            ticker = self._get_ticker(symbol)
            earnings = ticker.earnings_dates
            if earnings is None or earnings.empty:
                return None

            results = []
            count = 0
            for idx, row in earnings.iterrows():
                if count >= 8:
                    break
                estimate = row.get("EPS Estimate")
                actual = row.get("Reported EPS")
                if actual is None or str(actual) == "nan":
                    continue

                estimate_val = float(estimate) if estimate is not None and str(estimate) != "nan" else None
                actual_val = float(actual)
                surprise = None
                surprise_pct = None

                if estimate_val is not None:
                    surprise = actual_val - estimate_val
                    surprise_pct = _safe_div(surprise, abs(estimate_val))
                    if surprise_pct is not None:
                        surprise_pct = round(surprise_pct * 100, 2)

                results.append({
                    "quarter": str(idx.date()) if hasattr(idx, "date") else str(idx),
                    "estimate": round(estimate_val, 4) if estimate_val is not None else None,
                    "actual": round(actual_val, 4),
                    "surprise": round(surprise, 4) if surprise is not None else None,
                    "surprise_pct": surprise_pct,
                })
                count += 1

            return results if results else None

        except Exception as e:
            logger.error(f"Error fetching earnings history for {symbol}: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  2. Margin Analysis — gross, operating, net margins
    # ------------------------------------------------------------------ #
    def compute_margin_analysis(self, symbol: str) -> Optional[dict]:
        """
        Compute gross, operating, and net margins from income statement.
        Returns margins for the most recent period and trend direction.
        """
        try:
            ticker = self._get_ticker(symbol)
            financials = ticker.financials
            if financials is None or financials.empty:
                return None

            revenue = _get_item(financials, "Total Revenue", 0)
            gross_profit = _get_item(financials, "Gross Profit", 0)
            operating_income = _get_item(financials, "Operating Income", 0)
            net_income = _get_item(financials, "Net Income", 0)

            if revenue is None or revenue == 0:
                return None

            gross_margin = _safe_div(gross_profit, revenue)
            operating_margin = _safe_div(operating_income, revenue)
            net_margin = _safe_div(net_income, revenue)

            # Compute trend if prior period available
            trend = "stable"
            if financials.shape[1] >= 2:
                prev_revenue = _get_item(financials, "Total Revenue", 1)
                prev_net_income = _get_item(financials, "Net Income", 1)
                prev_net_margin = _safe_div(prev_net_income, prev_revenue)
                if net_margin is not None and prev_net_margin is not None:
                    if net_margin > prev_net_margin + 0.01:
                        trend = "improving"
                    elif net_margin < prev_net_margin - 0.01:
                        trend = "declining"

            return {
                "gross_margin": round(gross_margin * 100, 2) if gross_margin is not None else None,
                "operating_margin": round(operating_margin * 100, 2) if operating_margin is not None else None,
                "net_margin": round(net_margin * 100, 2) if net_margin is not None else None,
                "trend": trend,
            }

        except Exception as e:
            logger.error(f"Error computing margins for {symbol}: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  3. EPS Growth — QoQ and YoY
    # ------------------------------------------------------------------ #
    def compute_eps_growth(self, symbol: str) -> Optional[dict]:
        """Compute quarter-over-quarter and year-over-year EPS growth."""
        try:
            history = self.get_earnings_history(symbol)
            if not history or len(history) < 2:
                return None

            result = {}

            # QoQ: compare most recent to previous quarter
            current = history[0].get("actual")
            previous = history[1].get("actual")
            if current is not None and previous is not None:
                result["qoq_growth_pct"] = round(
                    _safe_div(current - previous, abs(previous), 0) * 100, 2
                )
                result["current_eps"] = current
                result["previous_eps"] = previous

            # YoY: compare most recent to same quarter last year (4 quarters ago)
            if len(history) >= 5:
                year_ago = history[4].get("actual")
                if current is not None and year_ago is not None:
                    result["yoy_growth_pct"] = round(
                        _safe_div(current - year_ago, abs(year_ago), 0) * 100, 2
                    )
                    result["year_ago_eps"] = year_ago

            return result if result else None

        except Exception as e:
            logger.error(f"Error computing EPS growth for {symbol}: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  4. PEG Ratio — P/E divided by EPS growth rate
    # ------------------------------------------------------------------ #
    def compute_peg_ratio(self, symbol: str) -> Optional[float]:
        """PEG = P/E ratio / EPS growth rate."""
        try:
            ticker = self._get_ticker(symbol)
            info = ticker.info or {}
            pe_ratio = info.get("trailingPE") or info.get("forwardPE")
            if pe_ratio is None:
                return None

            eps_growth = self.compute_eps_growth(symbol)
            if eps_growth is None:
                return None

            growth_rate = eps_growth.get("yoy_growth_pct") or eps_growth.get("qoq_growth_pct")
            if growth_rate is None or growth_rate == 0:
                return None

            peg = pe_ratio / growth_rate
            return round(peg, 4)

        except Exception as e:
            logger.error(f"Error computing PEG ratio for {symbol}: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  5. Accrual Ratio — (Net Income - Operating CF) / Total Assets
    # ------------------------------------------------------------------ #
    def compute_accrual_ratio(self, symbol: str) -> Optional[float]:
        """Accrual Ratio = (Net Income - Operating Cash Flow) / Total Assets."""
        try:
            ticker = self._get_ticker(symbol)
            financials = ticker.financials
            cashflow = ticker.cashflow
            balance = ticker.balance_sheet

            if any(df is None or df.empty for df in [financials, cashflow, balance]):
                return None

            net_income = _get_item(financials, "Net Income", 0)
            operating_cf = _get_item(cashflow, "Operating Cash Flow", 0)
            # yfinance sometimes labels it differently
            if operating_cf is None:
                operating_cf = _get_item(cashflow, "Total Cash From Operating Activities", 0)
            total_assets = _get_item(balance, "Total Assets", 0)

            if any(v is None for v in [net_income, operating_cf, total_assets]):
                return None
            if total_assets == 0:
                return None

            ratio = (net_income - operating_cf) / total_assets
            return round(ratio, 4)

        except Exception as e:
            logger.error(f"Error computing accrual ratio for {symbol}: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  6. Altman Z-Score
    # ------------------------------------------------------------------ #
    def compute_altman_z_score(self, symbol: str) -> Optional[dict]:
        """
        Altman Z-Score = 1.2*(WC/TA) + 1.4*(RE/TA) + 3.3*(EBIT/TA) + 0.6*(MC/TL) + 1.0*(Rev/TA)

        Interpretation:
            Z > 2.99  -> Safe
            1.81 - 2.99 -> Gray zone
            Z < 1.81  -> Distress
        """
        try:
            ticker = self._get_ticker(symbol)
            balance = ticker.balance_sheet
            financials = ticker.financials
            info = ticker.info or {}

            if balance is None or balance.empty or financials is None or financials.empty:
                return None

            total_assets = _get_item(balance, "Total Assets", 0)
            if total_assets is None or total_assets == 0:
                return None

            # Working Capital = Current Assets - Current Liabilities
            current_assets = _get_item(balance, "Current Assets", 0)
            current_liabilities = _get_item(balance, "Current Liabilities", 0)
            working_capital = None
            if current_assets is not None and current_liabilities is not None:
                working_capital = current_assets - current_liabilities

            # Retained Earnings
            retained_earnings = _get_item(balance, "Retained Earnings", 0)

            # EBIT
            ebit = _get_item(financials, "EBIT", 0)
            if ebit is None:
                # Approximate: Operating Income
                ebit = _get_item(financials, "Operating Income", 0)

            # Market Cap
            market_cap = info.get("marketCap")

            # Total Liabilities
            total_liabilities = _get_item(balance, "Total Liabilities Net Minority Interest", 0)
            if total_liabilities is None:
                total_liabilities = _get_item(balance, "Total Liab", 0)
            # Fallback: total_assets - stockholders_equity
            if total_liabilities is None:
                equity = _get_item(balance, "Stockholders Equity", 0)
                if equity is not None:
                    total_liabilities = total_assets - equity

            # Revenue
            revenue = _get_item(financials, "Total Revenue", 0)

            # Compute components
            a = _safe_div(working_capital, total_assets, 0)
            b = _safe_div(retained_earnings, total_assets, 0)
            c = _safe_div(ebit, total_assets, 0)
            d = _safe_div(market_cap, total_liabilities, 0) if total_liabilities and total_liabilities > 0 else 0
            e = _safe_div(revenue, total_assets, 0)

            z_score = 1.2 * a + 1.4 * b + 3.3 * c + 0.6 * d + 1.0 * e

            if z_score > 2.99:
                zone = "safe"
            elif z_score >= 1.81:
                zone = "gray"
            else:
                zone = "distress"

            return {
                "z_score": round(z_score, 4),
                "zone": zone,
                "components": {
                    "wc_ta": round(a, 4),
                    "re_ta": round(b, 4),
                    "ebit_ta": round(c, 4),
                    "mc_tl": round(d, 4),
                    "rev_ta": round(e, 4),
                },
            }

        except Exception as e:
            logger.error(f"Error computing Altman Z-Score for {symbol}: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  7. Piotroski F-Score — 9-point scoring system
    # ------------------------------------------------------------------ #
    def compute_piotroski_f_score(self, symbol: str) -> Optional[dict]:
        """
        Piotroski F-Score: 9 binary signals (0 or 1) summed.

        Profitability (4 points):
            1. ROA > 0
            2. Operating Cash Flow > 0
            3. ROA increasing (vs prior year)
            4. Cash flow from operations > Net Income (accruals)

        Leverage/Liquidity (3 points):
            5. Long-term debt ratio decreasing
            6. Current ratio increasing
            7. No new shares issued

        Operating Efficiency (2 points):
            8. Gross margin increasing
            9. Asset turnover increasing
        """
        try:
            ticker = self._get_ticker(symbol)
            financials = ticker.financials
            balance = ticker.balance_sheet
            cashflow = ticker.cashflow

            if any(df is None or df.empty for df in [financials, balance, cashflow]):
                return None

            # Need at least 2 periods for comparisons
            has_prior = financials.shape[1] >= 2 and balance.shape[1] >= 2 and cashflow.shape[1] >= 2

            criteria = {}
            total = 0

            # --- Current period values ---
            net_income = _get_item(financials, "Net Income", 0)
            total_assets = _get_item(balance, "Total Assets", 0)
            operating_cf = _get_item(cashflow, "Operating Cash Flow", 0)
            if operating_cf is None:
                operating_cf = _get_item(cashflow, "Total Cash From Operating Activities", 0)
            revenue = _get_item(financials, "Total Revenue", 0)
            gross_profit = _get_item(financials, "Gross Profit", 0)
            current_assets = _get_item(balance, "Current Assets", 0)
            current_liabilities = _get_item(balance, "Current Liabilities", 0)
            long_term_debt = _get_item(balance, "Long Term Debt", 0)
            shares_outstanding = _get_item(balance, "Share Issued", 0)
            if shares_outstanding is None:
                shares_outstanding = _get_item(balance, "Ordinary Shares Number", 0)

            # --- Prior period values ---
            prev_net_income = _get_item(financials, "Net Income", 1) if has_prior else None
            prev_total_assets = _get_item(balance, "Total Assets", 1) if has_prior else None
            prev_revenue = _get_item(financials, "Total Revenue", 1) if has_prior else None
            prev_gross_profit = _get_item(financials, "Gross Profit", 1) if has_prior else None
            prev_current_assets = _get_item(balance, "Current Assets", 1) if has_prior else None
            prev_current_liabilities = _get_item(balance, "Current Liabilities", 1) if has_prior else None
            prev_long_term_debt = _get_item(balance, "Long Term Debt", 1) if has_prior else None
            prev_shares = _get_item(balance, "Share Issued", 1) if has_prior else None
            if prev_shares is None and has_prior:
                prev_shares = _get_item(balance, "Ordinary Shares Number", 1)

            # --- PROFITABILITY ---

            # 1. ROA > 0
            roa = _safe_div(net_income, total_assets)
            criteria["roa_positive"] = 1 if roa is not None and roa > 0 else 0
            total += criteria["roa_positive"]

            # 2. Operating Cash Flow > 0
            criteria["ocf_positive"] = 1 if operating_cf is not None and operating_cf > 0 else 0
            total += criteria["ocf_positive"]

            # 3. ROA increasing
            prev_roa = _safe_div(prev_net_income, prev_total_assets)
            if roa is not None and prev_roa is not None:
                criteria["roa_increasing"] = 1 if roa > prev_roa else 0
            else:
                criteria["roa_increasing"] = 0
            total += criteria["roa_increasing"]

            # 4. Accruals: Operating CF > Net Income
            if operating_cf is not None and net_income is not None:
                criteria["accruals"] = 1 if operating_cf > net_income else 0
            else:
                criteria["accruals"] = 0
            total += criteria["accruals"]

            # --- LEVERAGE / LIQUIDITY ---

            # 5. Long-term debt ratio decreasing
            ltd_ratio = _safe_div(long_term_debt, total_assets)
            prev_ltd_ratio = _safe_div(prev_long_term_debt, prev_total_assets)
            if ltd_ratio is not None and prev_ltd_ratio is not None:
                criteria["leverage_decreasing"] = 1 if ltd_ratio < prev_ltd_ratio else 0
            elif long_term_debt is not None and long_term_debt == 0:
                criteria["leverage_decreasing"] = 1  # no debt is good
            else:
                criteria["leverage_decreasing"] = 0
            total += criteria["leverage_decreasing"]

            # 6. Current ratio increasing
            curr_ratio = _safe_div(current_assets, current_liabilities)
            prev_curr_ratio = _safe_div(prev_current_assets, prev_current_liabilities)
            if curr_ratio is not None and prev_curr_ratio is not None:
                criteria["current_ratio_increasing"] = 1 if curr_ratio > prev_curr_ratio else 0
            else:
                criteria["current_ratio_increasing"] = 0
            total += criteria["current_ratio_increasing"]

            # 7. No new shares issued
            if shares_outstanding is not None and prev_shares is not None:
                criteria["no_dilution"] = 1 if shares_outstanding <= prev_shares else 0
            else:
                criteria["no_dilution"] = 0
            total += criteria["no_dilution"]

            # --- OPERATING EFFICIENCY ---

            # 8. Gross margin increasing
            gm = _safe_div(gross_profit, revenue)
            prev_gm = _safe_div(prev_gross_profit, prev_revenue)
            if gm is not None and prev_gm is not None:
                criteria["gross_margin_increasing"] = 1 if gm > prev_gm else 0
            else:
                criteria["gross_margin_increasing"] = 0
            total += criteria["gross_margin_increasing"]

            # 9. Asset turnover increasing
            turnover = _safe_div(revenue, total_assets)
            prev_turnover = _safe_div(prev_revenue, prev_total_assets)
            if turnover is not None and prev_turnover is not None:
                criteria["asset_turnover_increasing"] = 1 if turnover > prev_turnover else 0
            else:
                criteria["asset_turnover_increasing"] = 0
            total += criteria["asset_turnover_increasing"]

            return {
                "f_score": total,
                "max_score": 9,
                "criteria": criteria,
                "interpretation": (
                    "strong" if total >= 7
                    else "moderate" if total >= 5
                    else "weak"
                ),
            }

        except Exception as e:
            logger.error(f"Error computing Piotroski F-Score for {symbol}: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  8. Full Earnings Analysis — orchestrates all above
    # ------------------------------------------------------------------ #
    def get_full_earnings_analysis(self, symbol: str) -> dict:
        """
        Run all earnings and fundamental analyses for a symbol.
        Returns a comprehensive dict with all metrics.
        """
        symbol = symbol.upper()

        earnings_history = self.get_earnings_history(symbol)
        margin_analysis = self.compute_margin_analysis(symbol)
        eps_growth = self.compute_eps_growth(symbol)
        peg_ratio = self.compute_peg_ratio(symbol)
        accrual_ratio = self.compute_accrual_ratio(symbol)
        altman_z = self.compute_altman_z_score(symbol)
        piotroski = self.compute_piotroski_f_score(symbol)

        # Compute a summary earnings score for use in composite signal
        earnings_score_inputs = {}
        if earnings_history and len(earnings_history) > 0:
            latest = earnings_history[0]
            earnings_score_inputs["eps_surprise_pct"] = latest.get("surprise_pct")

        if peg_ratio is not None:
            earnings_score_inputs["peg_ratio"] = peg_ratio

        if piotroski is not None:
            earnings_score_inputs["piotroski_f_score"] = piotroski["f_score"]

        if altman_z is not None:
            earnings_score_inputs["altman_z_score"] = altman_z["z_score"]

        if margin_analysis is not None:
            earnings_score_inputs["margin_trend"] = margin_analysis.get("trend", "stable")

        if accrual_ratio is not None:
            earnings_score_inputs["accrual_ratio"] = accrual_ratio

        # Compute earnings_growth from earnings_history
        earnings_growth = None
        if earnings_history and len(earnings_history) >= 2:
            growth_entries = []
            for i in range(len(earnings_history) - 1):
                current_eps = earnings_history[i].get("actual")
                prev_eps = earnings_history[i + 1].get("actual")
                if current_eps is not None and prev_eps is not None and prev_eps != 0:
                    growth_pct = round(((current_eps - prev_eps) / abs(prev_eps)) * 100, 2)
                    growth_entries.append({
                        "quarter": earnings_history[i].get("quarter"),
                        "eps": current_eps,
                        "prev_eps": prev_eps,
                        "growth_pct": growth_pct,
                    })
            if growth_entries:
                avg_growth = round(
                    sum(e["growth_pct"] for e in growth_entries) / len(growth_entries), 2
                )
                earnings_growth = {
                    "quarterly_growth": growth_entries,
                    "average_growth_pct": avg_growth,
                    "periods_analyzed": len(growth_entries),
                }

        return {
            "symbol": symbol,
            "earnings_history": earnings_history,
            "margin_analysis": margin_analysis,
            "eps_growth": eps_growth,
            "earnings_growth": earnings_growth,
            "peg_ratio": peg_ratio,
            "accrual_ratio": accrual_ratio,
            "altman_z_score": altman_z,
            "piotroski_f_score": piotroski,
            "earnings_score_inputs": earnings_score_inputs,
        }
