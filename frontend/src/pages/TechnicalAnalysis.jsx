import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { createChart, CrosshairMode, ColorType, CandlestickSeries, HistogramSeries, LineSeries } from 'lightweight-charts';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Area, ComposedChart,
  Cell, Legend,
} from 'recharts';
import {
  Activity, TrendingUp, BarChart3, Layers, AlertTriangle,
  Gauge, ChevronRight, Loader2,
} from 'lucide-react';
import StockSelector from '../components/StockSelector';
import SignalBadge from '../components/SignalBadge';
import LoadingSkeleton from '../components/LoadingSkeleton';
import useAppStore from '../stores/appStore';
import { fetchOHLCV, fetchIndicators, fetchSignal } from '../services/api';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const PERIODS = [
  { label: '1M', value: '1mo' },
  { label: '3M', value: '3mo' },
  { label: '6M', value: '6mo' },
  { label: '1Y', value: '1y' },
  { label: '2Y', value: '2y' },
];

const INTERVALS = [
  { label: '1D', value: '1d' },
  { label: '1W', value: '1wk' },
];

const OVERLAY_OPTIONS = [
  { key: 'sma20', label: 'SMA 20', color: '#f59e0b' },
  { key: 'sma50', label: 'SMA 50', color: '#3b82f6' },
  { key: 'sma200', label: 'SMA 200', color: '#a855f7' },
  { key: 'ema12', label: 'EMA 12', color: '#10b981' },
  { key: 'ema26', label: 'EMA 26', color: '#ef4444' },
  { key: 'bb', label: 'Bollinger', color: '#64748b' },
  { key: 'supertrend', label: 'Supertrend', color: '#f97316' },
];

const INDICATOR_TABS = [
  { key: 'rsi', label: 'RSI', icon: Activity },
  { key: 'macd', label: 'MACD', icon: TrendingUp },
  { key: 'stochastic', label: 'Stochastic', icon: Gauge },
  { key: 'volume', label: 'Volume', icon: BarChart3 },
];

// Indicator categories for the summary table
const INDICATOR_CATEGORIES = {
  Trend: [
    { key: 'SMA_20', label: 'SMA 20' },
    { key: 'SMA_50', label: 'SMA 50' },
    { key: 'SMA_200', label: 'SMA 200' },
    { key: 'EMA_12', label: 'EMA 12' },
    { key: 'EMA_26', label: 'EMA 26' },
    { key: 'MACD', label: 'MACD' },
    { key: 'MACD_Signal', label: 'MACD Signal' },
    { key: 'MACD_Histogram', label: 'MACD Histogram' },
    { key: 'ADX', label: 'ADX' },
    { key: 'Supertrend', label: 'Supertrend' },
    { key: 'Supertrend_Direction', label: 'Supertrend Direction' },
    { key: 'PSAR', label: 'Parabolic SAR' },
  ],
  Momentum: [
    { key: 'RSI', label: 'RSI (14)' },
    { key: 'Stoch_K', label: 'Stochastic %K' },
    { key: 'Stoch_D', label: 'Stochastic %D' },
    { key: 'Williams_R', label: 'Williams %R' },
    { key: 'CCI', label: 'CCI (20)' },
    { key: 'ROC', label: 'Rate of Change' },
    { key: 'Momentum', label: 'Momentum' },
    { key: 'TSI', label: 'True Strength Index' },
    { key: 'Ultimate_Oscillator', label: 'Ultimate Oscillator' },
    { key: 'Awesome_Oscillator', label: 'Awesome Oscillator' },
  ],
  Volatility: [
    { key: 'BB_Upper', label: 'BB Upper' },
    { key: 'BB_Middle', label: 'BB Middle' },
    { key: 'BB_Lower', label: 'BB Lower' },
    { key: 'BB_Width', label: 'BB Width' },
    { key: 'ATR', label: 'ATR (14)' },
    { key: 'HV', label: 'Historical Volatility' },
    { key: 'Keltner_Upper', label: 'Keltner Upper' },
    { key: 'Keltner_Lower', label: 'Keltner Lower' },
  ],
  Volume: [
    { key: 'OBV', label: 'OBV' },
    { key: 'CMF', label: 'Chaikin Money Flow' },
    { key: 'MFI', label: 'Money Flow Index' },
    { key: 'Force_Index', label: 'Force Index' },
    { key: 'Volume_ROC', label: 'Volume ROC' },
  ],
  Pattern: [
    { key: 'Hammer', label: 'Hammer' },
    { key: 'Shooting_Star', label: 'Shooting Star' },
    { key: 'Bullish_Engulfing', label: 'Bullish Engulfing' },
    { key: 'Bearish_Engulfing', label: 'Bearish Engulfing' },
    { key: 'Morning_Star', label: 'Morning Star' },
    { key: 'Evening_Star', label: 'Evening Star' },
    { key: 'Doji', label: 'Doji' },
    { key: 'Three_White_Soldiers', label: 'Three White Soldiers' },
    { key: 'Three_Black_Crows', label: 'Three Black Crows' },
  ],
  Statistical: [
    { key: 'Z_Score', label: 'Z-Score' },
    { key: 'Hurst', label: 'Hurst Exponent' },
    { key: 'LinReg_Slope', label: 'Linear Reg Slope' },
    { key: 'LinReg_R2', label: 'Linear Reg R-Squared' },
  ],
};

