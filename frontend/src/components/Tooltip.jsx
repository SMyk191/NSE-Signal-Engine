import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Info } from 'lucide-react';

/**
 * Tooltip component that renders via portal to avoid overflow issues.
 * Usage: <Tooltip text="RSI measures momentum..."><span>RSI</span></Tooltip>
 * Or with icon: <Tooltip text="..." showIcon>RSI</Tooltip>
 */
export default function Tooltip({ children, text, showIcon = false, maxWidth = 280 }) {
  const [visible, setVisible] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const triggerRef = useRef(null);
  const tooltipRef = useRef(null);

  useEffect(() => {
    if (visible && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      const tooltipH = tooltipRef.current?.offsetHeight || 60;
      const tooltipW = Math.min(maxWidth, window.innerWidth - 16);

      let top = rect.top - tooltipH - 8;
      let left = rect.left + rect.width / 2 - tooltipW / 2;

      // Flip below if no room above
      if (top < 8) top = rect.bottom + 8;
      // Clamp horizontal
      if (left < 8) left = 8;
      if (left + tooltipW > window.innerWidth - 8) left = window.innerWidth - tooltipW - 8;

      setPos({ top, left });
    }
  }, [visible, maxWidth]);

  const tooltip = visible ? (
    <div
      ref={tooltipRef}
      style={{
        position: 'fixed',
        top: pos.top,
        left: pos.left,
        zIndex: 999999,
        maxWidth,
        pointerEvents: 'none',
      }}
      className="px-3 py-2.5 bg-[#1e293b] border border-[#334155] rounded-lg shadow-xl shadow-black/40"
    >
      <p className="text-xs text-[#e2e8f0] leading-relaxed">{text}</p>
    </div>
  ) : null;

  return (
    <>
      <span
        ref={triggerRef}
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
        className="inline-flex items-center gap-1 cursor-help"
      >
        {children}
        {showIcon && (
          <Info className="w-3 h-3 text-[#475569] hover:text-[#94a3b8] transition-colors" />
        )}
      </span>
      {createPortal(tooltip, document.body)}
    </>
  );
}

