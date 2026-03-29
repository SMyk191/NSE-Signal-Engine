import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, ComposedChart,
} from 'recharts';
import {
  BarChart3, CheckCircle2, XCircle, TrendingUp, TrendingDown,
  Loader2, AlertTriangle, Shield,
} from 'lucide-react';
import StockSelector from '../components/StockSelector';
import useAppStore from '../stores/appStore';
import { fetchEarnings } from '../services/api';

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#111827] border border-[#1f2937] rounded-lg px-3 py-2 shadow-xl">
      <p className="text-[10px] text-[#64748b] font-sans">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="text-xs price-font" style={{ color: p.color }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(2) : p.value ?? 'N/A'}
        </p>
      ))}
    </div>
  );
}

function MetricCard({ label, value, suffix = '', color, subtext }) {
  return (
    <div className="bg-[#0c1220] border border-[#1f2937] rounded-xl p-4">
      <span className="text-[10px] font-sans text-[#64748b] uppercase tracking-wider">
        {label}
      </span>
      <div className="mt-1 flex items-baseline gap-1">
        <span className={`text-xl font-bold price-font ${color || 'text-[#f1f5f9]'}`}>
          {value ?? 'N/A'}
        </span>
        {suffix && (
          <span className="text-xs price-font text-[#64748b]">{suffix}</span>
        )}
      </div>
      {subtext && (
        <span className="text-[10px] font-sans text-[#64748b] mt-1 block">{subtext}</span>
      )}
    </div>
  );
}

function getRatioColor(key, value) {
  if (value === null || value === undefined) return 'text-[#64748b]';
  const rules = {
    pe_ratio: (v) => v > 0 && v < 25 ? 'text-[#22c55e]' : v > 40 ? 'text-[#ef4444]' : 'text-[#f59e0b]',
    pb_ratio: (v) => v < 3 ? 'text-[#22c55e]' : v > 5 ? 'text-[#ef4444]' : 'text-[#f59e0b]',
    peg_ratio: (v) => v > 0 && v < 1.5 ? 'text-[#22c55e]' : v > 2.5 ? 'text-[#ef4444]' : 'text-[#f59e0b]',
    forward_pe: (v) => v > 0 && v < 25 ? 'text-[#22c55e]' : v > 40 ? 'text-[#ef4444]' : 'text-[#f59e0b]',
    debt_equity: (v) => v < 0.5 ? 'text-[#22c55e]' : v > 1.5 ? 'text-[#ef4444]' : 'text-[#f59e0b]',
    current_ratio: (v) => v > 1.5 ? 'text-[#22c55e]' : v < 1 ? 'text-[#ef4444]' : 'text-[#f59e0b]',
    roe: (v) => v > 15 ? 'text-[#22c55e]' : v < 8 ? 'text-[#ef4444]' : 'text-[#f59e0b]',
    roa: (v) => v > 10 ? 'text-[#22c55e]' : v < 3 ? 'text-[#ef4444]' : 'text-[#f59e0b]',
    roce: (v) => v > 15 ? 'text-[#22c55e]' : v < 8 ? 'text-[#ef4444]' : 'text-[#f59e0b]',
    dividend_yield: (v) => v > 2 ? 'text-[#22c55e]' : v < 0.5 ? 'text-[#f59e0b]' : 'text-[#f1f5f9]',
  };
  return (rules[key] || (() => 'text-[#f1f5f9]'))(value);
}

