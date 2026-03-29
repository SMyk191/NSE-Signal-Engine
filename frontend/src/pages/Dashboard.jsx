import { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Plus, AlertTriangle, TrendingUp, TrendingDown, Minus,
  ArrowUp, ArrowDown, Activity, BarChart2,
} from 'lucide-react';
import useAppStore from '../stores/appStore';
import StockSelector, { NIFTY_50 } from '../components/StockSelector';
import ScoreGauge from '../components/ScoreGauge';
import SignalBadge from '../components/SignalBadge';
import ActionPanel from '../components/ActionPanel';
import Tooltip, { INDICATOR_TOOLTIPS } from '../components/Tooltip';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

/* ─── Sector lookup ──────────────────────────────────────────── */
const SECTOR_MAP = {
  ADANIENT: 'Conglomerate', ADANIPORTS: 'Infrastructure', APOLLOHOSP: 'Healthcare',
  ASIANPAINT: 'Consumer Goods', AXISBANK: 'Banking', 'BAJAJ-AUTO': 'Automobile',
  BAJFINANCE: 'Financial Services', BAJAJFINSV: 'Financial Services',
  BHARTIARTL: 'Telecom', BPCL: 'Energy', BRITANNIA: 'FMCG', CIPLA: 'Pharma',
  COALINDIA: 'Mining', DIVISLAB: 'Pharma', DRREDDY: 'Pharma', EICHERMOT: 'Automobile',
  GRASIM: 'Cement & Textiles', HCLTECH: 'IT', HDFCBANK: 'Banking',
  HDFCLIFE: 'Insurance', HEROMOTOCO: 'Automobile', HINDALCO: 'Metals',
  HINDUNILVR: 'FMCG', ICICIBANK: 'Banking', INDUSINDBK: 'Banking', INFY: 'IT',
  ITC: 'FMCG', JSWSTEEL: 'Metals', KOTAKBANK: 'Banking', LT: 'Infrastructure',
  LTIM: 'IT', 'M&M': 'Automobile', MARUTI: 'Automobile', NESTLEIND: 'FMCG',
  NTPC: 'Energy', ONGC: 'Energy', POWERGRID: 'Energy', RELIANCE: 'Energy',
  SBILIFE: 'Insurance', SBIN: 'Banking', SUNPHARMA: 'Pharma',
  TATACONSUM: 'FMCG', TATAMOTORS: 'Automobile', TATASTEEL: 'Metals',
  TCS: 'IT', TECHM: 'IT', TITAN: 'Consumer Goods', ULTRACEMCO: 'Cement',
  UPL: 'Agrochemicals', WIPRO: 'IT',
};

/* ─── Animation keyframes (injected once) ────────────────────── */
const styleId = 'dashboard-animations';
if (typeof document !== 'undefined' && !document.getElementById(styleId)) {
  const style = document.createElement('style');
  style.id = styleId;
  style.textContent = `
    @keyframes fadeUp {
      from { opacity: 0; transform: translateY(12px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    .anim-fade-up {
      animation: fadeUp 0.5s ease-out both;
    }
  `;
  document.head.appendChild(style);
}