// ---------------------------------------------------------------------------
// Signal helpers
// ---------------------------------------------------------------------------
function classifyIndicatorSignal(key, value, allIndicators) {
  if (value === null || value === undefined) return 'neutral';
  const price = allIndicators?.price || allIndicators?.Close;

  // RSI
  if (key === 'RSI') {
    if (value < 30) return 'bullish';
    if (value > 70) return 'bearish';
    return 'neutral';
  }
  // Stochastic
  if (key === 'Stoch_K' || key === 'Stoch_D') {
    if (value < 20) return 'bullish';
    if (value > 80) return 'bearish';
    return 'neutral';
  }
  // Williams %R
  if (key === 'Williams_R') {
    if (value < -80) return 'bullish';
    if (value > -20) return 'bearish';
    return 'neutral';
  }
  // CCI
  if (key === 'CCI') {
    if (value < -100) return 'bullish';
    if (value > 100) return 'bearish';
    return 'neutral';
  }
  // MFI
  if (key === 'MFI') {
    if (value < 20) return 'bullish';
    if (value > 80) return 'bearish';
    return 'neutral';
  }
  // ADX
  if (key === 'ADX') {
    if (value > 25) return 'bullish';
    return 'neutral';
  }
  // MACD
  if (key === 'MACD') {
    const signal = allIndicators?.MACD_Signal;
    if (signal !== null && signal !== undefined) {
      return value > signal ? 'bullish' : 'bearish';
    }
    return 'neutral';
  }
  if (key === 'MACD_Histogram') {
    return value > 0 ? 'bullish' : value < 0 ? 'bearish' : 'neutral';
  }
  // SMAs and EMAs - price above = bullish
  if (['SMA_20', 'SMA_50', 'SMA_200', 'EMA_12', 'EMA_26'].includes(key)) {
    if (price) return price > value ? 'bullish' : 'bearish';
    return 'neutral';
  }
  // Supertrend direction
  if (key === 'Supertrend_Direction') {
    return value === 1 || value === true ? 'bullish' : 'bearish';
  }
  // BB position
  if (key === 'BB_Upper' && price) {
    return price > value ? 'bearish' : 'neutral';
  }
  if (key === 'BB_Lower' && price) {
    return price < value ? 'bullish' : 'neutral';
  }
  // Z-Score
  if (key === 'Z_Score') {
    if (value < -2) return 'bullish';
    if (value > 2) return 'bearish';
    return 'neutral';
  }
  // Hurst
  if (key === 'Hurst') {
    if (value > 0.6) return 'bullish';
    if (value < 0.4) return 'neutral';
    return 'neutral';
  }
  // CMF
  if (key === 'CMF') {
    return value > 0.05 ? 'bullish' : value < -0.05 ? 'bearish' : 'neutral';
  }
  // OBV - hard to classify without context, neutral by default
  // Pattern booleans
  if (['Hammer', 'Bullish_Engulfing', 'Morning_Star', 'Three_White_Soldiers'].includes(key)) {
    return value ? 'bullish' : 'neutral';
  }
  if (['Shooting_Star', 'Bearish_Engulfing', 'Evening_Star', 'Three_Black_Crows'].includes(key)) {
    return value ? 'bearish' : 'neutral';
  }
  if (key === 'Doji') {
    return value ? 'neutral' : 'neutral';
  }
  return 'neutral';
}

const signalColors = {
  bullish: 'text-emerald-400',
  bearish: 'text-red-400',
  neutral: 'text-amber-400',
};

const signalBg = {
  bullish: 'bg-emerald-500/10',
  bearish: 'bg-red-500/10',
  neutral: 'bg-amber-500/10',
};