function AltmanZScore({ score }) {
  if (score === null || score === undefined) return null;
  let zone, zoneColor, zoneBg, borderCol;
  if (score > 2.99) {
    zone = 'Safe Zone';
    zoneColor = 'text-[#22c55e]';
    zoneBg = 'bg-[#22c55e]/10';
    borderCol = '#22c55e33';
  } else if (score > 1.81) {
    zone = 'Gray Zone';
    zoneColor = 'text-[#f59e0b]';
    zoneBg = 'bg-[#f59e0b]/10';
    borderCol = '#f59e0b33';
  } else {
    zone = 'Distress Zone';
    zoneColor = 'text-[#ef4444]';
    zoneBg = 'bg-[#ef4444]/10';
    borderCol = '#ef444433';
  }

  return (
    <div className={`card ${zoneBg} rounded-xl p-6`} style={{ borderColor: borderCol }}>
      <h3 className="text-xs font-sans text-[#94a3b8] uppercase tracking-wider mb-3 font-medium">
        Altman Z-Score
      </h3>
      <div className="flex items-center gap-4">
        <span className={`text-4xl font-bold price-font ${zoneColor}`}>
          {score.toFixed(2)}
        </span>
        <div>
          <span className={`text-sm font-sans font-semibold ${zoneColor}`}>{zone}</span>
          <div className="text-[10px] font-sans text-[#64748b] mt-1">
            {score > 2.99
              ? 'Low bankruptcy probability'
              : score > 1.81
                ? 'Moderate risk - needs monitoring'
                : 'High financial distress risk'}
          </div>
        </div>
      </div>
      <div className="mt-4">
        <div className="flex justify-between text-[9px] font-sans text-[#64748b] mb-1">
          <span>Distress (&lt;1.81)</span>
          <span>Gray (1.81-2.99)</span>
          <span>Safe (&gt;2.99)</span>
        </div>
        <div className="h-2 rounded-full bg-[#1f2937] relative overflow-hidden">
          <div className="absolute inset-0 flex">
            <div className="w-[30%] bg-[#ef4444]/40" />
            <div className="w-[20%] bg-[#f59e0b]/40" />
            <div className="w-[50%] bg-[#22c55e]/40" />
          </div>
          <div
            className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full border-2 shadow-md"
            style={{
              left: `calc(${Math.min(Math.max((score / 5) * 100, 2), 98)}% - 6px)`,
              borderColor: score > 2.99 ? '#22c55e' : score > 1.81 ? '#f59e0b' : '#ef4444',
            }}
          />
        </div>
      </div>
    </div>
  );
}