/* ─── Helpers ────────────────────────────────────────────────── */
function fmt(v) {
  if (v == null) return '--';
  return `\u20B9${Number(v).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
}

function fmtCompact(v) {
  if (v == null) return '--';
  const n = Number(v);
  if (n >= 1e7) return `\u20B9${(n / 1e7).toFixed(2)}Cr`;
  if (n >= 1e5) return `\u20B9${(n / 1e5).toFixed(2)}L`;
  if (n >= 1e3) return `\u20B9${(n / 1e3).toFixed(1)}K`;
  return fmt(v);
}

function rsiInterpretation(rsi) {
  if (rsi == null) return 'N/A';
  if (rsi > 70) return 'Overbought';
  if (rsi < 30) return 'Oversold';
  return 'Neutral';
}

function volumeInterpretation(vr) {
  if (vr == null) return 'N/A';
  if (vr > 1.5) return 'High';
  if (vr < 0.7) return 'Low';
  return 'Normal';
}

function adxInterpretation(adx) {
  if (adx == null) return 'N/A';
  if (adx > 40) return 'Strong';
  if (adx > 25) return 'Trending';
  return 'Weak';
}

function signalBorderColor(score) {
  if (score >= 30) return '#22c55e';
  if (score <= -30) return '#ef4444';
  return '#f59e0b';
}

function clamp(val, min, max) {
  return Math.max(min, Math.min(max, val));
}

/* ─── Market Pulse Strip ─────────────────────────────────────── */
function MarketPulseStrip({ marketData }) {
  if (!marketData) return null;

  const {
    nifty_level, nifty_change_pct,
    advances, declines,
    breadth,
  } = marketData;

  const adRatio = advances && declines ? (advances / (declines || 1)).toFixed(2) : null;
  const breadthLabel = breadth || (adRatio > 1.5 ? 'Bullish' : adRatio < 0.7 ? 'Bearish' : 'Neutral');
  const breadthColor = breadthLabel === 'Bullish' ? '#22c55e' : breadthLabel === 'Bearish' ? '#ef4444' : '#f59e0b';

  return (
    <div className="anim-fade-up flex items-center gap-3 px-4 py-2.5 rounded-lg bg-[#0c1220]/60 border border-[#1f2937]/50 overflow-x-auto" style={{ animationDelay: '120ms' }}>
      {/* NIFTY 50 */}
      {nifty_level != null && (
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-[10px] uppercase tracking-wider text-[#64748b] font-medium">NIFTY 50</span>
          <span className="font-mono text-xs font-semibold text-[#f1f5f9] tabular-nums">
            {Number(nifty_level).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
          </span>
          {nifty_change_pct != null && (
            <span className={`font-mono text-[11px] font-semibold tabular-nums px-1.5 py-0.5 rounded ${nifty_change_pct >= 0 ? 'bg-[#22c55e]/10 text-[#22c55e]' : 'bg-[#ef4444]/10 text-[#ef4444]'}`}>
              {nifty_change_pct >= 0 ? '+' : ''}{nifty_change_pct.toFixed(2)}%
            </span>
          )}
        </div>
      )}

      <span className="w-px h-4 bg-[#1f2937] flex-shrink-0" />

      {/* A/D Ratio */}
      {adRatio && (
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <span className="text-[10px] uppercase tracking-wider text-[#64748b] font-medium">A/D</span>
          <span className="font-mono text-xs text-[#94a3b8] tabular-nums">
            <span className="text-[#22c55e]">{advances}</span>
            <span className="text-[#64748b]">/</span>
            <span className="text-[#ef4444]">{declines}</span>
          </span>
        </div>
      )}

      <span className="w-px h-4 bg-[#1f2937] flex-shrink-0" />

      {/* Breadth */}
      <div className="flex items-center gap-1.5 flex-shrink-0">
        <Activity className="w-3 h-3" style={{ color: breadthColor }} />
        <span className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: breadthColor }}>
          {breadthLabel}
        </span>
      </div>
    </div>
  );
}

/* ─── Mini Horizontal Bar ────────────────────────────────────── */
function MiniBar({ value, min = 0, max = 100, color }) {
  const pct = clamp(((value - min) / (max - min)) * 100, 0, 100);
  return (
    <div className="w-full h-[3px] rounded-full bg-[#1f2937] mt-1">
      <div
        className="h-full rounded-full transition-all duration-700"
        style={{ width: `${pct}%`, backgroundColor: color }}
      />
    </div>
  );
}

/* ─── Quick Indicator Cell ───────────────────────────────────── */
function IndicatorCell({ label, value, displayValue, visual, color, delay = 0, tooltip }) {
  const labelEl = (
    <span className="text-[9px] uppercase tracking-wider text-[#64748b] font-medium mb-0.5 truncate">
      {label}
    </span>
  );
  return (
    <div
      className="anim-fade-up flex flex-col px-3 py-2.5 rounded-lg bg-[#0c1220]/80 border border-[#1f2937]/60 min-w-0"
      style={{ animationDelay: `${delay}ms` }}
    >
      {tooltip ? <Tooltip text={tooltip} showIcon>{labelEl}</Tooltip> : labelEl}
      <span className="font-mono text-sm font-semibold tabular-nums leading-tight" style={{ color }}>
        {displayValue ?? (value != null ? (typeof value === 'number' ? value.toFixed(1) : value) : '--')}
      </span>
      {visual}
    </div>
  );
}

/* ─── Quick Indicators Grid (8 indicators, 2 rows) ──────────── */
function QuickIndicatorsGrid({ signal }) {
  if (!signal) return null;

  const rsi = signal.rsi;
  const macd = signal.macd_signal;
  const macdHist = signal.macd_histogram;
  const stochK = signal.stochastic_k;
  const williamsR = signal.williams_r;
  const adx = signal.adx;
  const bollingerB = signal.bollinger_pctb;
  const volRatio = signal.volume_ratio;
  const high52 = signal.high_52w;
  const low52 = signal.low_52w;
  const price = signal.price;

  // RSI color
  const rsiColor = rsi > 70 ? '#ef4444' : rsi < 30 ? '#22c55e' : '#f1f5f9';
  // MACD color
  const macdColor = macd === 'bullish' ? '#22c55e' : macd === 'bearish' ? '#ef4444' : '#94a3b8';
  // Stochastic color
  const stochColor = stochK > 80 ? '#ef4444' : stochK < 20 ? '#22c55e' : '#f1f5f9';
  // Williams %R color
  const wrColor = williamsR != null ? (williamsR > -20 ? '#ef4444' : williamsR < -80 ? '#22c55e' : '#f1f5f9') : '#94a3b8';
  // ADX color
  const adxColor = adx > 40 ? '#22c55e' : adx > 25 ? '#f59e0b' : '#64748b';
  // Bollinger %B color
  const bbColor = bollingerB > 1 ? '#ef4444' : bollingerB < 0 ? '#22c55e' : '#f1f5f9';
  // Volume color
  const volColor = volRatio > 1.5 ? '#22c55e' : volRatio < 0.7 ? '#ef4444' : '#f1f5f9';
  // 52W range position
  const rangePos = (high52 && low52 && price) ? ((price - low52) / (high52 - low52)) * 100 : null;
  const rangeColor = rangePos != null ? (rangePos > 80 ? '#22c55e' : rangePos < 20 ? '#ef4444' : '#f59e0b') : '#94a3b8';

  return (
    <div className="anim-fade-up" style={{ animationDelay: '160ms' }}>
      <div className="flex items-center gap-2 mb-2">
        <BarChart2 className="w-3.5 h-3.5 text-[#64748b]" />
        <span className="text-[10px] uppercase tracking-wider text-[#64748b] font-semibold">Quick Indicators</span>
      </div>
      <div className="grid grid-cols-4 gap-2">
        {/* Row 1 */}
        <IndicatorCell
          label="RSI (14)"
          value={rsi}
          color={rsiColor}
          delay={180}
          tooltip={INDICATOR_TOOLTIPS.RSI}
          visual={rsi != null ? <MiniBar value={rsi} min={0} max={100} color={rsiColor} /> : null}
        />
        <IndicatorCell
          label="MACD"
          displayValue={macd === 'bullish' ? '\u25B2 Bull' : macd === 'bearish' ? '\u25BC Bear' : '--'}
          color={macdColor}
          delay={220}
          tooltip={INDICATOR_TOOLTIPS.MACD}
          visual={macdHist != null ? (
            <span className="font-mono text-[10px] tabular-nums mt-0.5" style={{ color: macdHist >= 0 ? '#22c55e' : '#ef4444' }}>
              H: {macdHist >= 0 ? '+' : ''}{macdHist.toFixed(2)}
            </span>
          ) : null}
        />
        <IndicatorCell
          label="Stoch %K"
          value={stochK}
          color={stochColor}
          delay={260}
          tooltip={INDICATOR_TOOLTIPS['Stoch %K']}
          visual={stochK != null ? <MiniBar value={stochK} min={0} max={100} color={stochColor} /> : null}
        />
        <IndicatorCell
          label="Williams %R"
          value={williamsR}
          color={wrColor}
          delay={300}
          tooltip={INDICATOR_TOOLTIPS['Williams %R']}
          visual={williamsR != null ? <MiniBar value={-williamsR} min={0} max={100} color={wrColor} /> : null}
        />

        {/* Row 2 */}
        <IndicatorCell
          label="ADX"
          value={adx}
          displayValue={adx != null ? `${adx.toFixed(1)} ${adx > 40 ? 'Strong' : adx > 25 ? 'Trend' : 'Weak'}` : '--'}
          color={adxColor}
          delay={340}
          tooltip={INDICATOR_TOOLTIPS.ADX}
          visual={adx != null ? <MiniBar value={adx} min={0} max={60} color={adxColor} /> : null}
        />
        <IndicatorCell
          label="Boll %B"
          value={bollingerB}
          color={bbColor}
          delay={380}
          tooltip={INDICATOR_TOOLTIPS['Bollinger %B']}
          visual={bollingerB != null ? <MiniBar value={clamp(bollingerB * 100, 0, 100)} min={0} max={100} color={bbColor} /> : null}
        />
        <IndicatorCell
          label="Vol Ratio"
          displayValue={volRatio != null ? `${volRatio.toFixed(2)}x` : '--'}
          color={volColor}
          delay={420}
          tooltip={INDICATOR_TOOLTIPS['Volume Ratio']}
          visual={volRatio != null ? (
            <span className="text-[10px] mt-0.5" style={{ color: volColor }}>
              {volRatio > 1.5 ? 'High' : volRatio < 0.7 ? 'Low' : 'Normal'}
            </span>
          ) : null}
        />
        <IndicatorCell
          label="52W Range"
          displayValue={rangePos != null ? `${rangePos.toFixed(0)}%` : '--'}
          color={rangeColor}
          delay={460}
          tooltip={INDICATOR_TOOLTIPS['52W Range']}
          visual={rangePos != null ? <MiniBar value={rangePos} min={0} max={100} color={rangeColor} /> : null}
        />
      </div>
    </div>
  );
}

/* ─── Compact Factor Bar (inline, one-line) ──────────────────── */
function CompactFactorBar({ label, value, maxAbs = 30, tooltip }) {
  const clamped = Math.max(-maxAbs, Math.min(maxAbs, value));
  const pct = Math.abs(clamped) / maxAbs * 100;
  const isPositive = value >= 0;
  const color = isPositive ? '#22c55e' : '#ef4444';

  const labelEl = <span className="text-[11px] text-[#94a3b8] w-20 text-right flex-shrink-0 truncate">{label}</span>;

  return (
    <div className="flex items-center gap-2 py-1">
      {tooltip ? <Tooltip text={tooltip}>{labelEl}</Tooltip> : labelEl}
      <div className="flex-1 h-[6px] rounded-full bg-[#1f2937] relative overflow-hidden">
        <div
          className="absolute top-0 h-full rounded-full transition-all duration-500"
          style={{
            width: `${pct / 2}%`,
            backgroundColor: color,
            opacity: 0.85,
            left: isPositive ? '50%' : 'auto',
            right: isPositive ? 'auto' : '50%',
          }}
        />
        <div className="absolute left-1/2 top-0 bottom-0 w-px bg-[#374151]" />
      </div>
      <span className={`font-mono text-[11px] font-semibold tabular-nums w-9 text-right ${isPositive ? 'text-[#22c55e]' : 'text-[#ef4444]'}`}>
        {value > 0 ? '+' : ''}{value.toFixed(1)}
      </span>
    </div>
  );
}

/* ─── Key Fundamentals Strip ─────────────────────────────────── */
function FundamentalsStrip({ signal }) {
  if (!signal) return null;

  const items = [
    { label: 'P/E', value: signal.pe_ratio != null ? signal.pe_ratio.toFixed(1) : null },
    { label: 'P/B', value: signal.pb_ratio != null ? signal.pb_ratio.toFixed(1) : null },
    { label: 'Mkt Cap', value: signal.market_cap != null ? fmtCompact(signal.market_cap) : null },
    { label: '52W H', value: signal.high_52w != null ? fmt(signal.high_52w) : null },
    { label: '52W L', value: signal.low_52w != null ? fmt(signal.low_52w) : null },
    { label: 'Div Yield', value: signal.dividend_yield != null ? `${signal.dividend_yield.toFixed(2)}%` : null },
  ].filter((item) => item.value != null);

  if (items.length === 0) return null;

  return (
    <div className="anim-fade-up flex items-center gap-4 px-4 py-2 rounded-lg bg-[#0c1220]/40 border border-[#1f2937]/30 overflow-x-auto" style={{ animationDelay: '250ms' }}>
      {items.map((item, idx) => (
        <div key={item.label} className="flex items-center gap-1.5 flex-shrink-0">
          <span className="text-[9px] uppercase tracking-wider text-[#64748b] font-medium">{item.label}</span>
          <span className="font-mono text-[11px] text-[#94a3b8] font-semibold tabular-nums">{item.value}</span>
          {idx < items.length - 1 && <span className="w-px h-3 bg-[#1f2937] ml-2" />}
        </div>
      ))}
    </div>
  );
}

/* ─── Portfolio / Top Movers Table ───────────────────────────── */
function PortfolioTable({ portfolio, signals, topMovers }) {
  const hasPortfolio = portfolio.length > 0;

  const rows = hasPortfolio
    ? [...portfolio].sort((a, b) => {
        const sa = signals[a.symbol]?.composite_score ?? 0;
        const sb = signals[b.symbol]?.composite_score ?? 0;
        return sb - sa;
      })
    : [];

  // Show top movers if portfolio is empty
  if (!hasPortfolio && topMovers) {
    const { gainers = [], losers = [] } = topMovers;

    return (
      <div className="space-y-4">
        {/* Gainers */}
        {gainers.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-3.5 h-3.5 text-[#22c55e]" />
              <span className="text-[10px] uppercase tracking-wider text-[#22c55e] font-semibold">Top Gainers</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[#1f2937]">
                    <th className="px-3 py-2 text-[10px] uppercase tracking-wider font-medium text-[#64748b] text-left">Symbol</th>
                    <th className="px-3 py-2 text-[10px] uppercase tracking-wider font-medium text-[#64748b] text-right">Price</th>
                    <th className="px-3 py-2 text-[10px] uppercase tracking-wider font-medium text-[#64748b] text-right">Change</th>
                    <th className="px-3 py-2 text-[10px] uppercase tracking-wider font-medium text-[#64748b] text-right">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {gainers.map((s, idx) => (
                    <tr key={s.symbol} className="anim-fade-up border-b border-[#1f2937]/30 hover:bg-[#1f2937]/20 transition-colors" style={{ animationDelay: `${idx * 50}ms` }}>
                      <td className="px-3 py-2 text-xs font-medium text-white">{s.symbol}</td>
                      <td className="px-3 py-2 font-mono text-xs text-[#94a3b8] text-right tabular-nums">{s.price != null ? fmt(s.price) : '--'}</td>
                      <td className="px-3 py-2 font-mono text-xs font-medium text-[#22c55e] text-right tabular-nums">+{(s.change_pct ?? 0).toFixed(2)}%</td>
                      <td className="px-3 py-2 text-right">{s.composite_score != null ? <SignalBadge score={s.composite_score} size="sm" /> : '--'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Losers */}
        {losers.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <TrendingDown className="w-3.5 h-3.5 text-[#ef4444]" />
              <span className="text-[10px] uppercase tracking-wider text-[#ef4444] font-semibold">Top Losers</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[#1f2937]">
                    <th className="px-3 py-2 text-[10px] uppercase tracking-wider font-medium text-[#64748b] text-left">Symbol</th>
                    <th className="px-3 py-2 text-[10px] uppercase tracking-wider font-medium text-[#64748b] text-right">Price</th>
                    <th className="px-3 py-2 text-[10px] uppercase tracking-wider font-medium text-[#64748b] text-right">Change</th>
                    <th className="px-3 py-2 text-[10px] uppercase tracking-wider font-medium text-[#64748b] text-right">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {losers.map((s, idx) => (
                    <tr key={s.symbol} className="anim-fade-up border-b border-[#1f2937]/30 hover:bg-[#1f2937]/20 transition-colors" style={{ animationDelay: `${idx * 50}ms` }}>
                      <td className="px-3 py-2 text-xs font-medium text-white">{s.symbol}</td>
                      <td className="px-3 py-2 font-mono text-xs text-[#94a3b8] text-right tabular-nums">{s.price != null ? fmt(s.price) : '--'}</td>
                      <td className="px-3 py-2 font-mono text-xs font-medium text-[#ef4444] text-right tabular-nums">{(s.change_pct ?? 0).toFixed(2)}%</td>
                      <td className="px-3 py-2 text-right">{s.composite_score != null ? <SignalBadge score={s.composite_score} size="sm" /> : '--'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {gainers.length === 0 && losers.length === 0 && (
          <p className="text-sm text-[#64748b] py-10 text-center">
            Add stocks to your portfolio to track them here
          </p>
        )}
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <p className="text-sm text-[#64748b] py-10 text-center">
        Add stocks to your portfolio to track them here
      </p>
    );
  }

  const headers = [
    { key: 'symbol', label: 'Symbol', align: 'text-left' },
    { key: 'price', label: 'Price', align: 'text-right' },
    { key: 'change', label: 'Change', align: 'text-right' },
    { key: 'rsi', label: 'RSI', align: 'text-right' },
    { key: 'signal', label: 'Signal', align: 'text-center' },
    { key: 'score', label: 'Score', align: 'text-right' },
  ];

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-[#1f2937]">
            {headers.map((h) => (
              <th
                key={h.key}
                className={`px-4 py-2.5 text-[10px] uppercase tracking-wider font-medium text-[#64748b] ${h.align}`}
              >
                {h.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(({ symbol }, idx) => {
            const sig = signals[symbol];
            const changePct = sig?.change_pct ?? 0;
            const isUp = changePct >= 0;

            return (
              <tr
                key={symbol}
                className="anim-fade-up border-b border-[#1f2937]/40 hover:bg-[#1f2937]/20 transition-colors"
                style={{ animationDelay: `${idx * 60}ms` }}
              >
                <td className="px-4 py-3 text-sm font-medium text-white text-left">
                  {symbol}
                </td>
                <td className="px-4 py-3 font-mono text-sm text-[#94a3b8] text-right tabular-nums">
                  {sig?.price != null ? fmt(sig.price) : '--'}
                </td>
                <td className={`px-4 py-3 font-mono text-sm font-medium text-right tabular-nums ${isUp ? 'text-[#22c55e]' : 'text-[#ef4444]'}`}>
                  {sig ? `${isUp ? '+' : ''}${changePct.toFixed(2)}%` : '--'}
                </td>
                <td className="px-4 py-3 font-mono text-sm text-[#94a3b8] text-right tabular-nums">
                  {sig?.rsi != null ? sig.rsi.toFixed(1) : '--'}
                </td>
                <td className="px-4 py-3 text-center">
                  {sig ? <SignalBadge score={sig.composite_score ?? 0} size="sm" /> : '--'}
                </td>
                <td className="px-4 py-3 font-mono text-sm font-semibold text-[#f1f5f9] text-right tabular-nums">
                  {sig?.composite_score != null ? sig.composite_score.toFixed(0) : '--'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Dashboard
   ═══════════════════════════════════════════════════════════════ */
export default function Dashboard() {
  const { selectedStock, portfolio, addToPortfolio } = useAppStore();
  const [signal, setSignal] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [portfolioSignals, setPortfolioSignals] = useState({});
  const [marketData, setMarketData] = useState(null);
  const [topMovers, setTopMovers] = useState(null);

  const isInPortfolio = portfolio.some((p) => p.symbol === selectedStock);
  const stockInfo = NIFTY_50.find((s) => s.symbol === selectedStock);
  const companyName = stockInfo?.name ?? selectedStock;
  const sector = SECTOR_MAP[selectedStock] ?? '';

  // Fetch market overview
  useEffect(() => {
    axios
      .get(`${API_BASE}/market/overview`)
      .then((res) => setMarketData(res.data))
      .catch(() => {
        // Silently fail -- market pulse strip just won't render
      });
  }, []);

  // Fetch top movers when portfolio is empty
  useEffect(() => {
    if (portfolio.length > 0) return;

    // Fetch signals for a handful of NIFTY 50 stocks to determine movers
    const sampleSymbols = NIFTY_50.slice(0, 20).map((s) => s.symbol);
    const requests = sampleSymbols.map((sym) =>
      axios
        .get(`${API_BASE}/stocks/${sym}/signal`)
        .then((res) => ({ symbol: sym, ...res.data }))
        .catch(() => null)
    );

    Promise.all(requests).then((results) => {
      const valid = results.filter(Boolean).filter((r) => r.change_pct != null);
      const sorted = [...valid].sort((a, b) => (b.change_pct ?? 0) - (a.change_pct ?? 0));
      setTopMovers({
        gainers: sorted.filter((s) => s.change_pct >= 0).slice(0, 5),
        losers: sorted.filter((s) => s.change_pct < 0).slice(-5).reverse(),
      });
    });
  }, [portfolio.length]);

  // Fetch selected stock signal
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    axios
      .get(`${API_BASE}/stocks/${selectedStock}/signal`)
      .then((res) => {
        if (!cancelled) {
          setSignal(res.data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.response?.data?.detail || 'Failed to fetch signal data');
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [selectedStock]);

  // Fetch portfolio signals
  useEffect(() => {
    if (portfolio.length === 0) return;

    const requests = portfolio.map((p) =>
      axios
        .get(`${API_BASE}/stocks/${p.symbol}/signal`)
        .then((res) => ({ symbol: p.symbol, data: res.data }))
        .catch(() => ({ symbol: p.symbol, data: null }))
    );

    Promise.all(requests).then((results) => {
      const map = {};
      results.forEach(({ symbol, data }) => {
        if (data) map[symbol] = data;
      });
      setPortfolioSignals(map);
    });
  }, [portfolio]);

  const compositeScore = signal?.composite_score ?? 0;
  const changePct = signal?.change_pct ?? 0;
  const isPositive = changePct >= 0;
  const changeAbs = signal?.price != null && signal?.prev_close != null
    ? signal.price - signal.prev_close
    : null;

  const macdDirection = signal?.macd_signal ?? '--';
  const macdLabel = macdDirection !== '--'
    ? macdDirection.charAt(0).toUpperCase() + macdDirection.slice(1)
    : '--';

  // Breakdown data
  const breakdown = signal?.breakdown ?? {};
  const factorLabels = {
    trend_score: { label: 'Trend', tooltip: INDICATOR_TOOLTIPS['Trend Score'] },
    momentum_score: { label: 'Momentum', tooltip: INDICATOR_TOOLTIPS['Momentum Score'] },
    volatility_score: { label: 'Volatility', tooltip: INDICATOR_TOOLTIPS['Volatility Score'] },
    volume_score: { label: 'Volume', tooltip: INDICATOR_TOOLTIPS['Volume Score'] },
    pattern_score: { label: 'Pattern', tooltip: INDICATOR_TOOLTIPS['Pattern Score'] },
    statistical_score: { label: 'Statistical', tooltip: INDICATOR_TOOLTIPS['Statistical Score'] },
    sentiment_score: { label: 'Sentiment', tooltip: null },
    earnings_score: { label: 'Earnings', tooltip: null },
  };

  const factors = Object.entries(factorLabels)
    .filter(([key]) => breakdown[key] != null && !(key === 'sentiment_score' && breakdown[key] === 0) && !(key === 'earnings_score' && breakdown[key] === 0))
    .map(([key, { label, tooltip }]) => ({ label, value: breakdown[key], tooltip }));

  return (
    <div className="space-y-5 max-w-[1400px] mx-auto">

      {/* ── 1. Header Bar ────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-4 anim-fade-up">
        <h1 className="text-xl font-semibold text-white">Overview</h1>
        <div className="flex items-center gap-3">
          <StockSelector />
          {!isInPortfolio && (
            <button
              onClick={() => addToPortfolio(selectedStock)}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-medium
                         bg-[#3b82f6]/10 text-[#3b82f6] border border-[#3b82f6]/20
                         hover:bg-[#3b82f6]/20 hover:border-[#3b82f6]/40 transition-all"
            >
              <Plus className="w-4 h-4" />
              <span className="hidden sm:inline">Add to Portfolio</span>
            </button>
          )}
        </div>
      </div>

      {/* ── Error ────────────────────────────────────────────── */}
      {error && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-[#ef4444]/5 border border-[#ef4444]/10">
          <AlertTriangle className="w-4 h-4 text-[#ef4444] flex-shrink-0" />
          <p className="text-sm text-[#ef4444]">{error}</p>
        </div>
      )}

      {/* ── A. Market Pulse Strip ────────────────────────────── */}
      <MarketPulseStrip marketData={marketData} />

      {/* ── 2. Stock Summary Card (Hero) ─────────────────────── */}
      <div
        className="anim-fade-up rounded-xl border border-[#1f2937] overflow-hidden hover:border-[#374151] transition-colors"
        style={{
          background: '#111827',
          animationDelay: '100ms',
        }}
      >
        {/* Gradient top border */}
        <div
          className="h-[2px]"
          style={{
            background: loading
              ? '#1f2937'
              : `linear-gradient(90deg, ${signalBorderColor(compositeScore)}40, ${signalBorderColor(compositeScore)}, ${signalBorderColor(compositeScore)}40)`,
          }}
        />

        {loading ? (
          <div className="p-6 md:p-8">
            <div className="flex flex-col md:flex-row md:items-center gap-8">
              <div className="space-y-3 flex-1">
                <div className="animate-pulse bg-[#1f2937] rounded h-6 w-40" />
                <div className="animate-pulse bg-[#1f2937] rounded h-12 w-56" />
                <div className="animate-pulse bg-[#1f2937] rounded h-4 w-32" />
              </div>
              <div className="flex gap-3">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="animate-pulse bg-[#1f2937] rounded-lg h-20 w-20" />
                ))}
              </div>
              <div className="animate-pulse bg-[#1f2937] rounded-full h-[140px] w-[140px]" />
            </div>
          </div>
        ) : (
          <div className="p-6 md:p-8">
            {/* Top row: Symbol + Signal Badge */}
            <div className="flex items-start justify-between mb-3">
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <h2 className="text-2xl font-bold text-white tracking-tight">
                    {selectedStock}
                  </h2>
                </div>
                <p className="text-sm text-[#94a3b8]">
                  {companyName}
                  {sector && <span className="text-[#64748b]"> &middot; {sector}</span>}
                </p>
              </div>
              <div className="flex items-center gap-2.5">
                <SignalBadge score={compositeScore} size="md" />
                <span className={`font-mono text-sm font-bold tabular-nums ${compositeScore >= 30 ? 'text-[#22c55e]' : compositeScore <= -30 ? 'text-[#ef4444]' : 'text-[#f59e0b]'}`}>
                  {compositeScore > 0 ? '+' : ''}{compositeScore.toFixed(0)}
                </span>
              </div>
            </div>

            {/* Price row */}
            <div className="flex items-baseline gap-4 mb-5">
              <span className="font-mono text-4xl md:text-5xl font-bold text-white tracking-tight tabular-nums">
                {signal?.price != null ? fmt(signal.price) : '--'}
              </span>
              <span
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md font-mono text-sm font-semibold tabular-nums ${
                  isPositive
                    ? 'bg-[#22c55e]/10 text-[#22c55e]'
                    : 'bg-[#ef4444]/10 text-[#ef4444]'
                }`}
              >
                {isPositive ? '\u25B2' : '\u25BC'} {isPositive ? '+' : ''}{changePct.toFixed(2)}%
                {changeAbs != null && (
                  <span className="opacity-70 ml-1">
                    ({changeAbs >= 0 ? '+' : ''}{fmt(Math.abs(changeAbs)).replace('\u20B9', '\u20B9')})
                  </span>
                )}
              </span>
            </div>

            {/* ScoreGauge row */}
            <div className="flex flex-col lg:flex-row lg:items-end gap-4">
              <div className="flex-1" />
              <div className="flex-shrink-0 anim-fade-up" style={{ animationDelay: '500ms' }}>
                <ScoreGauge score={compositeScore} size={140} />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── B. Quick Indicators Grid ─────────────────────────── */}
      {!loading && signal && <QuickIndicatorsGrid signal={signal} />}

      {/* ── D. Key Fundamentals Strip ────────────────────────── */}
      {!loading && signal && <FundamentalsStrip signal={signal} />}

      {/* ── C. Signal Factors Breakdown (compact) ────────────── */}
      {!loading && factors.length > 0 && (
        <div
          className="anim-fade-up rounded-xl border border-[#1f2937] bg-[#111827] px-5 py-4 hover:border-[#374151] transition-colors"
          style={{ animationDelay: '280ms' }}
        >
          <h3 className="text-[10px] uppercase tracking-wider text-[#64748b] font-semibold mb-2">Signal Factors</h3>
          <div className="space-y-0">
            {factors.map((f) => (
              <CompactFactorBar key={f.label} label={f.label} value={f.value} tooltip={f.tooltip} />
            ))}
          </div>
        </div>
      )}

      {/* ── E. Action Panel ──────────────────────────────────── */}
      <div className="anim-fade-up" style={{ animationDelay: '320ms' }}>
        <ActionPanel symbol={selectedStock} />
      </div>

      {/* ── F. Portfolio / Top Movers Table ───────────────────── */}
      <div className="anim-fade-up" style={{ animationDelay: '380ms' }}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-[#f1f5f9]">
            {portfolio.length > 0 ? 'Portfolio' : 'Top Movers Today'}
          </h3>
          {portfolio.length > 0 && (
            <span className="text-xs text-[#64748b]">
              {portfolio.length} stock{portfolio.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        <div className="rounded-xl border border-[#1f2937] bg-[#111827] p-4 hover:border-[#374151] transition-colors">
          <PortfolioTable portfolio={portfolio} signals={portfolioSignals} topMovers={topMovers} />
        </div>
      </div>
    </div>
  );
}