// ---------------------------------------------------------------------------
// Custom Recharts tooltip
// ---------------------------------------------------------------------------
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="bg-[#111827] border border-[#1f2937] rounded-md px-3 py-2 shadow-xl">
      <p className="text-[11px] font-mono text-[#64748b] mb-1">{label}</p>
      {payload.map((entry, i) => (
        <p key={i} className="text-xs font-mono" style={{ color: entry.color }}>
          {entry.name}: {typeof entry.value === 'number' ? entry.value.toFixed(2) : entry.value}
        </p>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------
export default function TechnicalAnalysis() {
  const { symbol: urlSymbol } = useParams();
  const { selectedStock, setSelectedStock } = useAppStore();

  useEffect(() => {
    if (urlSymbol && urlSymbol !== selectedStock) {
      setSelectedStock(urlSymbol);
    }
  }, [urlSymbol]);
  const [period, setPeriod] = useState('1y');
  const [interval, setChartInterval] = useState('1d');
  const [overlays, setOverlays] = useState({ sma20: false, sma50: true, sma200: false, ema12: false, ema26: false, bb: false, supertrend: false });
  const [activeTab, setActiveTab] = useState('rsi');

  // Data state
  const [ohlcvData, setOhlcvData] = useState(null);
  const [indicatorData, setIndicatorData] = useState(null);
  const [signalData, setSignalData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Chart refs
  const chartContainerRef = useRef(null);
  const chartInstanceRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const overlaySeriesRef = useRef({});

  // ----- Data fetching -----
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [ohlcv, indicators, signal] = await Promise.all([
          fetchOHLCV(selectedStock, period, interval),
          fetchIndicators(selectedStock, true).catch(() => fetchIndicators(selectedStock)),
          fetchSignal(selectedStock),
        ]);
        if (!cancelled) {
          setOhlcvData(ohlcv);
          setIndicatorData(indicators);
          setSignalData(signal);
        }
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to fetch data');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [selectedStock, period, interval]);

  // ----- TradingView chart -----
  useEffect(() => {
    if (!chartContainerRef.current || !ohlcvData?.data?.length) return;

    // Clean up existing chart
    if (chartInstanceRef.current) {
      chartInstanceRef.current.remove();
      chartInstanceRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
      overlaySeriesRef.current = {};
    }

    const container = chartContainerRef.current;
    const chart = createChart(container, {
      width: container.clientWidth,
      height: 480,
      layout: {
        background: { type: ColorType.Solid, color: '#111827' },
        textColor: '#94a3b8',
        fontSize: 11,
        fontFamily: 'ui-monospace, monospace',
      },
      grid: {
        vertLines: { color: '#1f2937' },
        horzLines: { color: '#1f2937' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: '#3b82f6', width: 1, style: 2, labelBackgroundColor: '#3b82f6' },
        horzLine: { color: '#3b82f6', width: 1, style: 2, labelBackgroundColor: '#3b82f6' },
      },
      rightPriceScale: {
        borderColor: '#1f2937',
        scaleMargins: { top: 0.05, bottom: 0.2 },
      },
      timeScale: {
        borderColor: '#1f2937',
        timeVisible: false,
        secondsVisible: false,
      },
      handleScroll: { vertTouchDrag: false },
    });

    chartInstanceRef.current = chart;

    // Candlestick series (lightweight-charts v5 API)
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#10b981',
      downColor: '#ef4444',
      borderUpColor: '#10b981',
      borderDownColor: '#ef4444',
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    });

    const candleData = ohlcvData.data
      .filter((d) => d.open != null && d.high != null && d.low != null && d.close != null)
      .map((d) => ({
        time: d.date,
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
      }));

    candleSeries.setData(candleData);
    candleSeriesRef.current = candleSeries;

    // Volume histogram (lightweight-charts v5 API)
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });

    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });

    const volumeData = ohlcvData.data
      .filter((d) => d.volume != null && d.close != null && d.open != null)
      .map((d) => ({
        time: d.date,
        value: d.volume,
        color: d.close >= d.open ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)',
      }));

    volumeSeries.setData(volumeData);
    volumeSeriesRef.current = volumeSeries;

    // Fit content
    chart.timeScale().fitContent();

    // ResizeObserver
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width } = entry.contentRect;
        chart.applyOptions({ width });
      }
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartInstanceRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
      overlaySeriesRef.current = {};
    };
  }, [ohlcvData]);

  // ----- Overlay management -----
  useEffect(() => {
    const chart = chartInstanceRef.current;
    if (!chart || !ohlcvData?.data?.length) return;

    const data = ohlcvData.data;

    // Compute overlay data from OHLCV
    const closes = data.map((d) => d.close).filter((c) => c != null);
    const dates = data.filter((d) => d.close != null).map((d) => d.date);

    function sma(period) {
      const result = [];
      for (let i = 0; i < closes.length; i++) {
        if (i < period - 1) {
          result.push(null);
        } else {
          let sum = 0;
          for (let j = i - period + 1; j <= i; j++) sum += closes[j];
          result.push(sum / period);
        }
      }
      return result;
    }

    function ema(period) {
      const k = 2 / (period + 1);
      const result = [closes[0]];
      for (let i = 1; i < closes.length; i++) {
        result.push(closes[i] * k + result[i - 1] * (1 - k));
      }
      return result;
    }

    function bollingerBands(period = 20, mult = 2) {
      const mid = sma(period);
      const upper = [];
      const lower = [];
      for (let i = 0; i < closes.length; i++) {
        if (mid[i] === null) {
          upper.push(null);
          lower.push(null);
        } else {
          let sumSq = 0;
          for (let j = i - period + 1; j <= i; j++) {
            sumSq += (closes[j] - mid[i]) ** 2;
          }
          const std = Math.sqrt(sumSq / period);
          upper.push(mid[i] + mult * std);
          lower.push(mid[i] - mult * std);
        }
      }
      return { upper, mid, lower };
    }

    function supertrendCalc(period = 10, multiplier = 3) {
      const highs = data.filter((d) => d.high != null).map((d) => d.high);
      const lows = data.filter((d) => d.low != null).map((d) => d.low);
      if (highs.length !== closes.length) return closes.map(() => null);

      // ATR
      const tr = [];
      for (let i = 0; i < closes.length; i++) {
        if (i === 0) {
          tr.push(highs[i] - lows[i]);
        } else {
          tr.push(Math.max(highs[i] - lows[i], Math.abs(highs[i] - closes[i - 1]), Math.abs(lows[i] - closes[i - 1])));
        }
      }
      const atr = [];
      for (let i = 0; i < tr.length; i++) {
        if (i < period) {
          atr.push(null);
        } else if (i === period) {
          let s = 0;
          for (let j = 1; j <= period; j++) s += tr[j];
          atr.push(s / period);
        } else {
          atr.push((atr[i - 1] * (period - 1) + tr[i]) / period);
        }
      }

      const supertrend = [];
      let prevUpperBand = 0, prevLowerBand = 0, prevSupertrend = 0;
      for (let i = 0; i < closes.length; i++) {
        if (atr[i] === null) {
          supertrend.push(null);
          continue;
        }
        const hl2 = (highs[i] + lows[i]) / 2;
        let upperBand = hl2 + multiplier * atr[i];
        let lowerBand = hl2 - multiplier * atr[i];

        if (prevUpperBand !== 0) {
          upperBand = closes[i - 1] <= prevUpperBand ? Math.min(upperBand, prevUpperBand) : upperBand;
          lowerBand = closes[i - 1] >= prevLowerBand ? Math.max(lowerBand, prevLowerBand) : lowerBand;
        }

        let st;
        if (prevSupertrend === prevUpperBand) {
          st = closes[i] > upperBand ? lowerBand : upperBand;
        } else {
          st = closes[i] < lowerBand ? upperBand : lowerBand;
        }

        prevUpperBand = upperBand;
        prevLowerBand = lowerBand;
        prevSupertrend = st;
        supertrend.push(st);
      }
      return supertrend;
    }

    function toSeriesData(values, color) {
      return values
        .map((v, i) => (v !== null ? { time: dates[i], value: v } : null))
        .filter(Boolean);
    }

    // Remove existing overlays
    for (const [key, series] of Object.entries(overlaySeriesRef.current)) {
      try {
        chart.removeSeries(series);
      } catch (e) { /* ignore */ }
    }
    overlaySeriesRef.current = {};

    // Add active overlays
    if (overlays.sma20) {
      const s = chart.addSeries(LineSeries,{ color: '#f59e0b', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      s.setData(toSeriesData(sma(20), '#f59e0b'));
      overlaySeriesRef.current.sma20 = s;
    }
    if (overlays.sma50) {
      const s = chart.addSeries(LineSeries,{ color: '#3b82f6', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      s.setData(toSeriesData(sma(50), '#3b82f6'));
      overlaySeriesRef.current.sma50 = s;
    }
    if (overlays.sma200) {
      const s = chart.addSeries(LineSeries,{ color: '#a855f7', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      s.setData(toSeriesData(sma(200), '#a855f7'));
      overlaySeriesRef.current.sma200 = s;
    }
    if (overlays.ema12) {
      const s = chart.addSeries(LineSeries,{ color: '#10b981', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      s.setData(toSeriesData(ema(12), '#10b981'));
      overlaySeriesRef.current.ema12 = s;
    }
    if (overlays.ema26) {
      const s = chart.addSeries(LineSeries,{ color: '#ef4444', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      s.setData(toSeriesData(ema(26), '#ef4444'));
      overlaySeriesRef.current.ema26 = s;
    }
    if (overlays.bb) {
      const bb = bollingerBands(20, 2);
      const sUpper = chart.addSeries(LineSeries,{ color: '#64748b', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
      sUpper.setData(toSeriesData(bb.upper, '#64748b'));
      overlaySeriesRef.current.bbUpper = sUpper;
      const sMid = chart.addSeries(LineSeries,{ color: '#475569', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
      sMid.setData(toSeriesData(bb.mid, '#475569'));
      overlaySeriesRef.current.bbMid = sMid;
      const sLower = chart.addSeries(LineSeries,{ color: '#64748b', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });
      sLower.setData(toSeriesData(bb.lower, '#64748b'));
      overlaySeriesRef.current.bbLower = sLower;
    }
    if (overlays.supertrend) {
      const st = supertrendCalc(10, 3);
      const stData = st
        .map((v, i) => {
          if (v === null) return null;
          const isBullish = closes[i] > v;
          return { time: dates[i], value: v, color: isBullish ? '#10b981' : '#ef4444' };
        })
        .filter(Boolean);
      const s = chart.addSeries(LineSeries,{ lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
      s.setData(stData.map((d) => ({ time: d.time, value: d.value, color: d.color })));
      overlaySeriesRef.current.supertrend = s;
    }
  }, [overlays, ohlcvData]);

  // ----- Derived indicator chart data -----
  const indicatorChartData = useCallback(() => {
    if (!ohlcvData?.data?.length) return [];

    const data = ohlcvData.data;
    const closes = data.map((d) => d.close);

    // RSI
    function computeRSI(period = 14) {
      const changes = [];
      for (let i = 1; i < closes.length; i++) {
        changes.push(closes[i] - closes[i - 1]);
      }
      const rsi = [null]; // first entry has no change
      let avgGain = 0, avgLoss = 0;
      for (let i = 0; i < changes.length; i++) {
        if (i < period) {
          avgGain += Math.max(changes[i], 0);
          avgLoss += Math.max(-changes[i], 0);
          if (i === period - 1) {
            avgGain /= period;
            avgLoss /= period;
            const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
            rsi.push(100 - 100 / (1 + rs));
          } else {
            rsi.push(null);
          }
        } else {
          avgGain = (avgGain * (period - 1) + Math.max(changes[i], 0)) / period;
          avgLoss = (avgLoss * (period - 1) + Math.max(-changes[i], 0)) / period;
          const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
          rsi.push(100 - 100 / (1 + rs));
        }
      }
      return rsi;
    }

    // MACD
    function computeMACD() {
      function ema(arr, period) {
        const k = 2 / (period + 1);
        const result = [arr[0]];
        for (let i = 1; i < arr.length; i++) {
          result.push(arr[i] * k + result[i - 1] * (1 - k));
        }
        return result;
      }
      const ema12 = ema(closes, 12);
      const ema26 = ema(closes, 26);
      const macdLine = closes.map((_, i) => ema12[i] - ema26[i]);
      const signalLine = ema(macdLine, 9);
      const histogram = macdLine.map((v, i) => v - signalLine[i]);
      return { macdLine, signalLine, histogram };
    }

    // Stochastic
    function computeStochastic(period = 14, smoothK = 3, smoothD = 3) {
      const highs = data.map((d) => d.high);
      const lows = data.map((d) => d.low);
      const rawK = [];
      for (let i = 0; i < closes.length; i++) {
        if (i < period - 1) {
          rawK.push(null);
        } else {
          const highSlice = highs.slice(i - period + 1, i + 1);
          const lowSlice = lows.slice(i - period + 1, i + 1);
          const hh = Math.max(...highSlice);
          const ll = Math.min(...lowSlice);
          rawK.push(hh === ll ? 50 : ((closes[i] - ll) / (hh - ll)) * 100);
        }
      }
      // Smooth K
      function smaArr(arr, p) {
        const result = [];
        for (let i = 0; i < arr.length; i++) {
          if (arr[i] === null || i < p - 1) {
            result.push(null);
          } else {
            let cnt = 0, sum = 0;
            for (let j = i - p + 1; j <= i; j++) {
              if (arr[j] !== null) { sum += arr[j]; cnt++; }
            }
            result.push(cnt > 0 ? sum / cnt : null);
          }
        }
        return result;
      }
      const kLine = smaArr(rawK, smoothK);
      const dLine = smaArr(kLine, smoothD);
      return { kLine, dLine };
    }

    // OBV
    function computeOBV() {
      const obv = [0];
      for (let i = 1; i < data.length; i++) {
        const vol = data[i].volume || 0;
        if (closes[i] > closes[i - 1]) obv.push(obv[i - 1] + vol);
        else if (closes[i] < closes[i - 1]) obv.push(obv[i - 1] - vol);
        else obv.push(obv[i - 1]);
      }
      return obv;
    }

    const rsi = computeRSI(14);
    const macd = computeMACD();
    const stoch = computeStochastic(14, 3, 3);
    const obv = computeOBV();

    return data.map((d, i) => ({
      date: d.date,
      rsi: rsi[i] !== null ? parseFloat(rsi[i]?.toFixed(2)) : null,
      macd: parseFloat(macd.macdLine[i]?.toFixed(2)),
      macdSignal: parseFloat(macd.signalLine[i]?.toFixed(2)),
      macdHist: parseFloat(macd.histogram[i]?.toFixed(2)),
      stochK: stoch.kLine[i] !== null ? parseFloat(stoch.kLine[i]?.toFixed(2)) : null,
      stochD: stoch.dLine[i] !== null ? parseFloat(stoch.dLine[i]?.toFixed(2)) : null,
      volume: d.volume,
      volumeColor: d.close >= d.open ? '#10b981' : '#ef4444',
      obv: obv[i],
      close: d.close,
      open: d.open,
    }));
  }, [ohlcvData]);

  const chartData = indicatorChartData();

  // ----- Toggle overlay -----
  function toggleOverlay(key) {
    setOverlays((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  // ----- Error state -----
  if (error) {
    return (
      <div className="min-h-screen bg-[#0c1220] flex items-center justify-center animate-fade-up">
        <div className="bg-[#111827] border border-red-500/30 rounded-lg p-8 max-w-md text-center">
          <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-[#f1f5f9] mb-2">Failed to load data</h2>
          <p className="text-sm text-[#94a3b8] mb-4">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-blue-500/20 text-blue-400 rounded-md text-sm font-medium hover:bg-blue-500/30 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0c1220] text-[#f1f5f9] animate-fade-up">
      <div className="max-w-[1600px] mx-auto px-4 py-6 space-y-4">

        {/* ================================================================
            SECTION 1: HEADER ROW
        ================================================================ */}
        <div className="flex flex-wrap items-center gap-4">
          {/* Stock selector */}
          <StockSelector />

          {/* Period selector */}
          <div className="flex items-center bg-[#111827] border border-[#1f2937] rounded-md overflow-hidden">
            {PERIODS.map((p) => (
              <button
                key={p.value}
                onClick={() => setPeriod(p.value)}
                className={`px-3 py-2 text-xs font-mono font-medium transition-colors ${
                  period === p.value
                    ? 'bg-blue-500/20 text-blue-400'
                    : 'text-[#94a3b8] hover:text-[#f1f5f9] hover:bg-[#1f2937]'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Interval selector */}
          <div className="flex items-center bg-[#111827] border border-[#1f2937] rounded-md overflow-hidden">
            {INTERVALS.map((itv) => (
              <button
                key={itv.value}
                onClick={() => setChartInterval(itv.value)}
                className={`px-3 py-2 text-xs font-mono font-medium transition-colors ${
                  interval === itv.value
                    ? 'bg-blue-500/20 text-blue-400'
                    : 'text-[#94a3b8] hover:text-[#f1f5f9] hover:bg-[#1f2937]'
                }`}
              >
                {itv.label}
              </button>
            ))}
          </div>

          {/* Page title */}
          <div className="ml-auto flex items-center gap-2">
            <Activity className="w-5 h-5 text-blue-400" />
            <h1 className="text-lg font-bold text-[#f1f5f9]">Technical Analysis</h1>
          </div>
        </div>

        {/* ================================================================
            SECTION 2: MAIN CANDLESTICK CHART
        ================================================================ */}
        <div className="bg-[#111827] border border-[#1f2937] rounded-lg overflow-hidden">
          {/* Overlay toggle buttons */}
          <div className="flex flex-wrap items-center gap-2 px-4 py-3 border-b border-[#1f2937]">
            <span className="text-xs font-mono text-[#94a3b8] mr-1">Overlays:</span>
            {OVERLAY_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                onClick={() => toggleOverlay(opt.key)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-mono font-medium transition-all ${
                  overlays[opt.key]
                    ? 'border border-opacity-60 bg-opacity-20'
                    : 'border border-[#1f2937] text-[#94a3b8] hover:text-[#f1f5f9] hover:border-[#64748b]'
                }`}
                style={
                  overlays[opt.key]
                    ? { borderColor: opt.color, backgroundColor: opt.color + '1A', color: opt.color }
                    : {}
                }
              >
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: overlays[opt.key] ? opt.color : '#475569' }}
                />
                {opt.label}
              </button>
            ))}
          </div>

          {/* Chart container */}
          {loading ? (
            <div className="h-[480px] flex items-center justify-center">
              <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
            </div>
          ) : (
            <div ref={chartContainerRef} className="w-full" />
          )}
        </div>

        {/* ================================================================
            SECTION 3: BELOW-CHART INDICATOR PANELS
        ================================================================ */}
        <div className="bg-[#111827] border border-[#1f2937] rounded-lg overflow-hidden">
          {/* Tab buttons */}
          <div className="flex items-center border-b border-[#1f2937]">
            {INDICATOR_TABS.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex items-center gap-2 px-4 py-3 text-xs font-mono font-medium transition-colors border-b-2 ${
                    activeTab === tab.key
                      ? 'border-blue-400 text-blue-400 bg-blue-500/5'
                      : 'border-transparent text-[#94a3b8] hover:text-[#f1f5f9] hover:bg-[#1f2937]/50'
                  }`}
                >
                  <Icon size={14} />
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* Panel content */}
          <div className="p-4">
            {loading ? (
              <LoadingSkeleton variant="chart" />
            ) : chartData.length === 0 ? (
              <div className="h-48 flex items-center justify-center text-[#94a3b8] text-sm font-mono">
                No data available
              </div>
            ) : (
              <>
                {/* RSI Panel */}
                {activeTab === 'rsi' && (
                  <ResponsiveContainer width="100%" height={200}>
                    <ComposedChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                      <XAxis
                        dataKey="date"
                        tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'monospace' }}
                        tickLine={false}
                        axisLine={{ stroke: '#1f2937' }}
                        minTickGap={60}
                      />
                      <YAxis
                        domain={[0, 100]}
                        tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'monospace' }}
                        tickLine={false}
                        axisLine={{ stroke: '#1f2937' }}
                        width={40}
                      />
                      <Tooltip content={<CustomTooltip />} />
                      <ReferenceLine y={70} stroke="#ef4444" strokeDasharray="5 5" strokeWidth={1} />
                      <ReferenceLine y={30} stroke="#10b981" strokeDasharray="5 5" strokeWidth={1} />
                      {/* Overbought fill */}
                      <Area
                        dataKey={(d) => (d.rsi !== null && d.rsi > 70 ? d.rsi : null)}
                        fill="rgba(239, 68, 68, 0.15)"
                        stroke="none"
                        connectNulls={false}
                        isAnimationActive={false}
                        baseValue={70}
                      />
                      {/* Oversold fill */}
                      <Area
                        dataKey={(d) => (d.rsi !== null && d.rsi < 30 ? d.rsi : null)}
                        fill="rgba(16, 185, 129, 0.15)"
                        stroke="none"
                        connectNulls={false}
                        isAnimationActive={false}
                        baseValue={30}
                      />
                      <Line
                        type="monotone"
                        dataKey="rsi"
                        stroke="#3b82f6"
                        strokeWidth={1.5}
                        dot={false}
                        connectNulls
                        isAnimationActive={false}
                        name="RSI"
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                )}

                {/* MACD Panel */}
                {activeTab === 'macd' && (
                  <ResponsiveContainer width="100%" height={200}>
                    <ComposedChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                      <XAxis
                        dataKey="date"
                        tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'monospace' }}
                        tickLine={false}
                        axisLine={{ stroke: '#1f2937' }}
                        minTickGap={60}
                      />
                      <YAxis
                        tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'monospace' }}
                        tickLine={false}
                        axisLine={{ stroke: '#1f2937' }}
                        width={50}
                      />
                      <Tooltip content={<CustomTooltip />} />
                      <ReferenceLine y={0} stroke="#475569" strokeWidth={1} />
                      <Bar dataKey="macdHist" name="Histogram" isAnimationActive={false}>
                        {chartData.map((entry, index) => (
                          <Cell
                            key={`cell-${index}`}
                            fill={entry.macdHist >= 0 ? 'rgba(16, 185, 129, 0.6)' : 'rgba(239, 68, 68, 0.6)'}
                          />
                        ))}
                      </Bar>
                      <Line
                        type="monotone"
                        dataKey="macd"
                        stroke="#3b82f6"
                        strokeWidth={1.5}
                        dot={false}
                        connectNulls
                        isAnimationActive={false}
                        name="MACD"
                      />
                      <Line
                        type="monotone"
                        dataKey="macdSignal"
                        stroke="#f59e0b"
                        strokeWidth={1.5}
                        dot={false}
                        connectNulls
                        isAnimationActive={false}
                        name="Signal"
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                )}

                {/* Stochastic Panel */}
                {activeTab === 'stochastic' && (
                  <ResponsiveContainer width="100%" height={200}>
                    <ComposedChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                      <XAxis
                        dataKey="date"
                        tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'monospace' }}
                        tickLine={false}
                        axisLine={{ stroke: '#1f2937' }}
                        minTickGap={60}
                      />
                      <YAxis
                        domain={[0, 100]}
                        tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'monospace' }}
                        tickLine={false}
                        axisLine={{ stroke: '#1f2937' }}
                        width={40}
                      />
                      <Tooltip content={<CustomTooltip />} />
                      <ReferenceLine y={80} stroke="#ef4444" strokeDasharray="5 5" strokeWidth={1} />
                      <ReferenceLine y={20} stroke="#10b981" strokeDasharray="5 5" strokeWidth={1} />
                      <Line
                        type="monotone"
                        dataKey="stochK"
                        stroke="#3b82f6"
                        strokeWidth={1.5}
                        dot={false}
                        connectNulls
                        isAnimationActive={false}
                        name="%K"
                      />
                      <Line
                        type="monotone"
                        dataKey="stochD"
                        stroke="#f59e0b"
                        strokeWidth={1.5}
                        dot={false}
                        connectNulls
                        isAnimationActive={false}
                        name="%D"
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                )}

                {/* Volume Panel */}
                {activeTab === 'volume' && (
                  <ResponsiveContainer width="100%" height={200}>
                    <ComposedChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                      <XAxis
                        dataKey="date"
                        tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'monospace' }}
                        tickLine={false}
                        axisLine={{ stroke: '#1f2937' }}
                        minTickGap={60}
                      />
                      <YAxis
                        yAxisId="vol"
                        tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'monospace' }}
                        tickLine={false}
                        axisLine={{ stroke: '#1f2937' }}
                        width={60}
                        tickFormatter={(v) => {
                          if (v >= 1e9) return (v / 1e9).toFixed(1) + 'B';
                          if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M';
                          if (v >= 1e3) return (v / 1e3).toFixed(0) + 'K';
                          return v;
                        }}
                      />
                      <YAxis
                        yAxisId="obv"
                        orientation="right"
                        tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'monospace' }}
                        tickLine={false}
                        axisLine={{ stroke: '#1f2937' }}
                        width={60}
                        tickFormatter={(v) => {
                          if (Math.abs(v) >= 1e9) return (v / 1e9).toFixed(1) + 'B';
                          if (Math.abs(v) >= 1e6) return (v / 1e6).toFixed(1) + 'M';
                          if (Math.abs(v) >= 1e3) return (v / 1e3).toFixed(0) + 'K';
                          return v;
                        }}
                      />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="volume" yAxisId="vol" name="Volume" isAnimationActive={false}>
                        {chartData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.volumeColor + '99'} />
                        ))}
                      </Bar>
                      <Line
                        type="monotone"
                        dataKey="obv"
                        yAxisId="obv"
                        stroke="#a855f7"
                        strokeWidth={1.5}
                        dot={false}
                        connectNulls
                        isAnimationActive={false}
                        name="OBV"
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                )}
              </>
            )}
          </div>
        </div>

        {/* Bottom row: indicator table + signal breakdown */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">

          {/* ================================================================
              SECTION 4: INDICATOR SUMMARY TABLE
          ================================================================ */}
          <div className="xl:col-span-2 bg-[#111827] border border-[#1f2937] rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-[#1f2937] flex items-center gap-2">
              <Layers size={16} className="text-blue-400" />
              <h2 className="text-sm font-bold text-[#f1f5f9]">Indicator Summary</h2>
            </div>

            {loading ? (
              <div className="p-4">
                <LoadingSkeleton variant="table" />
              </div>
            ) : indicatorData?.latest ? (
              <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
                <table className="w-full text-xs font-mono">
                  <thead className="sticky top-0 bg-[#111827] z-10">
                    <tr className="border-b border-[#1f2937]">
                      <th className="text-left px-4 py-2.5 text-[#94a3b8] font-medium">Category</th>
                      <th className="text-left px-4 py-2.5 text-[#94a3b8] font-medium">Indicator</th>
                      <th className="text-right px-4 py-2.5 text-[#94a3b8] font-medium">Value</th>
                      <th className="text-center px-4 py-2.5 text-[#94a3b8] font-medium">Signal</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(INDICATOR_CATEGORIES).map(([category, indicators]) => {
                      const validIndicators = indicators.filter((ind) => {
                        const val = indicatorData.latest[ind.key];
                        return val !== null && val !== undefined;
                      });
                      if (validIndicators.length === 0) return null;

                      return validIndicators.map((ind, idx) => {
                        const val = indicatorData.latest[ind.key];
                        const signal = classifyIndicatorSignal(ind.key, val, indicatorData.latest);
                        const displayVal =
                          typeof val === 'boolean'
                            ? val ? 'Detected' : '-'
                            : typeof val === 'number'
                              ? Math.abs(val) >= 1e6
                                ? (val / 1e6).toFixed(2) + 'M'
                                : val.toFixed(4)
                              : String(val);

                        return (
                          <tr
                            key={ind.key}
                            className="border-b border-[#1f2937]/50 hover:bg-[#1f2937]/30 transition-colors"
                          >
                            <td className="px-4 py-2 text-[#94a3b8]">
                              {idx === 0 ? (
                                <span className="text-blue-400 font-semibold">{category}</span>
                              ) : (
                                ''
                              )}
                            </td>
                            <td className="px-4 py-2 text-[#f1f5f9]">{ind.label}</td>
                            <td className="px-4 py-2 text-right text-[#f1f5f9] tabular-nums">{displayVal}</td>
                            <td className="px-4 py-2 text-center">
                              <span
                                className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${signalColors[signal]} ${signalBg[signal]}`}
                              >
                                {signal}
                              </span>
                            </td>
                          </tr>
                        );
                      });
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-8 text-center text-[#94a3b8] text-sm font-mono">
                No indicator data available
              </div>
            )}
          </div>

          {/* ================================================================
              SECTION 5: SIGNAL BREAKDOWN CARD
          ================================================================ */}
          <div className="bg-[#111827] border border-[#1f2937] rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-[#1f2937] flex items-center gap-2">
              <TrendingUp size={16} className="text-blue-400" />
              <h2 className="text-sm font-bold text-[#f1f5f9]">Signal Breakdown</h2>
            </div>

            {loading ? (
              <div className="p-4">
                <LoadingSkeleton variant="gauge" />
              </div>
            ) : signalData ? (
              <div className="p-4 space-y-5">
                {/* Composite score */}
                <div className="text-center space-y-2">
                  <div className="text-3xl font-mono font-bold tabular-nums"
                    style={{
                      color: signalData.composite_score >= 30 ? '#10b981'
                        : signalData.composite_score <= -30 ? '#ef4444'
                        : '#f59e0b',
                    }}
                  >
                    {signalData.composite_score > 0 ? '+' : ''}{signalData.composite_score?.toFixed(1)}
                  </div>
                  <SignalBadge score={signalData.composite_score} size="lg" />
                </div>

                {/* Factor bars */}
                <div className="space-y-2.5">
                  {signalData.breakdown && Object.entries(signalData.breakdown).map(([key, value]) => {
                    const label = key.replace('_score', '').replace(/_/g, ' ');
                    const weight = signalData.weights?.[key.replace('_score', '')] || 0;
                    const pct = Math.abs(value);
                    const isPositive = value >= 0;

                    return (
                      <div key={key}>
                        <div className="flex items-center justify-between text-[11px] font-mono mb-1">
                          <span className="text-[#94a3b8] capitalize">{label}</span>
                          <div className="flex items-center gap-2">
                            <span className="text-[#64748b] text-[10px]">
                              {(weight * 100).toFixed(0)}%
                            </span>
                            <span className={isPositive ? 'text-emerald-400' : 'text-red-400'}>
                              {isPositive ? '+' : ''}{value?.toFixed(1)}
                            </span>
                          </div>
                        </div>
                        <div className="h-1.5 bg-[#1f2937] rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-500"
                            style={{
                              width: `${Math.min(pct, 100)}%`,
                              backgroundColor: isPositive ? '#10b981' : '#ef4444',
                            }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Factor bar chart (Recharts) */}
                {signalData.breakdown && (
                  <div className="pt-2">
                    <ResponsiveContainer width="100%" height={180}>
                      <BarChart
                        data={Object.entries(signalData.breakdown).map(([key, value]) => ({
                          name: key.replace('_score', '').replace(/_/g, ' ').slice(0, 5),
                          fullName: key.replace('_score', '').replace(/_/g, ' '),
                          value: parseFloat(value?.toFixed(1)),
                        }))}
                        margin={{ top: 5, right: 5, bottom: 5, left: 5 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                        <XAxis
                          dataKey="name"
                          tick={{ fill: '#94a3b8', fontSize: 9, fontFamily: 'monospace' }}
                          tickLine={false}
                          axisLine={{ stroke: '#1f2937' }}
                        />
                        <YAxis
                          tick={{ fill: '#94a3b8', fontSize: 9, fontFamily: 'monospace' }}
                          tickLine={false}
                          axisLine={{ stroke: '#1f2937' }}
                          width={35}
                        />
                        <Tooltip
                          content={({ active, payload }) => {
                            if (!active || !payload?.length) return null;
                            const d = payload[0].payload;
                            return (
                              <div className="bg-[#111827] border border-[#1f2937] rounded-md px-3 py-2 shadow-xl">
                                <p className="text-[11px] font-mono text-[#94a3b8] capitalize">{d.fullName}</p>
                                <p className="text-xs font-mono" style={{ color: d.value >= 0 ? '#10b981' : '#ef4444' }}>
                                  {d.value >= 0 ? '+' : ''}{d.value}
                                </p>
                              </div>
                            );
                          }}
                        />
                        <ReferenceLine y={0} stroke="#475569" />
                        <Bar dataKey="value" radius={[2, 2, 0, 0]} isAnimationActive={false}>
                          {Object.entries(signalData.breakdown).map(([key, value], index) => (
                            <Cell
                              key={`cell-${index}`}
                              fill={value >= 0 ? 'rgba(16, 185, 129, 0.7)' : 'rgba(239, 68, 68, 0.7)'}
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {/* Active alerts */}
                {signalData.alerts && signalData.alerts.length > 0 && (
                  <div className="space-y-2 pt-2">
                    <h3 className="text-xs font-mono font-semibold text-[#94a3b8] flex items-center gap-1.5">
                      <AlertTriangle size={12} className="text-amber-400" />
                      Active Alerts
                    </h3>
                    <div className="space-y-1.5 max-h-48 overflow-y-auto">
                      {signalData.alerts.map((alert, i) => (
                        <div
                          key={i}
                          className={`flex items-start gap-2 px-3 py-2 rounded text-[11px] font-mono ${
                            alert.severity === 'critical'
                              ? 'bg-red-500/10 border border-red-500/20'
                              : alert.severity === 'warning'
                                ? 'bg-amber-500/10 border border-amber-500/20'
                                : 'bg-slate-500/10 border border-slate-500/20'
                          }`}
                        >
                          <ChevronRight
                            size={12}
                            className={`mt-0.5 flex-shrink-0 ${
                              alert.severity === 'critical' ? 'text-red-400' : alert.severity === 'warning' ? 'text-amber-400' : 'text-[#94a3b8]'
                            }`}
                          />
                          <div>
                            <span className={`font-bold ${
                              alert.severity === 'critical' ? 'text-red-400' : alert.severity === 'warning' ? 'text-amber-400' : 'text-[#94a3b8]'
                            }`}>
                              {alert.type.replace(/_/g, ' ')}
                            </span>
                            <p className="text-[#94a3b8] mt-0.5">{alert.message}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {signalData.alerts && signalData.alerts.length === 0 && (
                  <div className="text-center py-4 text-[#94a3b8] text-xs font-mono">
                    No active alerts
                  </div>
                )}
              </div>
            ) : (
              <div className="p-8 text-center text-[#94a3b8] text-sm font-mono">
                No signal data available
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