/* ─── Indicator tooltip definitions ──────────────────────────── */
export const INDICATOR_TOOLTIPS = {
  // Trend
  RSI: 'Relative Strength Index measures momentum on a 0-100 scale. Below 30 = oversold (buy signal), above 70 = overbought (sell signal). Ideal range: 40-60 for neutral.',
  MACD: 'Moving Average Convergence Divergence shows trend direction and momentum. MACD above signal line = bullish. Histogram growing = strengthening momentum.',
  'Stoch %K': 'Stochastic %K measures where price closed relative to the range. Below 20 = oversold, above 80 = overbought. Best signals when %K crosses %D.',
  'Williams %R': 'Williams %R is a momentum oscillator (-100 to 0). Below -80 = oversold (potential buy), above -20 = overbought (potential sell).',
  ADX: 'Average Directional Index measures trend strength (not direction). Below 20 = weak/no trend, 20-40 = developing trend, above 40 = strong trend.',
  'Bollinger %B': 'Bollinger %B shows where price is relative to Bollinger Bands. Below 0 = below lower band (oversold), above 1 = above upper band (overbought). Ideal: 0.2-0.8.',
  'Volume Ratio': 'Current volume vs 20-day average. Above 1.5x = high activity (confirms moves), below 0.5x = low interest. 1.0x = normal.',
  '52W Range': 'Position within 52-week high-low range. Near 0% = at yearly low, near 100% = at yearly high.',

  // Moving Averages
  SMA: 'Simple Moving Average smooths price data. Price above SMA = bullish, below = bearish. SMA 50 crossing above SMA 200 = Golden Cross (strong buy).',
  EMA: 'Exponential Moving Average gives more weight to recent prices. Faster than SMA. EMA crossovers signal trend changes.',
  'SMA 20': 'Short-term trend. Price above = short-term bullish.',
  'SMA 50': 'Medium-term trend. Often used as dynamic support/resistance.',
  'SMA 200': 'Long-term trend. Price above = long-term bullish. Most important moving average for institutional investors.',

  // Volatility
  ATR: 'Average True Range measures volatility in price terms. Higher ATR = more volatile. Used for stop-loss placement (typically 2x ATR below entry).',
  'BB Width': 'Bollinger Bandwidth measures volatility. Narrow bands (squeeze) = low volatility, often precedes a breakout. Wide bands = high volatility.',
  'Hist. Vol': 'Historical Volatility (annualized). Below 20% = low vol, 20-40% = moderate, above 40% = high. Compare with ATR for context.',

  // Volume
  OBV: 'On-Balance Volume tracks cumulative buying/selling pressure. Rising OBV confirms uptrend. Divergence from price = potential reversal.',
  CMF: 'Chaikin Money Flow measures buying/selling pressure over 20 days. Above 0 = net buying, below 0 = net selling. Strong signal above 0.1 or below -0.1.',
  MFI: 'Money Flow Index is volume-weighted RSI. Below 20 = oversold, above 80 = overbought. More reliable than RSI because it includes volume.',

  // Pattern
  Doji: 'Candlestick with tiny body — shows indecision. After a trend, it signals potential reversal. Confirm with next candle.',
  Hammer: 'Bullish reversal pattern at bottom of downtrend. Long lower shadow (2x body), small body at top. Signals selling exhaustion.',
  'Engulfing Bull': 'Green candle completely engulfs previous red candle. Strong bullish reversal, especially at support levels.',
  'Engulfing Bear': 'Red candle completely engulfs previous green candle. Strong bearish reversal, especially at resistance levels.',
  'Morning Star': '3-candle bullish reversal: long red → small body (indecision) → long green. Very reliable at support.',
  'Evening Star': '3-candle bearish reversal: long green → small body → long red. Very reliable at resistance.',

  // Statistical
  'Z-Score': 'Standard deviations from 20-day mean. Below -2 = statistically oversold, above +2 = overbought. Mean reversion signal.',
  Hurst: 'Hurst Exponent measures trend persistence. Above 0.5 = trending, below 0.5 = mean-reverting, ~0.5 = random walk.',
  'LinReg Slope': 'Linear Regression slope shows trend direction and steepness. Positive = uptrend, negative = downtrend.',
  'R²': 'R-squared shows how well price follows a linear trend. Above 0.8 = strong trend, below 0.3 = noisy/no clear trend.',

  // Fundamentals
  'P/E': 'Price-to-Earnings ratio. Below 15 = potentially undervalued, 15-25 = fair, above 25 = expensive. Compare within same sector.',
  'P/B': 'Price-to-Book ratio. Below 1 = trading below asset value, 1-3 = fair for most sectors, above 3 = premium valuation.',
  PEG: 'P/E divided by earnings growth rate. Below 1 = undervalued growth, 1-2 = fair, above 2 = overvalued. Best growth metric.',
  ROE: 'Return on Equity. Above 15% = good, above 20% = excellent. Shows how efficiently the company uses shareholders\' money.',
  ROA: 'Return on Assets. Above 5% = good for most sectors, above 10% = excellent. Asset-heavy industries have lower ROA.',
  'Debt/Equity': 'Below 0.5 = conservative, 0.5-1.0 = moderate, above 1.0 = leveraged. Compare within sector — banks naturally have higher D/E.',
  ROCE: 'Return on Capital Employed. Above 15% = good, above 20% = excellent. Best profitability measure — accounts for debt.',
  'Div Yield': 'Annual dividend as % of price. Above 2% = decent income, above 4% = high yield. Verify payout ratio is sustainable.',
  'Altman Z': 'Bankruptcy predictor. Above 3.0 = safe, 1.8-3.0 = gray zone, below 1.8 = distress. Developed for manufacturing firms.',
  Piotroski: 'Financial strength score (0-9). 8-9 = very strong, 5-7 = moderate, 0-4 = weak. Based on profitability, leverage, and efficiency.',

  // Composite
  'Composite Score': 'Weighted combination of trend (20%), momentum (20%), volatility (10%), volume (10%), pattern (10%), statistical (10%), sentiment (10%), and earnings (10%). Range: -100 to +100.',
  'Trend Score': 'Based on price vs SMAs, MACD, Ichimoku cloud, and Supertrend. Positive = price in uptrend across multiple timeframes.',
  'Momentum Score': 'Based on RSI, Stochastic, Williams %R, CCI, and divergences. Detects overbought/oversold conditions.',
  'Volatility Score': 'Based on Bollinger Band position, ATR trend, and historical volatility. Low vol near support = opportunity.',
  'Volume Score': 'Based on OBV trend, CMF, MFI, and volume spikes. Confirms whether price moves have institutional backing.',
  'Pattern Score': 'Based on detected candlestick patterns (hammer, engulfing, stars, etc.). Reversal patterns at key levels are most reliable.',
  'Statistical Score': 'Based on Z-score, Hurst exponent, and linear regression. Identifies statistically extreme moves and trend persistence.',

  // Options
  PCR: 'Put-Call Ratio. Above 1.0 = more puts than calls (contrarian bullish — put writers provide support). Below 0.7 = more calls (bearish). 0.7-1.0 = neutral.',
  'Max Pain': 'Strike price where option buyers lose the most money. Price tends to gravitate toward max pain near expiry.',
  'OI Buildup': 'Open Interest buildup shows where smart money is positioning. High put OI = support, high call OI = resistance.',
};