function PiotroskiScore({ data }) {
  if (!data) return null;
  const score = data.f_score ?? data.score ?? 0;
  const criteriaObj = data.criteria || {};
  // criteria can be an object { name: bool } or array [{ name, pass }]
  const criteriaList = Array.isArray(criteriaObj)
    ? criteriaObj
    : Object.entries(criteriaObj).map(([name, pass]) => ({ name, pass }));

  let scoreColor = 'text-[#22c55e]';
  if (score <= 3) scoreColor = 'text-[#ef4444]';
  else if (score <= 6) scoreColor = 'text-[#f59e0b]';

  return (
    <div className="card rounded-xl p-6">
      <h3 className="text-xs font-sans text-[#94a3b8] uppercase tracking-wider mb-3 font-medium">
        Piotroski F-Score
      </h3>
      <div className="flex items-center gap-4 mb-4">
        <span className={`text-4xl font-bold price-font ${scoreColor}`}>{score}</span>
        <span className="text-sm price-font text-[#64748b]">/ 9</span>
        <div className="flex-1">
          <div className="flex gap-1">
            {Array.from({ length: 9 }, (_, i) => (
              <div
                key={i}
                className={`h-3 flex-1 rounded-sm ${
                  i < score
                    ? score >= 7 ? 'bg-[#22c55e]' : score >= 4 ? 'bg-[#f59e0b]' : 'bg-[#ef4444]'
                    : 'bg-[#1f2937]'
                }`}
              />
            ))}
          </div>
        </div>
      </div>
      {criteriaList.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {criteriaList.map((c, i) => (
            <div key={i} className="flex items-center gap-2">
              {c.pass ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-[#22c55e] flex-shrink-0" />
              ) : (
                <XCircle className="w-3.5 h-3.5 text-[#ef4444] flex-shrink-0" />
              )}
              <span className="text-[10px] font-sans text-[#94a3b8] truncate">
                {c.name || c.label || `Criterion ${i + 1}`}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function EarningsPredictor() {
  const { symbol: urlSymbol } = useParams();
  const { selectedStock, setSelectedStock } = useAppStore();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (urlSymbol) setSelectedStock(urlSymbol.toUpperCase());
  }, [urlSymbol, setSelectedStock]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetchEarnings(selectedStock);
        if (!cancelled) setData(res);
      } catch (err) {
        if (!cancelled) setError(err.response?.data?.detail || err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [selectedStock]);

  // Prepare chart data
  const earningsHistory = data?.earnings_history || [];
  const marginData = data?.margin_analysis;
  const zScore = data?.altman_z_score;
  const piotroski = data?.piotroski_f_score;
  const accrual = data?.accrual_ratio;
  const keyRatiosData = data?.key_ratios || {};

  // BUG FIX #1: Margins come as percentages already (25.09 = 25.09%).
  // Do NOT multiply by 100 again.
  const marginChartData = marginData?.history
    ? marginData.history.map((m) => ({
        period: m.period || m.quarter,
        gross: m.gross_margin != null ? parseFloat(Number(m.gross_margin).toFixed(1)) : null,
        operating: m.operating_margin != null ? parseFloat(Number(m.operating_margin).toFixed(1)) : null,
        net: m.net_margin != null ? parseFloat(Number(m.net_margin).toFixed(1)) : null,
      }))
    : [];

  // Build EPS chart data from earnings history
  const revenueChartData = earningsHistory.slice().reverse().map((e, i) => ({
    quarter: e.quarter?.substring(0, 10) || `Q${i + 1}`,
    eps: e.actual,
    estimate: e.estimate,
    surprise_pct: e.surprise_pct,
  }));

  // BUG FIX #2: Read from data.key_ratios with proper formatting
  // P/E, P/B, PEG, Forward P/E: as-is with 2dp + "x"
  // ROE, ROA: decimal -> * 100, show "%"
  // Debt/Equity: as-is 2dp
  // Current Ratio: as-is 2dp + "x"
  // ROCE: percentage if available
  // Dividend Yield: decimal -> * 100, show "%"
  const formatRatio = (val, multiplier = 1) => {
    if (val == null || isNaN(val)) return null;
    // If multiplier is 100 (decimal->pct) but value > 1, it's already a percentage
    if (multiplier === 100 && Math.abs(val) > 1) return parseFloat(Number(val).toFixed(2));
    return parseFloat((val * multiplier).toFixed(2));
  };

  const keyRatios = [
    { key: 'pe_ratio', label: 'P/E', value: formatRatio(keyRatiosData.pe), suffix: 'x' },
    { key: 'pb_ratio', label: 'P/B', value: formatRatio(keyRatiosData.pb), suffix: 'x' },
    { key: 'peg_ratio', label: 'PEG', value: formatRatio(keyRatiosData.peg), suffix: 'x' },
    { key: 'forward_pe', label: 'Forward P/E', value: formatRatio(keyRatiosData.forward_pe), suffix: 'x' },
    { key: 'roe', label: 'ROE', value: formatRatio(keyRatiosData.roe, 100), suffix: '%' },
    { key: 'roa', label: 'ROA', value: formatRatio(keyRatiosData.roa, 100), suffix: '%' },
    { key: 'roce', label: 'ROCE', value: formatRatio(keyRatiosData.roce, keyRatiosData.roce != null && Math.abs(keyRatiosData.roce) < 1 ? 100 : 1), suffix: '%' },
    { key: 'debt_equity', label: 'Debt/Equity', value: formatRatio(keyRatiosData.debt_equity), suffix: '' },
    { key: 'current_ratio', label: 'Current Ratio', value: formatRatio(keyRatiosData.current_ratio), suffix: 'x' },
    { key: 'dividend_yield', label: 'Div Yield', value: formatRatio(keyRatiosData.dividend_yield, 100), suffix: '%' },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between animate-fade-up">
        <div className="flex items-center gap-4">
          <BarChart3 className="w-6 h-6 text-[#3b82f6]" />
          <div>
            <h1 className="text-xl font-sans font-bold text-[#f1f5f9]">
              Earnings Predictor
            </h1>
            <p className="text-xs font-sans text-[#64748b]">
              Fundamentals, margins, financial health scores
            </p>
          </div>
        </div>
        <StockSelector />
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 text-[#3b82f6] animate-spin" />
          <span className="ml-3 font-sans text-sm text-[#94a3b8]">
            Loading earnings for {selectedStock}...
          </span>
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="bg-[#ef4444]/10 border border-[#ef4444]/30 rounded-xl p-4 animate-fade-up">
          <p className="text-[#ef4444] font-sans text-sm">{error}</p>
        </div>
      )}

      {data && !loading && (
        <div className="space-y-6">
          {/* Earnings History Table */}
          <div className="card rounded-xl p-6 animate-fade-up stagger-1">
            <h3 className="text-xs font-sans text-[#94a3b8] uppercase tracking-wider mb-4 font-medium">
              Earnings History (Last 8 Quarters)
            </h3>
            {earningsHistory.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-[#1f2937]">
                      {['Quarter', 'EPS Estimate', 'EPS Actual', 'Surprise %', ''].map((h) => (
                        <th
                          key={h}
                          className="text-left text-[10px] font-sans text-[#64748b] uppercase tracking-wider pb-3 px-3 font-medium"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {earningsHistory.map((row, i) => {
                      const beat = row.surprise != null && row.surprise > 0;
                      const miss = row.surprise != null && row.surprise < 0;
                      return (
                        <tr key={i} className="border-b border-[#1f2937]/50 hover:bg-[#1a2332] transition-smooth">
                          <td className="py-2.5 px-3 text-xs font-sans text-[#94a3b8]">
                            {row.quarter?.substring(0, 10)}
                          </td>
                          <td className="py-2.5 px-3 text-xs price-font text-[#94a3b8]">
                            {row.estimate?.toFixed(2) ?? '-'}
                          </td>
                          <td className="py-2.5 px-3 text-xs price-font text-[#f1f5f9] font-bold">
                            {row.actual?.toFixed(2) ?? '-'}
                          </td>
                          <td className={`py-2.5 px-3 text-xs price-font font-bold ${
                            beat ? 'text-[#22c55e]' : miss ? 'text-[#ef4444]' : 'text-[#64748b]'
                          }`}>
                            {row.surprise_pct != null ? `${row.surprise_pct > 0 ? '+' : ''}${row.surprise_pct.toFixed(1)}%` : '-'}
                          </td>
                          <td className="py-2.5 px-3">
                            {beat ? (
                              <CheckCircle2 className="w-4 h-4 text-[#22c55e]" />
                            ) : miss ? (
                              <XCircle className="w-4 h-4 text-[#ef4444]" />
                            ) : (
                              <span className="text-[#1f2937]">-</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-[#64748b] font-sans text-sm text-center py-4">
                No earnings history available
              </p>
            )}
          </div>

          {/* Revenue / EPS Chart */}
          {revenueChartData.length > 0 && (
            <div className="card rounded-xl p-6 animate-fade-up stagger-2">
              <h3 className="text-xs font-sans text-[#94a3b8] uppercase tracking-wider mb-4 font-medium">
                EPS Trend (Actual vs Estimate)
              </h3>
              <ResponsiveContainer width="100%" height={260}>
                <ComposedChart data={revenueChartData}>
                  <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="quarter"
                    tick={{ fontSize: 9, fill: '#64748b', fontFamily: 'Inter, sans-serif' }}
                    axisLine={{ stroke: '#1f2937' }}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: '#64748b', fontFamily: 'JetBrains Mono, monospace' }}
                    axisLine={{ stroke: '#1f2937' }}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend
                    wrapperStyle={{ fontSize: '10px', fontFamily: 'Inter, sans-serif' }}
                  />
                  <Bar dataKey="eps" name="EPS Actual" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="estimate" name="EPS Estimate" fill="#475569" radius={[4, 4, 0, 0]} />
                  <Line
                    type="monotone"
                    dataKey="surprise_pct"
                    name="Surprise %"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    dot={{ fill: '#f59e0b', r: 3 }}
                    yAxisId={0}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Margin Trends */}
          {marginChartData.length > 0 && (
            <div className="card rounded-xl p-6 animate-fade-up stagger-3">
              <h3 className="text-xs font-sans text-[#94a3b8] uppercase tracking-wider mb-4 font-medium">
                Margin Trends
              </h3>
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={marginChartData}>
                  <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="period"
                    tick={{ fontSize: 9, fill: '#64748b', fontFamily: 'Inter, sans-serif' }}
                    axisLine={{ stroke: '#1f2937' }}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: '#64748b', fontFamily: 'JetBrains Mono, monospace' }}
                    axisLine={{ stroke: '#1f2937' }}
                    tickFormatter={(v) => `${v}%`}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize: '10px', fontFamily: 'Inter, sans-serif' }} />
                  <Line type="monotone" dataKey="gross" name="Gross Margin %" stroke="#22c55e" strokeWidth={2} dot={{ fill: '#22c55e', r: 3 }} />
                  <Line type="monotone" dataKey="operating" name="Operating Margin %" stroke="#3b82f6" strokeWidth={2} dot={{ fill: '#3b82f6', r: 3 }} />
                  <Line type="monotone" dataKey="net" name="Net Margin %" stroke="#8b5cf6" strokeWidth={2} dot={{ fill: '#8b5cf6', r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Current Margins - BUG FIX #1: no * 100, values are already percentages */}
          {marginData && (
            <div className="card rounded-xl p-6 animate-fade-up stagger-4">
              <h3 className="text-xs font-sans text-[#94a3b8] uppercase tracking-wider mb-4 font-medium">
                Current Margins
              </h3>
              <div className="grid grid-cols-3 gap-4">
                <MetricCard
                  label="Gross Margin"
                  value={marginData.gross_margin != null ? Number(marginData.gross_margin).toFixed(1) : null}
                  suffix="%"
                  color={marginData.gross_margin > 30 ? 'text-[#22c55e]' : 'text-[#f59e0b]'}
                />
                <MetricCard
                  label="Operating Margin"
                  value={marginData.operating_margin != null ? Number(marginData.operating_margin).toFixed(1) : null}
                  suffix="%"
                  color={marginData.operating_margin > 15 ? 'text-[#22c55e]' : 'text-[#f59e0b]'}
                />
                <MetricCard
                  label="Net Margin"
                  value={marginData.net_margin != null ? Number(marginData.net_margin).toFixed(1) : null}
                  suffix="%"
                  color={marginData.net_margin > 10 ? 'text-[#22c55e]' : 'text-[#f59e0b]'}
                />
              </div>
            </div>
          )}

          {/* Key Ratios Dashboard - BUG FIX #2: reads from data.key_ratios */}
          <div className="card rounded-xl p-6 animate-fade-up">
            <h3 className="text-xs font-sans text-[#94a3b8] uppercase tracking-wider mb-4 font-medium">
              Key Ratios
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
              {keyRatios.map((r) => (
                <MetricCard
                  key={r.key}
                  label={r.label}
                  value={r.value != null ? r.value.toFixed(2) : null}
                  suffix={r.suffix}
                  color={getRatioColor(r.key, r.value)}
                />
              ))}
            </div>
          </div>

          {/* Altman Z-Score + Piotroski - BUG FIX #3: read f_score correctly */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-fade-up">
            {zScore != null && (
              <AltmanZScore score={typeof zScore === 'object' ? (zScore.score ?? zScore.z_score) : zScore} />
            )}
            <PiotroskiScore data={piotroski} />
          </div>

          {/* Earnings Quality */}
          {accrual != null && (
            <div className="card rounded-xl p-6 animate-fade-up">
              <h3 className="text-xs font-sans text-[#94a3b8] uppercase tracking-wider mb-3 font-medium">
                Earnings Quality
              </h3>
              <div className="flex items-center gap-4">
                <span className="text-[10px] font-sans text-[#64748b] uppercase">Accrual Ratio</span>
                <span className={`text-2xl font-bold price-font ${
                  Math.abs(accrual) < 0.05 ? 'text-[#22c55e]' : Math.abs(accrual) > 0.1 ? 'text-[#ef4444]' : 'text-[#f59e0b]'
                }`}>
                  {(typeof accrual === 'number' ? accrual : 0).toFixed(4)}
                </span>
                <span className="text-xs font-sans text-[#64748b]">
                  {Math.abs(accrual) < 0.05
                    ? '(High quality - cash-backed earnings)'
                    : Math.abs(accrual) > 0.1
                      ? '(Low quality - accrual-heavy)'
                      : '(Moderate quality)'}
                </span>
              </div>
            </div>
          )}

          {/* Peer Comparison */}
          {data?.peers && data.peers.length > 0 && (
            <div className="card rounded-xl p-6 animate-fade-up">
              <h3 className="text-xs font-sans text-[#94a3b8] uppercase tracking-wider mb-4 font-medium">
                Peer Comparison
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-[#1f2937]">
                      {['Symbol', 'P/E', 'P/B', 'ROE', 'Debt/Equity', 'Margin'].map((h) => (
                        <th key={h} className="text-left text-[10px] font-sans text-[#64748b] uppercase tracking-wider pb-3 px-3 font-medium">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.peers.map((peer, i) => (
                      <tr key={i} className="border-b border-[#1f2937]/50 hover:bg-[#1a2332] transition-smooth">
                        <td className="py-2.5 px-3 text-xs font-sans text-[#3b82f6] font-bold">{peer.symbol}</td>
                        <td className="py-2.5 px-3 text-xs price-font text-[#94a3b8]">{peer.pe?.toFixed(1) ?? '-'}</td>
                        <td className="py-2.5 px-3 text-xs price-font text-[#94a3b8]">{peer.pb?.toFixed(1) ?? '-'}</td>
                        <td className="py-2.5 px-3 text-xs price-font text-[#94a3b8]">{peer.roe != null ? `${(peer.roe * 100).toFixed(1)}%` : '-'}</td>
                        <td className="py-2.5 px-3 text-xs price-font text-[#94a3b8]">{peer.debt_equity?.toFixed(2) ?? '-'}</td>
                        <td className="py-2.5 px-3 text-xs price-font text-[#94a3b8]">{peer.net_margin != null ? `${(peer.net_margin * 100).toFixed(1)}%` : '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
