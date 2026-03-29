from __future__ import annotations

"""
NSESignalEngine - Core Technical Indicator Computation Engine
=============================================================
Implements 50 technical indicators from scratch using numpy/pandas.
No ta-lib dependency. All formulas are mathematically precise.

Author: NSESignalEngine
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union


class IndicatorEngine:
    """
    Core engine for computing 50 technical indicators on OHLCV data.

    Expects a DataFrame with columns: Open, High, Low, Close, Volume
    (and optionally 'Adj Close'). All methods return pandas Series or DataFrames.
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._validate()
        self.open = self.df["Open"].astype(float)
        self.high = self.df["High"].astype(float)
        self.low = self.df["Low"].astype(float)
        self.close = self.df["Close"].astype(float)
        self.volume = self.df["Volume"].astype(float)

    def _validate(self):
        required = {"Open", "High", "Low", "Close", "Volume"}
        missing = required - set(self.df.columns)
        if missing:
            raise ValueError(f"DataFrame missing required columns: {missing}")
        if len(self.df) < 2:
            raise ValueError("DataFrame must have at least 2 rows")

    # =========================================================================
    # HELPER FUNCTIONS
    # =========================================================================

    @staticmethod
    def _wilder_smooth(series: pd.Series, period: int) -> pd.Series:
        """Wilder's smoothing method (equivalent to EMA with alpha=1/period)."""
        result = pd.Series(np.nan, index=series.index, dtype=float)
        # First value is the SMA of the first 'period' values
        first_valid = series.first_valid_index()
        if first_valid is None:
            return result
        start_loc = series.index.get_loc(first_valid)
        if start_loc + period > len(series):
            return result
        result.iloc[start_loc + period - 1] = series.iloc[start_loc:start_loc + period].mean()
        for i in range(start_loc + period, len(series)):
            result.iloc[i] = (result.iloc[i - 1] * (period - 1) + series.iloc[i]) / period
        return result

    @staticmethod
    def _ema(series: pd.Series, period: int) -> pd.Series:
        """Exponential Moving Average: EMA_t = Price * k + EMA_(t-1) * (1-k), k=2/(n+1)."""
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def _sma(series: pd.Series, period: int) -> pd.Series:
        """Simple Moving Average."""
        return series.rolling(window=period, min_periods=period).mean()

    @staticmethod
    def _wma(series: pd.Series, period: int) -> pd.Series:
        """Weighted Moving Average: WMA = sum(P_i * w_i) / sum(w_i), weights = n, n-1, ..., 1."""
        weights = np.arange(1, period + 1, dtype=float)
        denom = weights.sum()  # n*(n+1)/2

        def _calc(window):
            return np.dot(window, weights) / denom

        return series.rolling(window=period, min_periods=period).apply(_calc, raw=True)

    @staticmethod
    def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        """True Range = max(H-L, |H-Cp|, |L-Cp|)."""
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # =========================================================================
    # TREND INDICATORS (1-14)
    # =========================================================================

    # 1. SMA
    def sma(self, period: int = 20) -> pd.Series:
        """Simple Moving Average for a given period."""
        return self._sma(self.close, period)

    def sma_all(self) -> pd.DataFrame:
        """SMA for periods 5, 10, 20, 50, 100, 200."""
        result = pd.DataFrame(index=self.df.index)
        for p in [5, 10, 20, 50, 100, 200]:
            result[f"SMA_{p}"] = self._sma(self.close, p)
        return result

    # 2. EMA
    def ema(self, period: int = 20) -> pd.Series:
        """Exponential Moving Average: EMA_t = Price * k + EMA_(t-1) * (1-k), k=2/(n+1)."""
        return self._ema(self.close, period)

    def ema_all(self) -> pd.DataFrame:
        """EMA for periods 9, 12, 21, 26, 50, 200."""
        result = pd.DataFrame(index=self.df.index)
        for p in [9, 12, 21, 26, 50, 200]:
            result[f"EMA_{p}"] = self._ema(self.close, p)
        return result

    # 3. WMA
    def wma(self, period: int = 20) -> pd.Series:
        """Weighted Moving Average: WMA = (P1*n + P2*(n-1) + ... + Pn*1) / (n*(n+1)/2)."""
        return self._wma(self.close, period)

    def wma_all(self) -> pd.DataFrame:
        """WMA for periods 10, 20, 50."""
        result = pd.DataFrame(index=self.df.index)
        for p in [10, 20, 50]:
            result[f"WMA_{p}"] = self._wma(self.close, p)
        return result

    # 4. Hull Moving Average (HMA)
    def hma(self, period: int = 20) -> pd.Series:
        """Hull Moving Average: HMA(n) = WMA(sqrt(n)) of (2*WMA(n/2) - WMA(n))."""
        half_period = max(int(period / 2), 1)
        sqrt_period = max(int(np.sqrt(period)), 1)
        wma_half = self._wma(self.close, half_period)
        wma_full = self._wma(self.close, period)
        diff = 2 * wma_half - wma_full
        return self._wma(diff, sqrt_period)

    # 5. DEMA
    def dema(self, period: int = 20) -> pd.Series:
        """Double EMA: DEMA = 2*EMA(n) - EMA(EMA(n))."""
        ema1 = self._ema(self.close, period)
        ema2 = self._ema(ema1, period)
        return 2 * ema1 - ema2

    # 6. TEMA
    def tema(self, period: int = 20) -> pd.Series:
        """Triple EMA: TEMA = 3*EMA - 3*EMA(EMA) + EMA(EMA(EMA))."""
        ema1 = self._ema(self.close, period)
        ema2 = self._ema(ema1, period)
        ema3 = self._ema(ema2, period)
        return 3 * ema1 - 3 * ema2 + ema3

    # 7. KAMA
    def kama(self, period: int = 10, fast_sc: float = 2.0 / 3.0, slow_sc: float = 2.0 / 31.0) -> pd.Series:
        """
        Kaufman Adaptive Moving Average.
        ER = |Change| / Volatility
        SC = (ER * (fast_SC - slow_SC) + slow_SC)^2
        KAMA_t = KAMA_(t-1) + SC * (Price - KAMA_(t-1))
        """
        close = self.close.values.astype(float)
        n = len(close)
        result = np.full(n, np.nan)

        if n <= period:
            return pd.Series(result, index=self.df.index)

        # Direction = |Close - Close[period ago]|
        direction = np.abs(close[period:] - close[:-period])
        # Volatility = sum of |Close_i - Close_(i-1)| over period
        abs_diff = np.abs(np.diff(close))
        volatility = np.convolve(abs_diff, np.ones(period), mode="valid")

        # Efficiency Ratio
        er = np.where(volatility != 0, direction / volatility, 0.0)

        # Smoothing constant
        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2

        # Initialize KAMA with SMA of first 'period' values
        result[period - 1] = np.mean(close[:period])

        for i in range(period, n):
            sc_i = sc[i - period]
            result[i] = result[i - 1] + sc_i * (close[i] - result[i - 1])

        return pd.Series(result, index=self.df.index, name="KAMA")

    # 8. MACD
    def macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """
        MACD Line = EMA(12) - EMA(26)
        Signal Line = EMA(9) of MACD
        Histogram = MACD - Signal
        """
        ema_fast = self._ema(self.close, fast)
        ema_slow = self._ema(self.close, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self._ema(macd_line, signal)
        histogram = macd_line - signal_line
        return pd.DataFrame({
            "MACD": macd_line,
            "MACD_Signal": signal_line,
            "MACD_Histogram": histogram,
        }, index=self.df.index)

    # 9. Parabolic SAR
    def parabolic_sar(self, af_start: float = 0.02, af_step: float = 0.02,
                      af_max: float = 0.20) -> pd.DataFrame:
        """
        Parabolic SAR with acceleration factor starting at 0.02,
        step 0.02, max 0.20.
        """
        high = self.high.values.astype(float)
        low = self.low.values.astype(float)
        close = self.close.values.astype(float)
        n = len(close)

        sar = np.full(n, np.nan)
        trend = np.zeros(n, dtype=int)  # 1 = up, -1 = down
        af = np.full(n, af_start)
        ep = np.full(n, np.nan)  # extreme point

        # Initialise: determine initial trend from first two bars
        if high[1] > high[0]:
            trend[0] = 1
            sar[0] = low[0]
            ep[0] = high[0]
        else:
            trend[0] = -1
            sar[0] = high[0]
            ep[0] = low[0]

        for i in range(1, n):
            # Carry forward
            prev_sar = sar[i - 1]
            prev_af = af[i - 1]
            prev_ep = ep[i - 1]
            prev_trend = trend[i - 1]

            # Calculate new SAR
            new_sar = prev_sar + prev_af * (prev_ep - prev_sar)

            # Clamp SAR
            if prev_trend == 1:
                new_sar = min(new_sar, low[i - 1])
                if i >= 2:
                    new_sar = min(new_sar, low[i - 2])
            else:
                new_sar = max(new_sar, high[i - 1])
                if i >= 2:
                    new_sar = max(new_sar, high[i - 2])

            # Check for reversal
            if prev_trend == 1:
                if low[i] < new_sar:
                    # Reverse to downtrend
                    trend[i] = -1
                    new_sar = prev_ep
                    ep[i] = low[i]
                    af[i] = af_start
                else:
                    trend[i] = 1
                    if high[i] > prev_ep:
                        ep[i] = high[i]
                        af[i] = min(prev_af + af_step, af_max)
                    else:
                        ep[i] = prev_ep
                        af[i] = prev_af
            else:
                if high[i] > new_sar:
                    # Reverse to uptrend
                    trend[i] = 1
                    new_sar = prev_ep
                    ep[i] = high[i]
                    af[i] = af_start
                else:
                    trend[i] = -1
                    if low[i] < prev_ep:
                        ep[i] = low[i]
                        af[i] = min(prev_af + af_step, af_max)
                    else:
                        ep[i] = prev_ep
                        af[i] = prev_af

            sar[i] = new_sar

        return pd.DataFrame({
            "PSAR": sar,
            "PSAR_Trend": trend,
        }, index=self.df.index)

    # 10. Ichimoku Cloud
    def ichimoku(self, tenkan: int = 9, kijun: int = 26, senkou_b: int = 52) -> pd.DataFrame:
        """
        Ichimoku Cloud:
        - Tenkan-sen = (highest high + lowest low) / 2 over 9 periods
        - Kijun-sen = (highest high + lowest low) / 2 over 26 periods
        - Senkou Span A = (Tenkan + Kijun) / 2, shifted 26 periods ahead
        - Senkou Span B = (highest high + lowest low) / 2 over 52 periods, shifted 26 ahead
        - Chikou Span = Close shifted 26 periods back
        """
        tenkan_sen = (self.high.rolling(tenkan).max() + self.low.rolling(tenkan).min()) / 2
        kijun_sen = (self.high.rolling(kijun).max() + self.low.rolling(kijun).min()) / 2
        senkou_a = ((tenkan_sen + kijun_sen) / 2).shift(kijun)
        senkou_b_line = ((self.high.rolling(senkou_b).max() + self.low.rolling(senkou_b).min()) / 2).shift(kijun)
        chikou = self.close.shift(-kijun)

        return pd.DataFrame({
            "Ichimoku_Tenkan": tenkan_sen,
            "Ichimoku_Kijun": kijun_sen,
            "Ichimoku_SenkouA": senkou_a,
            "Ichimoku_SenkouB": senkou_b_line,
            "Ichimoku_Chikou": chikou,
        }, index=self.df.index)

    # 11. Supertrend
    def supertrend(self, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
        """
        Supertrend indicator.
        Basic Upper Band = (High + Low) / 2 + multiplier * ATR
        Basic Lower Band = (High + Low) / 2 - multiplier * ATR
        """
        hl2 = (self.high + self.low) / 2
        atr = self._wilder_smooth(self._true_range(self.high, self.low, self.close), period)

        upper_basic = hl2 + multiplier * atr
        lower_basic = hl2 - multiplier * atr

        upper = upper_basic.copy()
        lower = lower_basic.copy()
        supertrend = pd.Series(np.nan, index=self.df.index, dtype=float)
        direction = pd.Series(1, index=self.df.index, dtype=int)  # 1=up, -1=down

        close = self.close.values
        upper_vals = upper.values.astype(float)
        lower_vals = lower.values.astype(float)
        upper_basic_vals = upper_basic.values.astype(float)
        lower_basic_vals = lower_basic.values.astype(float)
        st_vals = np.full(len(close), np.nan)
        dir_vals = np.ones(len(close), dtype=int)

        for i in range(1, len(close)):
            # Final upper band
            if upper_basic_vals[i] < upper_vals[i - 1] or close[i - 1] > upper_vals[i - 1]:
                upper_vals[i] = upper_basic_vals[i]
            else:
                upper_vals[i] = upper_vals[i - 1]

            # Final lower band
            if lower_basic_vals[i] > lower_vals[i - 1] or close[i - 1] < lower_vals[i - 1]:
                lower_vals[i] = lower_basic_vals[i]
            else:
                lower_vals[i] = lower_vals[i - 1]

            # Direction and Supertrend value
            if np.isnan(atr.iloc[i]):
                st_vals[i] = np.nan
                dir_vals[i] = 1
                continue

            if dir_vals[i - 1] == 1:  # Previous was uptrend
                if close[i] < lower_vals[i]:
                    dir_vals[i] = -1
                    st_vals[i] = upper_vals[i]
                else:
                    dir_vals[i] = 1
                    st_vals[i] = lower_vals[i]
            else:  # Previous was downtrend
                if close[i] > upper_vals[i]:
                    dir_vals[i] = 1
                    st_vals[i] = lower_vals[i]
                else:
                    dir_vals[i] = -1
                    st_vals[i] = upper_vals[i]

        return pd.DataFrame({
            "Supertrend": pd.Series(st_vals, index=self.df.index),
            "Supertrend_Direction": pd.Series(dir_vals, index=self.df.index),
            "Supertrend_Upper": pd.Series(upper_vals, index=self.df.index),
            "Supertrend_Lower": pd.Series(lower_vals, index=self.df.index),
        })

    # 12. ADX with +DI/-DI
    def adx(self, period: int = 14) -> pd.DataFrame:
        """
        Average Directional Index with +DI and -DI.
        Uses Wilder's smoothing throughout.
        """
        high = self.high
        low = self.low
        close = self.close

        # +DM and -DM
        up_move = high.diff()
        down_move = -low.diff()

        plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
                            index=self.df.index, dtype=float)
        minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
                             index=self.df.index, dtype=float)

        tr = self._true_range(high, low, close)

        # Wilder's smoothing
        atr = self._wilder_smooth(tr, period)
        plus_dm_smooth = self._wilder_smooth(plus_dm, period)
        minus_dm_smooth = self._wilder_smooth(minus_dm, period)

        plus_di = 100 * plus_dm_smooth / atr
        minus_di = 100 * minus_dm_smooth / atr

        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        adx_val = self._wilder_smooth(dx, period)

        return pd.DataFrame({
            "ADX": adx_val,
            "Plus_DI": plus_di,
            "Minus_DI": minus_di,
        }, index=self.df.index)

    # 13. Aroon
    def aroon(self, period: int = 25) -> pd.DataFrame:
        """
        Aroon Up = ((period - periods since highest high) / period) * 100
        Aroon Down = ((period - periods since lowest low) / period) * 100
        Aroon Oscillator = Aroon Up - Aroon Down
        """
        aroon_up = pd.Series(np.nan, index=self.df.index, dtype=float)
        aroon_down = pd.Series(np.nan, index=self.df.index, dtype=float)

        high_vals = self.high.values
        low_vals = self.low.values

        for i in range(period, len(self.df)):
            window_high = high_vals[i - period: i + 1]
            window_low = low_vals[i - period: i + 1]
            days_since_high = period - np.argmax(window_high)
            days_since_low = period - np.argmin(window_low)
            aroon_up.iloc[i] = ((period - days_since_high) / period) * 100
            aroon_down.iloc[i] = ((period - days_since_low) / period) * 100

        return pd.DataFrame({
            "Aroon_Up": aroon_up,
            "Aroon_Down": aroon_down,
            "Aroon_Oscillator": aroon_up - aroon_down,
        }, index=self.df.index)

    # 14. Vortex Indicator
    def vortex(self, period: int = 14) -> pd.DataFrame:
        """
        Vortex Indicator:
        VM+ = |High_t - Low_(t-1)|
        VM- = |Low_t - High_(t-1)|
        VI+ = sum(VM+, period) / sum(TR, period)
        VI- = sum(VM-, period) / sum(TR, period)
        """
        vm_plus = (self.high - self.low.shift(1)).abs()
        vm_minus = (self.low - self.high.shift(1)).abs()
        tr = self._true_range(self.high, self.low, self.close)

        vm_plus_sum = vm_plus.rolling(period).sum()
        vm_minus_sum = vm_minus.rolling(period).sum()
        tr_sum = tr.rolling(period).sum()

        vi_plus = vm_plus_sum / tr_sum
        vi_minus = vm_minus_sum / tr_sum

        return pd.DataFrame({
            "Vortex_Plus": vi_plus,
            "Vortex_Minus": vi_minus,
        }, index=self.df.index)

    # =========================================================================
    # MOMENTUM INDICATORS (15-25)
    # =========================================================================

    # 15. RSI
    def rsi(self, period: int = 14) -> pd.Series:
        """
        RSI using Wilder's smoothing.
        RS = Wilder_Avg(gains) / Wilder_Avg(losses)
        RSI = 100 - 100/(1+RS)
        """
        delta = self.close.diff()
        gains = delta.clip(lower=0)
        losses = (-delta).clip(lower=0)

        avg_gain = self._wilder_smooth(gains, period)
        avg_loss = self._wilder_smooth(losses, period)

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi_val = 100 - (100 / (1 + rs))
        rsi_val.name = "RSI"
        return rsi_val

    # 16. Stochastic %K/%D
    def stochastic(self, k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
        """
        Stochastic Oscillator:
        %K = (Close - Lowest Low) / (Highest High - Lowest Low) * 100
        %D = SMA(3) of %K
        """
        lowest_low = self.low.rolling(k_period).min()
        highest_high = self.high.rolling(k_period).max()
        denom = (highest_high - lowest_low).replace(0, np.nan)
        stoch_k = 100 * (self.close - lowest_low) / denom
        stoch_d = self._sma(stoch_k, d_period)

        return pd.DataFrame({
            "Stoch_K": stoch_k,
            "Stoch_D": stoch_d,
        }, index=self.df.index)

    # 17. Stochastic RSI
    def stochastic_rsi(self, rsi_period: int = 14, stoch_period: int = 14,
                       k_smooth: int = 3, d_smooth: int = 3) -> pd.DataFrame:
        """
        Stochastic RSI = (RSI - min(RSI, n)) / (max(RSI, n) - min(RSI, n))
        %K = SMA(k_smooth) of StochRSI
        %D = SMA(d_smooth) of %K
        """
        rsi_val = self.rsi(rsi_period)
        rsi_min = rsi_val.rolling(stoch_period).min()
        rsi_max = rsi_val.rolling(stoch_period).max()
        denom = (rsi_max - rsi_min).replace(0, np.nan)
        stoch_rsi = (rsi_val - rsi_min) / denom

        k = self._sma(stoch_rsi, k_smooth)
        d = self._sma(k, d_smooth)

        return pd.DataFrame({
            "StochRSI": stoch_rsi,
            "StochRSI_K": k,
            "StochRSI_D": d,
        }, index=self.df.index)

    # 18. Williams %R
    def williams_r(self, period: int = 14) -> pd.Series:
        """Williams %R = (Highest High - Close) / (Highest High - Lowest Low) * -100."""
        highest_high = self.high.rolling(period).max()
        lowest_low = self.low.rolling(period).min()
        denom = (highest_high - lowest_low).replace(0, np.nan)
        wr = -100 * (highest_high - self.close) / denom
        wr.name = "Williams_R"
        return wr

    # 19. CCI
    def cci(self, period: int = 20, constant: float = 0.015) -> pd.Series:
        """
        CCI = (Typical Price - SMA(TP)) / (constant * Mean Deviation)
        Typical Price = (H + L + C) / 3
        """
        tp = (self.high + self.low + self.close) / 3
        sma_tp = self._sma(tp, period)
        mean_dev = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
        cci_val = (tp - sma_tp) / (constant * mean_dev)
        cci_val.name = "CCI"
        return cci_val

    # 20. ROC
    def roc(self, period: int = 12) -> pd.Series:
        """Rate of Change = ((Close - Close_n) / Close_n) * 100."""
        roc_val = ((self.close - self.close.shift(period)) / self.close.shift(period)) * 100
        roc_val.name = "ROC"
        return roc_val

    # 21. Momentum
    def momentum(self, period: int = 10) -> pd.Series:
        """Momentum = Close - Close_n."""
        mom = self.close - self.close.shift(period)
        mom.name = "Momentum"
        return mom

    # 22. TSI
    def tsi(self, long_period: int = 25, short_period: int = 13,
            signal_period: int = 7) -> pd.DataFrame:
        """
        True Strength Index:
        Double smoothed momentum / Double smoothed absolute momentum * 100
        Signal = EMA(signal_period) of TSI
        """
        delta = self.close.diff()
        # Double smooth the momentum
        smooth1 = self._ema(delta, long_period)
        smooth2 = self._ema(smooth1, short_period)
        # Double smooth the absolute momentum
        abs_smooth1 = self._ema(delta.abs(), long_period)
        abs_smooth2 = self._ema(abs_smooth1, short_period)

        tsi_val = 100 * smooth2 / abs_smooth2.replace(0, np.nan)
        tsi_signal = self._ema(tsi_val, signal_period)

        return pd.DataFrame({
            "TSI": tsi_val,
            "TSI_Signal": tsi_signal,
        }, index=self.df.index)

    # 23. Ultimate Oscillator
    def ultimate_oscillator(self, p1: int = 7, p2: int = 14, p3: int = 28) -> pd.Series:
        """
        Ultimate Oscillator:
        BP = Close - min(Low, Previous Close)
        TR = max(High, Previous Close) - min(Low, Previous Close)
        UO = 100 * (4*Avg7 + 2*Avg14 + Avg28) / 7
        """
        prev_close = self.close.shift(1)
        bp = self.close - pd.concat([self.low, prev_close], axis=1).min(axis=1)
        tr = pd.concat([self.high, prev_close], axis=1).max(axis=1) - \
             pd.concat([self.low, prev_close], axis=1).min(axis=1)

        avg1 = bp.rolling(p1).sum() / tr.rolling(p1).sum()
        avg2 = bp.rolling(p2).sum() / tr.rolling(p2).sum()
        avg3 = bp.rolling(p3).sum() / tr.rolling(p3).sum()

        uo = 100 * (4 * avg1 + 2 * avg2 + avg3) / 7
        uo.name = "Ultimate_Oscillator"
        return uo

    # 24. Awesome Oscillator
    def awesome_oscillator(self) -> pd.Series:
        """Awesome Oscillator = SMA(5) of midpoint - SMA(34) of midpoint."""
        midpoint = (self.high + self.low) / 2
        ao = self._sma(midpoint, 5) - self._sma(midpoint, 34)
        ao.name = "Awesome_Oscillator"
        return ao

    # 25. PPO
    def ppo(self, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """
        Percentage Price Oscillator:
        PPO = (EMA(12) - EMA(26)) / EMA(26) * 100
        Signal = EMA(9) of PPO
        Histogram = PPO - Signal
        """
        ema_fast = self._ema(self.close, fast)
        ema_slow = self._ema(self.close, slow)
        ppo_line = (ema_fast - ema_slow) / ema_slow * 100
        ppo_signal = self._ema(ppo_line, signal)
        ppo_hist = ppo_line - ppo_signal

        return pd.DataFrame({
            "PPO": ppo_line,
            "PPO_Signal": ppo_signal,
            "PPO_Histogram": ppo_hist,
        }, index=self.df.index)

    # =========================================================================
    # VOLATILITY INDICATORS (26-32)
    # =========================================================================

    # 26. Bollinger Bands
    def bollinger_bands(self, period: int = 20, num_std: float = 2.0) -> pd.DataFrame:
        """
        Bollinger Bands:
        Middle = SMA(20)
        Upper = Middle + 2*StdDev(20)
        Lower = Middle - 2*StdDev(20)
        %B = (Price - Lower) / (Upper - Lower)
        Bandwidth = (Upper - Lower) / Middle * 100
        """
        middle = self._sma(self.close, period)
        std = self.close.rolling(period).std(ddof=0)
        upper = middle + num_std * std
        lower = middle - num_std * std
        bandwidth = (upper - lower) / middle * 100
        pct_b = (self.close - lower) / (upper - lower).replace(0, np.nan)

        return pd.DataFrame({
            "BB_Upper": upper,
            "BB_Middle": middle,
            "BB_Lower": lower,
            "BB_PctB": pct_b,
            "BB_Bandwidth": bandwidth,
        }, index=self.df.index)

    # 27. ATR
    def atr(self, period: int = 14) -> pd.Series:
        """Average True Range using Wilder's smoothing."""
        tr = self._true_range(self.high, self.low, self.close)
        atr_val = self._wilder_smooth(tr, period)
        atr_val.name = "ATR"
        return atr_val

    # 28. Keltner Channels
    def keltner_channels(self, ema_period: int = 20, atr_period: int = 10,
                         multiplier: float = 2.0) -> pd.DataFrame:
        """
        Keltner Channels:
        Middle = EMA(20)
        Upper = EMA(20) + 2 * ATR(10)
        Lower = EMA(20) - 2 * ATR(10)
        """
        middle = self._ema(self.close, ema_period)
        atr_val = self.atr(atr_period)
        upper = middle + multiplier * atr_val
        lower = middle - multiplier * atr_val

        return pd.DataFrame({
            "Keltner_Upper": upper,
            "Keltner_Middle": middle,
            "Keltner_Lower": lower,
        }, index=self.df.index)

    # 29. Donchian Channels
    def donchian_channels(self, period: int = 20) -> pd.DataFrame:
        """
        Donchian Channels:
        Upper = Highest High over period
        Lower = Lowest Low over period
        Middle = (Upper + Lower) / 2
        """
        upper = self.high.rolling(period).max()
        lower = self.low.rolling(period).min()
        middle = (upper + lower) / 2

        return pd.DataFrame({
            "Donchian_Upper": upper,
            "Donchian_Middle": middle,
            "Donchian_Lower": lower,
        }, index=self.df.index)

    # 30. Historical Volatility
    def historical_volatility(self) -> pd.DataFrame:
        """
        Historical Volatility = StdDev(ln returns) * sqrt(252)
        Periods: 10, 20, 60, 252.
        """
        log_returns = np.log(self.close / self.close.shift(1))
        result = pd.DataFrame(index=self.df.index)
        for p in [10, 20, 60, 252]:
            result[f"HV_{p}"] = log_returns.rolling(p).std(ddof=1) * np.sqrt(252)
        return result

    # 31. Chaikin Volatility
    def chaikin_volatility(self, ema_period: int = 10, roc_period: int = 10) -> pd.Series:
        """
        Chaikin Volatility:
        1. HL_EMA = EMA(High - Low, period)
        2. CV = (HL_EMA - HL_EMA[roc_period ago]) / HL_EMA[roc_period ago] * 100
        """
        hl = self.high - self.low
        hl_ema = self._ema(hl, ema_period)
        cv = (hl_ema - hl_ema.shift(roc_period)) / hl_ema.shift(roc_period).replace(0, np.nan) * 100
        cv.name = "Chaikin_Volatility"
        return cv

    # 32. Ulcer Index
    def ulcer_index(self, period: int = 14) -> pd.Series:
        """
        Ulcer Index:
        Percentage Drawdown = (Close - Highest Close over period) / Highest Close * 100
        UI = sqrt(mean(PD^2) over period)
        """
        highest = self.close.rolling(period).max()
        pct_drawdown = (self.close - highest) / highest * 100
        sq_avg = (pct_drawdown ** 2).rolling(period).mean()
        ui = np.sqrt(sq_avg)
        ui.name = "Ulcer_Index"
        return ui

    # =========================================================================
    # VOLUME INDICATORS (33-40)
    # =========================================================================

    # 33. OBV
    def obv(self) -> pd.Series:
        """
        On-Balance Volume:
        If Close > Previous Close: OBV = OBV_prev + Volume
        If Close < Previous Close: OBV = OBV_prev - Volume
        If Close == Previous Close: OBV = OBV_prev
        """
        direction = np.sign(self.close.diff())
        direction.iloc[0] = 0
        obv_val = (direction * self.volume).cumsum()
        obv_val.name = "OBV"
        return obv_val

    # 34. VWAP
    def vwap(self) -> pd.Series:
        """
        Volume Weighted Average Price:
        VWAP = cumulative(Typical Price * Volume) / cumulative(Volume)
        Resets each trading day (uses cumulative from start if intraday not detected).
        """
        tp = (self.high + self.low + self.close) / 3
        cum_tp_vol = (tp * self.volume).cumsum()
        cum_vol = self.volume.cumsum()
        vwap_val = cum_tp_vol / cum_vol.replace(0, np.nan)
        vwap_val.name = "VWAP"
        return vwap_val

    # 35. A/D Line (Accumulation/Distribution)
    def ad_line(self) -> pd.Series:
        """
        A/D Line:
        Money Flow Multiplier = ((Close - Low) - (High - Close)) / (High - Low)
        Money Flow Volume = MFM * Volume
        A/D = cumulative sum of MFV
        """
        hl_diff = (self.high - self.low).replace(0, np.nan)
        mfm = ((self.close - self.low) - (self.high - self.close)) / hl_diff
        mfv = mfm * self.volume
        ad = mfv.cumsum()
        ad.name = "AD_Line"
        return ad

    # 36. CMF (Chaikin Money Flow)
    def cmf(self, period: int = 20) -> pd.Series:
        """
        CMF = Sum(Money Flow Volume, period) / Sum(Volume, period)
        """
        hl_diff = (self.high - self.low).replace(0, np.nan)
        mfm = ((self.close - self.low) - (self.high - self.close)) / hl_diff
        mfv = mfm * self.volume
        cmf_val = mfv.rolling(period).sum() / self.volume.rolling(period).sum()
        cmf_val.name = "CMF"
        return cmf_val

    # 37. MFI (Money Flow Index)
    def mfi(self, period: int = 14) -> pd.Series:
        """
        Money Flow Index (volume-weighted RSI):
        Typical Price = (H+L+C)/3
        Raw Money Flow = TP * Volume
        Positive/Negative MF based on TP direction
        MFR = Positive MF / Negative MF
        MFI = 100 - 100/(1+MFR)
        """
        tp = (self.high + self.low + self.close) / 3
        raw_mf = tp * self.volume
        tp_diff = tp.diff()

        pos_mf = pd.Series(np.where(tp_diff > 0, raw_mf, 0.0), index=self.df.index, dtype=float)
        neg_mf = pd.Series(np.where(tp_diff < 0, raw_mf, 0.0), index=self.df.index, dtype=float)

        pos_sum = pos_mf.rolling(period).sum()
        neg_sum = neg_mf.rolling(period).sum()
        mfr = pos_sum / neg_sum.replace(0, np.nan)
        mfi_val = 100 - (100 / (1 + mfr))
        mfi_val.name = "MFI"
        return mfi_val

    # 38. Force Index
    def force_index(self, period: int = 13) -> pd.Series:
        """Force Index = EMA(period) of (Close - Previous Close) * Volume."""
        fi = (self.close.diff()) * self.volume
        fi_ema = self._ema(fi, period)
        fi_ema.name = "Force_Index"
        return fi_ema

    # 39. Ease of Movement
    def ease_of_movement(self, period: int = 14) -> pd.DataFrame:
        """
        Ease of Movement:
        Distance Moved = ((High + Low)/2 - (Prev High + Prev Low)/2)
        Box Ratio = (Volume / 10^x) / (High - Low)  [scaled]
        EMV = Distance / Box Ratio
        EMV_SMA = SMA(period) of EMV
        """
        distance = ((self.high + self.low) / 2) - ((self.high.shift(1) + self.low.shift(1)) / 2)
        hl_diff = (self.high - self.low).replace(0, np.nan)
        box_ratio = (self.volume / 1e6) / hl_diff  # scale volume
        emv = distance / box_ratio.replace(0, np.nan)
        emv_sma = self._sma(emv, period)

        return pd.DataFrame({
            "EMV": emv,
            "EMV_SMA": emv_sma,
        }, index=self.df.index)

    # 40. Volume ROC
    def volume_roc(self, period: int = 25) -> pd.Series:
        """Volume Rate of Change = (Volume - Volume_n) / Volume_n * 100."""
        vroc = (self.volume - self.volume.shift(period)) / self.volume.shift(period).replace(0, np.nan) * 100
        vroc.name = "Volume_ROC"
        return vroc

    # =========================================================================
    # SUPPORT/RESISTANCE (41-43)
    # =========================================================================

    # 41. Pivot Points
    def pivot_points(self) -> pd.DataFrame:
        """
        Standard, Fibonacci, and Camarilla Pivot Points.
        Uses previous period's H, L, C.
        """
        h = self.high.shift(1)
        l = self.low.shift(1)
        c = self.close.shift(1)
        pp = (h + l + c) / 3

        # Standard
        s1 = 2 * pp - h
        r1 = 2 * pp - l
        s2 = pp - (h - l)
        r2 = pp + (h - l)
        s3 = l - 2 * (h - pp)
        r3 = h + 2 * (pp - l)

        # Fibonacci
        diff = h - l
        fib_s1 = pp - 0.382 * diff
        fib_r1 = pp + 0.382 * diff
        fib_s2 = pp - 0.618 * diff
        fib_r2 = pp + 0.618 * diff
        fib_s3 = pp - 1.000 * diff
        fib_r3 = pp + 1.000 * diff

        # Camarilla
        cam_s1 = c - diff * 1.1 / 12
        cam_r1 = c + diff * 1.1 / 12
        cam_s2 = c - diff * 1.1 / 6
        cam_r2 = c + diff * 1.1 / 6
        cam_s3 = c - diff * 1.1 / 4
        cam_r3 = c + diff * 1.1 / 4
        cam_s4 = c - diff * 1.1 / 2
        cam_r4 = c + diff * 1.1 / 2

        return pd.DataFrame({
            "PP": pp,
            "S1": s1, "R1": r1, "S2": s2, "R2": r2, "S3": s3, "R3": r3,
            "Fib_S1": fib_s1, "Fib_R1": fib_r1, "Fib_S2": fib_s2, "Fib_R2": fib_r2,
            "Fib_S3": fib_s3, "Fib_R3": fib_r3,
            "Cam_S1": cam_s1, "Cam_R1": cam_r1, "Cam_S2": cam_s2, "Cam_R2": cam_r2,
            "Cam_S3": cam_s3, "Cam_R3": cam_r3, "Cam_S4": cam_s4, "Cam_R4": cam_r4,
        }, index=self.df.index)

    # 42. Fibonacci Retracement
    def fibonacci_retracement(self, zigzag_pct: float = 5.0) -> pd.DataFrame:
        """
        Auto-detect swing highs/lows using a zigzag with the given percentage threshold,
        then compute Fibonacci retracement levels from the last major swing.
        Levels: 0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%
        """
        close = self.close.values.astype(float)
        n = len(close)
        threshold = zigzag_pct / 100.0

        # Find zigzag pivots
        pivots = []  # list of (index, price, type) where type = 'H' or 'L'

        if n < 3:
            return pd.DataFrame(index=self.df.index)

        # Start with first point
        current_dir = 0  # 0=unknown, 1=up, -1=down
        last_pivot_idx = 0
        last_pivot_val = close[0]

        for i in range(1, n):
            change = (close[i] - last_pivot_val) / last_pivot_val if last_pivot_val != 0 else 0

            if current_dir == 0:
                if change >= threshold:
                    pivots.append((last_pivot_idx, last_pivot_val, "L"))
                    current_dir = 1
                    last_pivot_idx = i
                    last_pivot_val = close[i]
                elif change <= -threshold:
                    pivots.append((last_pivot_idx, last_pivot_val, "H"))
                    current_dir = -1
                    last_pivot_idx = i
                    last_pivot_val = close[i]
            elif current_dir == 1:
                if close[i] > last_pivot_val:
                    last_pivot_idx = i
                    last_pivot_val = close[i]
                elif (last_pivot_val - close[i]) / last_pivot_val >= threshold:
                    pivots.append((last_pivot_idx, last_pivot_val, "H"))
                    current_dir = -1
                    last_pivot_idx = i
                    last_pivot_val = close[i]
            elif current_dir == -1:
                if close[i] < last_pivot_val:
                    last_pivot_idx = i
                    last_pivot_val = close[i]
                elif (close[i] - last_pivot_val) / last_pivot_val >= threshold:
                    pivots.append((last_pivot_idx, last_pivot_val, "L"))
                    current_dir = 1
                    last_pivot_idx = i
                    last_pivot_val = close[i]

        # Add last pivot
        if current_dir == 1:
            pivots.append((last_pivot_idx, last_pivot_val, "H"))
        elif current_dir == -1:
            pivots.append((last_pivot_idx, last_pivot_val, "L"))

        # Compute Fib levels from the last two major pivots
        fib_levels = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
        result = pd.DataFrame(index=self.df.index)

        if len(pivots) >= 2:
            swing_start = pivots[-2]
            swing_end = pivots[-1]
            high_val = max(swing_start[1], swing_end[1])
            low_val = min(swing_start[1], swing_end[1])
            diff = high_val - low_val

            # If the last swing was downward (H -> L), retracement goes up
            # If the last swing was upward (L -> H), retracement goes down
            if swing_end[2] == "L":  # downswing, retracement from low
                for level in fib_levels:
                    pct_str = f"{level*100:.1f}".replace(".", "_")
                    result[f"Fib_{pct_str}"] = low_val + diff * level
            else:  # upswing, retracement from high
                for level in fib_levels:
                    pct_str = f"{level*100:.1f}".replace(".", "_")
                    result[f"Fib_{pct_str}"] = high_val - diff * level

            result["Fib_Swing_High"] = high_val
            result["Fib_Swing_Low"] = low_val
            result["Fib_Swing_Direction"] = "down" if swing_end[2] == "L" else "up"

        return result

    # 43. Candlestick Patterns
    def candlestick_patterns(self) -> pd.DataFrame:
        """
        Detects: Doji, Hammer, Inverted Hammer, Bullish Engulfing, Bearish Engulfing,
        Morning Star, Evening Star, Three White Soldiers, Three Black Crows,
        Spinning Top, Marubozu, Harami (Bullish & Bearish).

        Returns DataFrame of booleans, one column per pattern.
        """
        o = self.open.values.astype(float)
        h = self.high.values.astype(float)
        l = self.low.values.astype(float)
        c = self.close.values.astype(float)
        n = len(c)

        body = c - o
        abs_body = np.abs(body)
        candle_range = h - l
        upper_shadow = h - np.maximum(o, c)
        lower_shadow = np.minimum(o, c) - l

        # Avoid division by zero
        safe_range = np.where(candle_range == 0, np.nan, candle_range)
        body_pct = abs_body / safe_range

        # Doji: body < 5% of range
        doji = abs_body < 0.05 * candle_range

        # Hammer: small body at top, lower shadow >= 2x body, small upper shadow
        hammer = np.zeros(n, dtype=bool)
        for i in range(n):
            if candle_range[i] == 0:
                continue
            hammer[i] = (lower_shadow[i] >= 2 * abs_body[i] and
                         upper_shadow[i] <= abs_body[i] * 0.5 and
                         abs_body[i] > 0)

        # Inverted Hammer: small body at bottom, upper shadow >= 2x body
        inv_hammer = np.zeros(n, dtype=bool)
        for i in range(n):
            if candle_range[i] == 0:
                continue
            inv_hammer[i] = (upper_shadow[i] >= 2 * abs_body[i] and
                             lower_shadow[i] <= abs_body[i] * 0.5 and
                             abs_body[i] > 0)

        # Bullish Engulfing: previous bearish, current bullish body engulfs previous
        bull_engulf = np.zeros(n, dtype=bool)
        for i in range(1, n):
            bull_engulf[i] = (body[i - 1] < 0 and body[i] > 0 and
                              o[i] <= c[i - 1] and c[i] >= o[i - 1])

        # Bearish Engulfing
        bear_engulf = np.zeros(n, dtype=bool)
        for i in range(1, n):
            bear_engulf[i] = (body[i - 1] > 0 and body[i] < 0 and
                              o[i] >= c[i - 1] and c[i] <= o[i - 1])

        # Morning Star (3-candle bullish reversal)
        morning_star = np.zeros(n, dtype=bool)
        for i in range(2, n):
            first_bearish = body[i - 2] < 0 and abs_body[i - 2] > 0.5 * candle_range[i - 2]
            second_small = abs_body[i - 1] < 0.3 * candle_range[i - 1] if candle_range[i - 1] > 0 else False
            second_gap = max(o[i - 1], c[i - 1]) < c[i - 2]  # gaps down
            third_bullish = body[i] > 0 and c[i] > (o[i - 2] + c[i - 2]) / 2
            morning_star[i] = first_bearish and second_small and third_bullish

        # Evening Star (3-candle bearish reversal)
        evening_star = np.zeros(n, dtype=bool)
        for i in range(2, n):
            first_bullish = body[i - 2] > 0 and abs_body[i - 2] > 0.5 * candle_range[i - 2]
            second_small = abs_body[i - 1] < 0.3 * candle_range[i - 1] if candle_range[i - 1] > 0 else False
            second_gap = min(o[i - 1], c[i - 1]) > c[i - 2]  # gaps up
            third_bearish = body[i] < 0 and c[i] < (o[i - 2] + c[i - 2]) / 2
            evening_star[i] = first_bullish and second_small and third_bearish

        # Three White Soldiers
        three_white = np.zeros(n, dtype=bool)
        for i in range(2, n):
            all_bullish = body[i] > 0 and body[i - 1] > 0 and body[i - 2] > 0
            ascending = c[i] > c[i - 1] > c[i - 2]
            opens_within = (o[i - 1] > o[i - 2] and o[i - 1] < c[i - 2] and
                            o[i] > o[i - 1] and o[i] < c[i - 1])
            strong_bodies = (abs_body[i] > 0.5 * candle_range[i] if candle_range[i] > 0 else False) and \
                            (abs_body[i - 1] > 0.5 * candle_range[i - 1] if candle_range[i - 1] > 0 else False) and \
                            (abs_body[i - 2] > 0.5 * candle_range[i - 2] if candle_range[i - 2] > 0 else False)
            three_white[i] = all_bullish and ascending and opens_within and strong_bodies

        # Three Black Crows
        three_black = np.zeros(n, dtype=bool)
        for i in range(2, n):
            all_bearish = body[i] < 0 and body[i - 1] < 0 and body[i - 2] < 0
            descending = c[i] < c[i - 1] < c[i - 2]
            opens_within = (o[i - 1] < o[i - 2] and o[i - 1] > c[i - 2] and
                            o[i] < o[i - 1] and o[i] > c[i - 1])
            strong_bodies = (abs_body[i] > 0.5 * candle_range[i] if candle_range[i] > 0 else False) and \
                            (abs_body[i - 1] > 0.5 * candle_range[i - 1] if candle_range[i - 1] > 0 else False) and \
                            (abs_body[i - 2] > 0.5 * candle_range[i - 2] if candle_range[i - 2] > 0 else False)
            three_black[i] = all_bearish and descending and opens_within and strong_bodies

        # Spinning Top: small body, both shadows longer than body
        spinning_top = np.zeros(n, dtype=bool)
        for i in range(n):
            if candle_range[i] == 0 or abs_body[i] == 0:
                continue
            spinning_top[i] = (abs_body[i] < 0.3 * candle_range[i] and
                               upper_shadow[i] > abs_body[i] and
                               lower_shadow[i] > abs_body[i])

        # Marubozu: body is nearly the entire candle (> 95% of range)
        marubozu_bull = np.zeros(n, dtype=bool)
        marubozu_bear = np.zeros(n, dtype=bool)
        for i in range(n):
            if candle_range[i] == 0:
                continue
            if abs_body[i] >= 0.95 * candle_range[i]:
                if body[i] > 0:
                    marubozu_bull[i] = True
                else:
                    marubozu_bear[i] = True

        # Harami (Bullish): previous bearish, current body inside previous body
        harami_bull = np.zeros(n, dtype=bool)
        harami_bear = np.zeros(n, dtype=bool)
        for i in range(1, n):
            if body[i - 1] < 0 and body[i] > 0:
                # Bullish harami: current body inside previous body
                if o[i] >= c[i - 1] and c[i] <= o[i - 1]:
                    harami_bull[i] = True
            if body[i - 1] > 0 and body[i] < 0:
                # Bearish harami: current body inside previous body
                if o[i] <= c[i - 1] and c[i] >= o[i - 1]:
                    harami_bear[i] = True

        idx = self.df.index
        return pd.DataFrame({
            "Doji": pd.Series(doji, index=idx),
            "Hammer": pd.Series(hammer, index=idx),
            "Inverted_Hammer": pd.Series(inv_hammer, index=idx),
            "Bullish_Engulfing": pd.Series(bull_engulf, index=idx),
            "Bearish_Engulfing": pd.Series(bear_engulf, index=idx),
            "Morning_Star": pd.Series(morning_star, index=idx),
            "Evening_Star": pd.Series(evening_star, index=idx),
            "Three_White_Soldiers": pd.Series(three_white, index=idx),
            "Three_Black_Crows": pd.Series(three_black, index=idx),
            "Spinning_Top": pd.Series(spinning_top, index=idx),
            "Marubozu_Bullish": pd.Series(marubozu_bull, index=idx),
            "Marubozu_Bearish": pd.Series(marubozu_bear, index=idx),
            "Harami_Bullish": pd.Series(harami_bull, index=idx),
            "Harami_Bearish": pd.Series(harami_bear, index=idx),
        })

    # =========================================================================
    # STATISTICAL INDICATORS (44-50)
    # =========================================================================

    # 44. Linear Regression Channel
    def linear_regression_channel(self, period: int = 50, k: float = 2.0) -> pd.DataFrame:
        """
        Linear Regression Channel:
        - Regression line (y = mx + b) over rolling window
        - Upper/Lower = Regression ± k * Standard Error
        - R-squared and slope angle (degrees)
        """
        close = self.close.values.astype(float)
        n = len(close)
        reg_val = np.full(n, np.nan)
        upper = np.full(n, np.nan)
        lower = np.full(n, np.nan)
        r_squared = np.full(n, np.nan)
        slope_angle = np.full(n, np.nan)

        for i in range(period - 1, n):
            y = close[i - period + 1: i + 1]
            x = np.arange(period, dtype=float)

            # Linear regression: y = mx + b
            x_mean = x.mean()
            y_mean = y.mean()
            ss_xx = ((x - x_mean) ** 2).sum()
            ss_xy = ((x - x_mean) * (y - y_mean)).sum()

            if ss_xx == 0:
                continue

            slope = ss_xy / ss_xx
            intercept = y_mean - slope * x_mean

            y_pred = slope * x + intercept
            reg_val[i] = y_pred[-1]  # Value at current point

            # Standard error of estimate
            residuals = y - y_pred
            se = np.sqrt((residuals ** 2).sum() / max(period - 2, 1))

            upper[i] = reg_val[i] + k * se
            lower[i] = reg_val[i] - k * se

            # R-squared
            ss_res = (residuals ** 2).sum()
            ss_tot = ((y - y_mean) ** 2).sum()
            r_squared[i] = 1 - ss_res / ss_tot if ss_tot != 0 else np.nan

            # Slope angle in degrees
            slope_angle[i] = np.degrees(np.arctan(slope))

        idx = self.df.index
        return pd.DataFrame({
            "LinReg": pd.Series(reg_val, index=idx),
            "LinReg_Upper": pd.Series(upper, index=idx),
            "LinReg_Lower": pd.Series(lower, index=idx),
            "LinReg_R2": pd.Series(r_squared, index=idx),
            "LinReg_Angle": pd.Series(slope_angle, index=idx),
        })

    # 45. Standard Error Bands
    def standard_error_bands(self, period: int = 21, num_se: float = 2.0) -> pd.DataFrame:
        """
        Standard Error Bands:
        Middle = Linear Regression value
        Upper = Middle + num_se * Standard Error
        Lower = Middle - num_se * Standard Error
        """
        close = self.close.values.astype(float)
        n = len(close)
        mid = np.full(n, np.nan)
        upper = np.full(n, np.nan)
        lower = np.full(n, np.nan)

        for i in range(period - 1, n):
            y = close[i - period + 1: i + 1]
            x = np.arange(period, dtype=float)
            x_mean = x.mean()
            y_mean = y.mean()
            ss_xx = ((x - x_mean) ** 2).sum()
            ss_xy = ((x - x_mean) * (y - y_mean)).sum()

            if ss_xx == 0:
                continue

            slope = ss_xy / ss_xx
            intercept = y_mean - slope * x_mean
            y_pred = slope * x + intercept
            mid[i] = y_pred[-1]

            residuals = y - y_pred
            se = np.sqrt((residuals ** 2).sum() / max(period - 2, 1))
            upper[i] = mid[i] + num_se * se
            lower[i] = mid[i] - num_se * se

        idx = self.df.index
        return pd.DataFrame({
            "SE_Upper": pd.Series(upper, index=idx),
            "SE_Middle": pd.Series(mid, index=idx),
            "SE_Lower": pd.Series(lower, index=idx),
        })

    # 46. Z-Score
    def z_score(self, period: int = 20) -> pd.Series:
        """Z-Score = (Close - SMA(period)) / StdDev(period)."""
        sma_val = self._sma(self.close, period)
        std = self.close.rolling(period).std(ddof=1)
        zs = (self.close - sma_val) / std.replace(0, np.nan)
        zs.name = "Z_Score"
        return zs

    # 47. Hurst Exponent
    def hurst_exponent(self, max_lag: int = 100) -> float:
        """
        Hurst Exponent via R/S (Rescaled Range) analysis.
        H < 0.5 = mean-reverting, H = 0.5 = random walk, H > 0.5 = trending.
        Returns a single float for the entire series.
        """
        close = self.close.dropna().values.astype(float)
        n = len(close)
        if n < max_lag:
            max_lag = n // 2

        lags = []
        rs_values = []

        for lag in range(10, max_lag + 1):
            # Divide series into non-overlapping subseries
            n_sub = n // lag
            if n_sub < 1:
                continue

            rs_list = []
            for j in range(n_sub):
                sub = close[j * lag: (j + 1) * lag]
                returns = np.diff(sub)
                if len(returns) == 0:
                    continue
                mean_ret = returns.mean()
                deviate = np.cumsum(returns - mean_ret)
                r = deviate.max() - deviate.min()
                s = returns.std(ddof=1)
                if s > 0 and r > 0:
                    rs_list.append(r / s)

            if len(rs_list) > 0:
                lags.append(lag)
                rs_values.append(np.mean(rs_list))

        if len(lags) < 2:
            return np.nan

        log_lags = np.log(lags)
        log_rs = np.log(rs_values)

        # Linear regression to find slope = Hurst exponent
        slope, _ = np.polyfit(log_lags, log_rs, 1)
        return float(slope)

    # 48. Correlation Coefficient
    def correlation(self, other_series: pd.Series, period: int = 20) -> pd.Series:
        """Rolling Pearson correlation between Close and another series."""
        corr = self.close.rolling(period).corr(other_series)
        corr.name = "Correlation"
        return corr

    # 49. Beta
    def beta(self, market_returns: pd.Series, period: int = 252) -> pd.Series:
        """
        Rolling Beta = Cov(stock_returns, market_returns) / Var(market_returns)
        """
        stock_returns = self.close.pct_change()
        # Align indices
        aligned = pd.DataFrame({"stock": stock_returns, "market": market_returns}).dropna()

        cov = aligned["stock"].rolling(period).cov(aligned["market"])
        var_market = aligned["market"].rolling(period).var()
        beta_val = cov / var_market.replace(0, np.nan)
        beta_val.name = "Beta"
        # Reindex to original
        return beta_val.reindex(self.df.index)

    # 50. Relative Strength vs Market
    def relative_strength(self, market_prices: pd.Series) -> pd.Series:
        """
        Relative Strength = Stock Price / Market Price (ratio line).
        Rising = outperforming, Falling = underperforming.
        """
        rs = self.close / market_prices.reindex(self.df.index).replace(0, np.nan)
        rs.name = "Relative_Strength"
        return rs

    # =========================================================================
    # DIVERGENCE DETECTION
    # =========================================================================

    def detect_divergences(self, price_series: pd.Series, indicator_series: pd.Series,
                           lookback: int = 20) -> pd.DataFrame:
        """
        Detect bullish and bearish divergences between price and an indicator.

        Bullish divergence: price makes lower low, indicator makes higher low.
        Bearish divergence: price makes higher high, indicator makes lower high.

        Returns DataFrame with columns: Bullish_Divergence, Bearish_Divergence (booleans).
        """
        n = len(price_series)
        bullish = np.zeros(n, dtype=bool)
        bearish = np.zeros(n, dtype=bool)

        price = price_series.values.astype(float)
        indicator = indicator_series.values.astype(float)

        # Find local minima and maxima within lookback window
        for i in range(lookback * 2, n):
            # Get the lookback window
            p_window = price[i - lookback: i + 1]
            ind_window = indicator[i - lookback: i + 1]

            if np.any(np.isnan(p_window)) or np.any(np.isnan(ind_window)):
                continue

            # Current is near a local min (in the last few bars)
            recent_p = price[i - 2: i + 1]
            recent_ind = indicator[i - 2: i + 1]

            # Find the lowest price in recent bars and in the earlier part of window
            recent_low_idx = i - 2 + np.argmin(recent_p)
            early_window_p = price[i - lookback: i - lookback // 2]
            early_window_ind = indicator[i - lookback: i - lookback // 2]

            if len(early_window_p) == 0:
                continue

            early_low_idx = i - lookback + np.argmin(early_window_p)
            early_high_idx = i - lookback + np.argmax(early_window_p)

            # Bullish divergence: price lower low, indicator higher low
            if (price[recent_low_idx] < price[early_low_idx] and
                    indicator[recent_low_idx] > indicator[early_low_idx]):
                bullish[i] = True

            # Find the highest price in recent bars and early window
            recent_high_idx = i - 2 + np.argmax(recent_p)

            # Bearish divergence: price higher high, indicator lower high
            if (price[recent_high_idx] > price[early_high_idx] and
                    indicator[recent_high_idx] < indicator[early_high_idx]):
                bearish[i] = True

        return pd.DataFrame({
            "Bullish_Divergence": pd.Series(bullish, index=price_series.index),
            "Bearish_Divergence": pd.Series(bearish, index=price_series.index),
        })

    # =========================================================================
    # COMPUTE ALL
    # =========================================================================

    def compute_all(self) -> Dict:
        """
        Compute ALL 50 indicators and return a dict with:
        - 'latest': dict of the latest (most recent) value for every indicator
        - 'series': dict of full pandas Series/DataFrames for every indicator
        """
        series = {}
        latest = {}

        def _extract_latest(name: str, data):
            """Add data to series dict and extract latest values."""
            series[name] = data
            if isinstance(data, pd.DataFrame):
                for col in data.columns:
                    val = data[col].dropna()
                    latest[col] = val.iloc[-1] if len(val) > 0 else np.nan
            elif isinstance(data, pd.Series):
                val = data.dropna()
                latest[name] = val.iloc[-1] if len(val) > 0 else np.nan
            elif isinstance(data, (int, float)):
                latest[name] = data

        # --- TREND ---
        _extract_latest("SMA", self.sma_all())
        _extract_latest("EMA", self.ema_all())
        _extract_latest("WMA", self.wma_all())
        _extract_latest("HMA", self.hma())
        _extract_latest("DEMA", self.dema())
        _extract_latest("TEMA", self.tema())
        _extract_latest("KAMA", self.kama())
        _extract_latest("MACD", self.macd())
        _extract_latest("PSAR", self.parabolic_sar())
        _extract_latest("Ichimoku", self.ichimoku())
        _extract_latest("Supertrend", self.supertrend())
        _extract_latest("ADX", self.adx())
        _extract_latest("Aroon", self.aroon())
        _extract_latest("Vortex", self.vortex())

        # --- MOMENTUM ---
        _extract_latest("RSI", self.rsi())
        _extract_latest("Stochastic", self.stochastic())
        _extract_latest("StochRSI", self.stochastic_rsi())
        _extract_latest("Williams_R", self.williams_r())
        _extract_latest("CCI", self.cci())
        _extract_latest("ROC", self.roc())
        _extract_latest("Momentum", self.momentum())
        _extract_latest("TSI", self.tsi())
        _extract_latest("Ultimate_Oscillator", self.ultimate_oscillator())
        _extract_latest("Awesome_Oscillator", self.awesome_oscillator())
        _extract_latest("PPO", self.ppo())

        # --- VOLATILITY ---
        _extract_latest("Bollinger", self.bollinger_bands())
        _extract_latest("ATR", self.atr())
        _extract_latest("Keltner", self.keltner_channels())
        _extract_latest("Donchian", self.donchian_channels())
        _extract_latest("HV", self.historical_volatility())
        _extract_latest("Chaikin_Volatility", self.chaikin_volatility())
        _extract_latest("Ulcer_Index", self.ulcer_index())

        # --- VOLUME ---
        _extract_latest("OBV", self.obv())
        _extract_latest("VWAP", self.vwap())
        _extract_latest("AD_Line", self.ad_line())
        _extract_latest("CMF", self.cmf())
        _extract_latest("MFI", self.mfi())
        _extract_latest("Force_Index", self.force_index())
        _extract_latest("EMV", self.ease_of_movement())
        _extract_latest("Volume_ROC", self.volume_roc())

        # --- SUPPORT/RESISTANCE ---
        _extract_latest("Pivot_Points", self.pivot_points())
        _extract_latest("Fibonacci", self.fibonacci_retracement())
        _extract_latest("Candlestick", self.candlestick_patterns())

        # --- STATISTICAL ---
        _extract_latest("LinReg", self.linear_regression_channel())
        _extract_latest("SE_Bands", self.standard_error_bands())
        _extract_latest("Z_Score", self.z_score())
        _extract_latest("Hurst", self.hurst_exponent())

        # Note: correlation, beta, and relative_strength require external
        # series and are not included in compute_all by default.
        # They can be called separately with the required arguments.

        return {"latest": latest, "series": series}
