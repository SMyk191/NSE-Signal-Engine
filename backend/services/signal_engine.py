from __future__ import annotations

"""
Composite Signal Scoring Engine
Produces a composite score from -100 to +100 based on multiple indicator categories.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class Alert:
    timestamp: datetime
    alert_type: str
    symbol: str
    message: str
    severity: str  # "info", "warning", "critical"
    score: Optional[float] = None


@dataclass
class SignalResult:
    symbol: str
    composite_score: float
    signal: str  # STRONG BUY, BUY, HOLD, SELL, STRONG SELL
    trend_score: float
    momentum_score: float
    volatility_score: float
    volume_score: float
    pattern_score: float
    statistical_score: float
    sentiment_score: float
    earnings_score: float
    alerts: list = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


def _clamp(value: float, low: float = -100.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


class SignalEngine:
    """
    Takes indicator results and produces a composite score from -100 to +100.

    COMPOSITE = w1*Trend + w2*Momentum + w3*Volatility + w4*Volume
                + w5*Pattern + w6*Statistical + w7*Sentiment + w8*Earnings
    """

    DEFAULT_WEIGHTS = {
        "trend": 0.20,
        "momentum": 0.20,
        "volatility": 0.10,
        "volume": 0.10,
        "pattern": 0.10,
        "statistical": 0.10,
        "sentiment": 0.10,
        "earnings": 0.10,
    }

    SIGNAL_THRESHOLDS = [
        (60, "STRONG BUY"),
        (30, "BUY"),
        (-30, "HOLD"),
        (-60, "SELL"),
    ]
    DEFAULT_SIGNAL = "STRONG SELL"

    def __init__(self, weights: Optional[dict] = None):
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self._previous_scores: dict[str, float] = {}
        self._previous_indicators: dict[str, dict] = {}

    # ------------------------------------------------------------------ #
    #  Score classification
    # ------------------------------------------------------------------ #
    @staticmethod
    def classify_score(score: float) -> str:
        for threshold, label in SignalEngine.SIGNAL_THRESHOLDS:
            if score >= threshold:
                return label
        return SignalEngine.DEFAULT_SIGNAL

    # ------------------------------------------------------------------ #
    #  TREND SCORE  (-100 to +100)
    # ------------------------------------------------------------------ #
    def compute_trend_score(self, indicators: dict) -> float:
        score = 0.0
        price = indicators.get("price")
        sma20 = indicators.get("sma20")
        sma50 = indicators.get("sma50")
        sma200 = indicators.get("sma200")
        macd = indicators.get("macd")
        macd_signal = indicators.get("macd_signal")
        macd_hist = indicators.get("macd_hist")
        macd_hist_prev = indicators.get("macd_hist_prev")
        above_ichimoku_cloud = indicators.get("above_ichimoku_cloud")
        supertrend_bullish = indicators.get("supertrend_bullish")

        if price is not None and sma200 is not None:
            score += 20 if price > sma200 else -20

        if price is not None and sma50 is not None:
            score += 15 if price > sma50 else -15

        if price is not None and sma20 is not None:
            score += 10 if price > sma20 else -10

        if sma50 is not None and sma200 is not None:
            score += 15 if sma50 > sma200 else -15

        if macd is not None and macd_signal is not None:
            score += 10 if macd > macd_signal else -10

        if macd_hist is not None and macd_hist_prev is not None:
            score += 10 if macd_hist > macd_hist_prev else -10

        if above_ichimoku_cloud is not None:
            score += 10 if above_ichimoku_cloud else -10

        if supertrend_bullish is not None:
            score += 10 if supertrend_bullish else -10

        return _clamp(score)

    # ------------------------------------------------------------------ #
    #  MOMENTUM SCORE  (-100 to +100)
    # ------------------------------------------------------------------ #
    def compute_momentum_score(self, indicators: dict) -> float:
        score = 0.0
        rsi = indicators.get("rsi")
        stoch_k = indicators.get("stoch_k")
        stoch_d = indicators.get("stoch_d")
        stoch_k_prev = indicators.get("stoch_k_prev")
        stoch_d_prev = indicators.get("stoch_d_prev")
        williams_r = indicators.get("williams_r")
        cci = indicators.get("cci")
        cci_prev = indicators.get("cci_prev")
        bullish_divergence = indicators.get("bullish_divergence", False)
        bearish_divergence = indicators.get("bearish_divergence", False)

        # RSI scoring
        if rsi is not None:
            if rsi < 30:
                score += 30
            elif rsi > 70:
                score -= 30

        # Stochastic scoring — bullish cross below 20 / bearish cross above 80
        if stoch_k is not None and stoch_d is not None:
            if stoch_k_prev is not None and stoch_d_prev is not None:
                bullish_cross = stoch_k < 20 and stoch_k_prev <= stoch_d_prev and stoch_k > stoch_d
                bearish_cross = stoch_k > 80 and stoch_k_prev >= stoch_d_prev and stoch_k < stoch_d
                if bullish_cross:
                    score += 20
                elif bearish_cross:
                    score -= 20

        # Williams %R
        if williams_r is not None:
            if williams_r < -80:
                score += 15
            elif williams_r > -20:
                score -= 15

        # CCI
        if cci is not None and cci_prev is not None:
            if cci < -100 and cci > cci_prev:
                score += 15
            elif cci > 100 and cci < cci_prev:
                score -= 15

        # Divergence bonuses
        if bullish_divergence:
            score += 20
        if bearish_divergence:
            score -= 20

        return _clamp(score)

    # ------------------------------------------------------------------ #
    #  VOLATILITY SCORE  (-100 to +100)
    # ------------------------------------------------------------------ #
    def compute_volatility_score(self, indicators: dict) -> float:
        score = 0.0
        bb_upper = indicators.get("bb_upper")
        bb_lower = indicators.get("bb_lower")
        bb_mid = indicators.get("bb_mid")
        bb_width = indicators.get("bb_width")
        bb_width_prev = indicators.get("bb_width_prev")
        price = indicators.get("price")
        atr = indicators.get("atr")
        atr_prev = indicators.get("atr_prev")
        historical_vol = indicators.get("historical_volatility")

        # Bollinger Band position
        if price is not None and bb_upper is not None and bb_lower is not None and bb_mid is not None:
            bb_range = bb_upper - bb_lower
            if bb_range > 0:
                position = (price - bb_lower) / bb_range
                if position > 0.95:
                    score -= 25  # near upper band = overbought
                elif position < 0.05:
                    score += 25  # near lower band = oversold
                elif 0.4 <= position <= 0.6:
                    score += 5   # near middle = neutral-positive

        # BB squeeze detection (narrowing bands)
        if bb_width is not None and bb_width_prev is not None:
            if bb_width < bb_width_prev * 0.8:
                score += 15  # squeeze building energy

        # ATR trend
        if atr is not None and atr_prev is not None:
            if atr > atr_prev * 1.2:
                score -= 10  # rising volatility = caution
            elif atr < atr_prev * 0.8:
                score += 10

        # Historical volatility
        if historical_vol is not None:
            if historical_vol < 15:
                score += 10
            elif historical_vol > 40:
                score -= 15

        return _clamp(score)

    # ------------------------------------------------------------------ #
    #  VOLUME SCORE  (-100 to +100)
    # ------------------------------------------------------------------ #
    def compute_volume_score(self, indicators: dict) -> float:
        score = 0.0
        obv = indicators.get("obv")
        obv_sma20 = indicators.get("obv_sma20")
        cmf = indicators.get("cmf")
        mfi = indicators.get("mfi")
        vroc = indicators.get("vroc")

        # OBV vs its 20-period SMA
        if obv is not None and obv_sma20 is not None:
            if obv > obv_sma20:
                score += 25
            else:
                score -= 25

        # Chaikin Money Flow
        if cmf is not None:
            if cmf > 0.1:
                score += 20
            elif cmf < -0.1:
                score -= 20

        # Money Flow Index
        if mfi is not None:
            if mfi < 20:
                score += 15  # oversold
            elif mfi > 80:
                score -= 15  # overbought

        # Volume Rate of Change
        if vroc is not None:
            if vroc > 50:
                score += 10
            elif vroc < -50:
                score -= 10

        return _clamp(score)

    # ------------------------------------------------------------------ #
    #  PATTERN SCORE  (-100 to +100)
    # ------------------------------------------------------------------ #
    def compute_pattern_score(self, indicators: dict) -> float:
        score = 0.0
        patterns = indicators.get("candlestick_patterns", {})
        chart_patterns = indicators.get("chart_patterns", {})

        # Candlestick pattern scoring
        bullish_candle_patterns = [
            "hammer", "morning_star", "bullish_engulfing",
            "piercing_line", "three_white_soldiers", "dragonfly_doji",
        ]
        bearish_candle_patterns = [
            "shooting_star", "evening_star", "bearish_engulfing",
            "dark_cloud_cover", "three_black_crows", "gravestone_doji",
        ]

        for pat in bullish_candle_patterns:
            if patterns.get(pat):
                score += 15

        for pat in bearish_candle_patterns:
            if patterns.get(pat):
                score -= 15

        # Chart patterns
        bullish_chart = ["double_bottom", "inverse_head_shoulders", "ascending_triangle", "cup_and_handle"]
        bearish_chart = ["double_top", "head_and_shoulders", "descending_triangle"]

        for pat in bullish_chart:
            if chart_patterns.get(pat):
                score += 20

        for pat in bearish_chart:
            if chart_patterns.get(pat):
                score -= 20

        return _clamp(score)

    # ------------------------------------------------------------------ #
    #  STATISTICAL SCORE  (-100 to +100)
    # ------------------------------------------------------------------ #
    def compute_statistical_score(self, indicators: dict) -> float:
        score = 0.0
        zscore = indicators.get("price_zscore")
        hurst = indicators.get("hurst_exponent")
        mean_reversion_signal = indicators.get("mean_reversion_signal")
        linear_reg_slope = indicators.get("linear_reg_slope")

        # Z-score: measures distance from mean
        if zscore is not None:
            if zscore < -2.0:
                score += 30  # heavily oversold statistically
            elif zscore < -1.0:
                score += 15
            elif zscore > 2.0:
                score -= 30
            elif zscore > 1.0:
                score -= 15

        # Hurst exponent: > 0.5 trending, < 0.5 mean-reverting
        if hurst is not None:
            if hurst > 0.6:
                score += 15  # trending — go with the flow
            elif hurst < 0.4:
                score += 10  # mean-reverting — expect snap back

        # Direct mean reversion signal
        if mean_reversion_signal is not None:
            score += mean_reversion_signal * 20  # expects -1 to +1

        # Linear regression slope
        if linear_reg_slope is not None:
            if linear_reg_slope > 0:
                score += 15
            elif linear_reg_slope < 0:
                score -= 15

        return _clamp(score)

    # ------------------------------------------------------------------ #
    #  SENTIMENT SCORE  (-100 to +100)
    # ------------------------------------------------------------------ #
    def compute_sentiment_score(self, indicators: dict) -> float:
        """Expects a sentiment_score in range -1.0 to +1.0 from the sentiment analyzer."""
        raw = indicators.get("sentiment_score")
        if raw is None:
            return 0.0
        return _clamp(raw * 100)

    # ------------------------------------------------------------------ #
    #  EARNINGS SCORE  (-100 to +100)
    # ------------------------------------------------------------------ #
    def compute_earnings_score(self, indicators: dict) -> float:
        score = 0.0
        earnings = indicators.get("earnings", {})

        eps_surprise_pct = earnings.get("eps_surprise_pct")
        peg_ratio = earnings.get("peg_ratio")
        piotroski = earnings.get("piotroski_f_score")
        altman_z = earnings.get("altman_z_score")
        margin_trend = earnings.get("margin_trend")  # "improving" / "declining" / "stable"
        accrual_ratio = earnings.get("accrual_ratio")

        # EPS surprise
        if eps_surprise_pct is not None:
            if eps_surprise_pct > 10:
                score += 20
            elif eps_surprise_pct > 0:
                score += 10
            elif eps_surprise_pct < -10:
                score -= 20
            elif eps_surprise_pct < 0:
                score -= 10

        # PEG ratio
        if peg_ratio is not None:
            if 0 < peg_ratio < 1:
                score += 15  # undervalued growth
            elif peg_ratio > 2:
                score -= 10

        # Piotroski F-Score
        if piotroski is not None:
            if piotroski >= 7:
                score += 20
            elif piotroski >= 5:
                score += 10
            elif piotroski <= 2:
                score -= 20
            elif piotroski <= 4:
                score -= 10

        # Altman Z-Score
        if altman_z is not None:
            if altman_z > 2.99:
                score += 15
            elif altman_z < 1.81:
                score -= 20
            else:
                score -= 5

        # Margin trend
        if margin_trend == "improving":
            score += 10
        elif margin_trend == "declining":
            score -= 10

        # Accrual ratio — high accruals are a red flag
        if accrual_ratio is not None:
            if accrual_ratio > 0.10:
                score -= 10
            elif accrual_ratio < -0.05:
                score += 5

        return _clamp(score)

    # ------------------------------------------------------------------ #
    #  ALERT GENERATION
    # ------------------------------------------------------------------ #
    def generate_alerts(self, symbol: str, indicators: dict, composite_score: float) -> list[Alert]:
        alerts: list[Alert] = []
        now = datetime.now()
        prev = self._previous_scores.get(symbol)
        prev_ind = self._previous_indicators.get(symbol, {})

        # 1. Score crosses 30 or -30
        if prev is not None:
            if prev < 30 <= composite_score:
                alerts.append(Alert(now, "SCORE_CROSS_UP", symbol,
                                    f"Composite score crossed above +30 ({composite_score:.1f})", "warning", composite_score))
            elif prev >= 30 > composite_score:
                alerts.append(Alert(now, "SCORE_CROSS_DOWN", symbol,
                                    f"Composite score crossed below +30 ({composite_score:.1f})", "warning", composite_score))
            if prev > -30 >= composite_score:
                alerts.append(Alert(now, "SCORE_CROSS_DOWN", symbol,
                                    f"Composite score crossed below -30 ({composite_score:.1f})", "warning", composite_score))
            elif prev <= -30 < composite_score:
                alerts.append(Alert(now, "SCORE_CROSS_UP", symbol,
                                    f"Composite score crossed above -30 ({composite_score:.1f})", "warning", composite_score))

        # 2. RSI enters oversold / overbought
        rsi = indicators.get("rsi")
        prev_rsi = prev_ind.get("rsi")
        if rsi is not None:
            if rsi < 30 and (prev_rsi is None or prev_rsi >= 30):
                alerts.append(Alert(now, "RSI_OVERSOLD", symbol,
                                    f"RSI entered oversold territory ({rsi:.1f})", "critical"))
            elif rsi > 70 and (prev_rsi is None or prev_rsi <= 70):
                alerts.append(Alert(now, "RSI_OVERBOUGHT", symbol,
                                    f"RSI entered overbought territory ({rsi:.1f})", "critical"))

        # 3. MACD crossover
        macd = indicators.get("macd")
        macd_signal = indicators.get("macd_signal")
        prev_macd = prev_ind.get("macd")
        prev_macd_signal = prev_ind.get("macd_signal")
        if all(v is not None for v in [macd, macd_signal, prev_macd, prev_macd_signal]):
            if prev_macd <= prev_macd_signal and macd > macd_signal:
                alerts.append(Alert(now, "MACD_BULLISH_CROSS", symbol,
                                    "MACD crossed above signal line (bullish)", "warning"))
            elif prev_macd >= prev_macd_signal and macd < macd_signal:
                alerts.append(Alert(now, "MACD_BEARISH_CROSS", symbol,
                                    "MACD crossed below signal line (bearish)", "warning"))

        # 4. Golden / Death Cross
        sma50 = indicators.get("sma50")
        sma200 = indicators.get("sma200")
        prev_sma50 = prev_ind.get("sma50")
        prev_sma200 = prev_ind.get("sma200")
        if all(v is not None for v in [sma50, sma200, prev_sma50, prev_sma200]):
            if prev_sma50 <= prev_sma200 and sma50 > sma200:
                alerts.append(Alert(now, "GOLDEN_CROSS", symbol,
                                    "Golden Cross detected: SMA50 crossed above SMA200", "critical"))
            elif prev_sma50 >= prev_sma200 and sma50 < sma200:
                alerts.append(Alert(now, "DEATH_CROSS", symbol,
                                    "Death Cross detected: SMA50 crossed below SMA200", "critical"))

        # 5. BB squeeze + breakout
        bb_width = indicators.get("bb_width")
        bb_width_prev = indicators.get("bb_width_prev")
        price = indicators.get("price")
        bb_upper = indicators.get("bb_upper")
        bb_lower = indicators.get("bb_lower")
        if bb_width is not None and bb_width_prev is not None:
            squeeze = bb_width < bb_width_prev * 0.8
            if squeeze and price is not None:
                if bb_upper is not None and price > bb_upper:
                    alerts.append(Alert(now, "BB_SQUEEZE_BREAKOUT_UP", symbol,
                                        "Bollinger Band squeeze with upside breakout", "critical"))
                elif bb_lower is not None and price < bb_lower:
                    alerts.append(Alert(now, "BB_SQUEEZE_BREAKOUT_DOWN", symbol,
                                        "Bollinger Band squeeze with downside breakout", "critical"))

        # 6. Unusual volume (> 2x 20-day avg)
        current_volume = indicators.get("volume")
        avg_volume_20 = indicators.get("avg_volume_20")
        if current_volume is not None and avg_volume_20 is not None and avg_volume_20 > 0:
            if current_volume > 2 * avg_volume_20:
                alerts.append(Alert(now, "UNUSUAL_VOLUME", symbol,
                                    f"Unusual volume detected: {current_volume:,.0f} vs avg {avg_volume_20:,.0f} "
                                    f"({current_volume / avg_volume_20:.1f}x)", "warning"))

        # 7. Candlestick reversal at support/resistance
        patterns = indicators.get("candlestick_patterns", {})
        at_support = indicators.get("at_support", False)
        at_resistance = indicators.get("at_resistance", False)
        bullish_reversals = ["hammer", "morning_star", "bullish_engulfing", "piercing_line", "dragonfly_doji"]
        bearish_reversals = ["shooting_star", "evening_star", "bearish_engulfing", "dark_cloud_cover", "gravestone_doji"]

        if at_support:
            for pat in bullish_reversals:
                if patterns.get(pat):
                    alerts.append(Alert(now, "REVERSAL_AT_SUPPORT", symbol,
                                        f"Bullish {pat.replace('_', ' ')} at support level", "critical"))
                    break

        if at_resistance:
            for pat in bearish_reversals:
                if patterns.get(pat):
                    alerts.append(Alert(now, "REVERSAL_AT_RESISTANCE", symbol,
                                        f"Bearish {pat.replace('_', ' ')} at resistance level", "critical"))
                    break

        return alerts

    # ------------------------------------------------------------------ #
    #  MAIN: compute composite signal
    # ------------------------------------------------------------------ #
    def compute_signal(self, symbol: str, indicators: dict) -> SignalResult:
        """
        Main entry point. Takes a dict of indicator values and returns
        a SignalResult with composite score and alerts.
        """
        trend = self.compute_trend_score(indicators)
        momentum = self.compute_momentum_score(indicators)
        volatility = self.compute_volatility_score(indicators)
        volume = self.compute_volume_score(indicators)
        pattern = self.compute_pattern_score(indicators)
        statistical = self.compute_statistical_score(indicators)
        sentiment = self.compute_sentiment_score(indicators)
        earnings = self.compute_earnings_score(indicators)

        composite = (
            self.weights["trend"] * trend
            + self.weights["momentum"] * momentum
            + self.weights["volatility"] * volatility
            + self.weights["volume"] * volume
            + self.weights["pattern"] * pattern
            + self.weights["statistical"] * statistical
            + self.weights["sentiment"] * sentiment
            + self.weights["earnings"] * earnings
        )
        composite = _clamp(composite)

        signal = self.classify_score(composite)

        alerts = self.generate_alerts(symbol, indicators, composite)

        # Store current state for next comparison
        self._previous_scores[symbol] = composite
        self._previous_indicators[symbol] = indicators.copy()

        return SignalResult(
            symbol=symbol,
            composite_score=round(composite, 2),
            signal=signal,
            trend_score=round(trend, 2),
            momentum_score=round(momentum, 2),
            volatility_score=round(volatility, 2),
            volume_score=round(volume, 2),
            pattern_score=round(pattern, 2),
            statistical_score=round(statistical, 2),
            sentiment_score=round(sentiment, 2),
            earnings_score=round(earnings, 2),
            alerts=alerts,
        )
