import { useState, useEffect, useCallback } from 'react';
import {
  PieChart, Pie, Cell, ScatterChart, Scatter, AreaChart, Area,
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts';
import {
  Shield, Plus, Trash2, Loader2, Play, DollarSign,
  TrendingUp, AlertTriangle,
} from 'lucide-react';
import { NIFTY_50 } from '../components/StockSelector';
import useAppStore from '../stores/appStore';
import { analyzePortfolio, fetchEfficientFrontier, fetchMonteCarlo } from '../services/api';

const PIE_COLORS = [
  '#3b82f6', '#22c55e', '#8b5cf6', '#f59e0b', '#ef4444',
  '#ec4899', '#6366f1', '#14b8a6', '#f97316', '#10b981',
];

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#111827] border border-[#1f2937] rounded px-3 py-2 shadow-xl">
      <p className="text-[10px] font-mono text-[#64748b]">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="text-xs font-mono" style={{ color: p.color || '#e2e8f0' }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(4) : p.value}
        </p>
      ))}
    </div>
  );
}

function MetricCard({ label, value, suffix = '', color, icon: Icon }) {
  return (
    <div className="bg-[#0c1220] border border-[#1f2937] rounded-lg p-4">
      <div className="flex items-center gap-2 mb-1">
        {Icon && <Icon className="w-3 h-3 text-[#64748b]" />}
        <span className="text-[10px] text-[#64748b] uppercase tracking-wider">{label}</span>
      </div>
      <span className={`text-lg font-bold font-mono ${color || 'text-[#f1f5f9]'}`}>
        {value ?? 'N/A'}
      </span>
      {suffix && <span className="text-xs font-mono text-[#94a3b8] ml-1">{suffix}</span>}
    </div>
  );
}

function CorrelationHeatmap({ matrix, stocks }) {
  if (!matrix || !stocks || stocks.length === 0) return null;

  const getColor = (val) => {
    if (val === null || val === undefined) return '#1f2937';
    const abs = Math.abs(val);
    if (abs > 0.7) return val > 0 ? '#ef4444' : '#3b82f6';
    if (abs > 0.4) return val > 0 ? '#f59e0b' : '#3b82f6';
    return '#22c55e';
  };

  return (
    <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
      <h3 className="text-xs text-[#64748b] uppercase tracking-wider mb-4">
        Correlation Matrix
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr>
              <th className="text-[10px] font-mono text-[#64748b] p-2" />
              {stocks.map((s) => (
                <th key={s} className="text-[10px] font-mono text-[#94a3b8] p-2 text-center">
                  {s}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {stocks.map((row) => (
              <tr key={row}>
                <td className="text-[10px] font-mono text-[#94a3b8] p-2 text-right font-bold">
                  {row}
                </td>
                {stocks.map((col) => {
                  const val = matrix[row]?.[col] ?? matrix[col]?.[row] ?? null;
                  return (
                    <td key={col} className="p-1 text-center">
                      <div
                        className="rounded text-[10px] font-mono font-bold py-2 px-1 mx-auto min-w-[48px]"
                        style={{
                          backgroundColor: `${getColor(val)}20`,
                          color: getColor(val),
                        }}
                      >
                        {val != null ? val.toFixed(2) : '-'}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-center gap-4 mt-4 text-[9px] font-mono text-[#64748b]">
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-500/30 inline-block" /> Low (&lt;0.4)</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-amber-500/30 inline-block" /> Medium (0.4-0.7)</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-500/30 inline-block" /> High (&gt;0.7)</span>
      </div>
    </div>
  );
}

export default function PortfolioRisk() {
  const { portfolio, addToPortfolio, removeFromPortfolio, updateWeights } = useAppStore();
  const [capital, setCapital] = useState(100000);
  const [addSymbol, setAddSymbol] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [efData, setEfData] = useState(null);
  const [mcData, setMcData] = useState(null);

  const totalWeight = portfolio.reduce((sum, p) => sum + (p.weight || 0), 0);

  const handleAdd = () => {
    const sym = addSymbol.trim().toUpperCase();
    if (sym && NIFTY_50.some((s) => s.symbol === sym)) {
      addToPortfolio(sym, 0);
      setAddSymbol('');
    }
  };

  const handleEqualWeight = () => {
    if (portfolio.length === 0) return;
    const w = parseFloat((1 / portfolio.length).toFixed(4));
    portfolio.forEach((p) => updateWeights(p.symbol, w));
  };

  const handleAnalyze = useCallback(async () => {
    if (portfolio.length === 0) return;
    const stocks = portfolio.map((p) => p.symbol);
    const weights = portfolio.map((p) => p.weight);

    if (Math.abs(totalWeight - 1) > 0.05) {
      setError('Weights must sum to approximately 1.0');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    setEfData(null);
    setMcData(null);

    try {
      const [portfolioRes, efRes, mcRes] = await Promise.allSettled([
        analyzePortfolio(stocks, weights),
        fetchEfficientFrontier(),
        fetchMonteCarlo(),
      ]);

      if (portfolioRes.status === 'fulfilled') setResult(portfolioRes.value);
      else setError(portfolioRes.reason?.response?.data?.detail || portfolioRes.reason?.message);

      if (efRes.status === 'fulfilled') setEfData(efRes.value);
      if (mcRes.status === 'fulfilled') setMcData(mcRes.value);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  }, [portfolio, totalWeight]);

  // Pie chart data
  const pieData = portfolio
    .filter((p) => p.weight > 0)
    .map((p) => ({ name: p.symbol, value: parseFloat((p.weight * 100).toFixed(1)) }));

  // Position sizing from result
  const stockSummaries = result?.stock_summaries || [];

  // VaR data
  const varData = result?.var;

  // Performance
  const perf = result?.performance || {};

  // Correlation
  const corrMatrix = result?.correlation_matrix;

  // Monte Carlo paths
  const monteCarloChart = mcData?.monte_carlo?.percentile_paths;

  // Efficient frontier
  const efChartData = efData?.frontier_data
    ? efData.frontier_data.returns.map((r, i) => ({
        volatility: efData.frontier_data.volatilities[i],
        ret: r,
        sharpe: efData.frontier_data.sharpes[i],
      }))
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4 animate-fade-up">
        <Shield className="w-6 h-6 text-blue-500" />
        <div>
          <h1 className="text-xl font-bold text-[#f1f5f9]">Portfolio Risk</h1>
          <p className="text-xs text-[#64748b]">Build portfolio, analyze risk, optimize allocation</p>
        </div>
      </div>

      {/* Portfolio Builder */}
      <div className="bg-[#111827] border border-[#1f2937] rounded-xl p-6 animate-fade-up" style={{ animationDelay: '100ms' }}>
        <h3 className="text-xs text-[#64748b] uppercase tracking-wider mb-4">
          Portfolio Builder
        </h3>

        {/* Add stock + Capital */}
        <div className="flex flex-wrap items-end gap-4 mb-4">
          <div>
            <label className="text-[10px] text-[#64748b] uppercase block mb-1">Add Stock</label>
            <div className="flex gap-2">
              <select
                value={addSymbol}
                onChange={(e) => setAddSymbol(e.target.value)}
                className="bg-[#0c1220] border border-[#1f2937] rounded px-3 py-2 text-xs font-mono text-[#f1f5f9] w-48 focus:border-blue-500/40 outline-none"
              >
                <option value="">Select stock...</option>
                {NIFTY_50.filter((s) => !portfolio.some((p) => p.symbol === s.symbol)).map((s) => (
                  <option key={s.symbol} value={s.symbol}>{s.symbol} - {s.name}</option>
                ))}
              </select>
              <button
                onClick={handleAdd}
                disabled={!addSymbol}
                className="px-3 py-2 bg-blue-500/10 border border-blue-500/30 text-blue-400 rounded text-xs font-mono hover:bg-blue-500/20 transition-colors disabled:opacity-30"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
          </div>
          <div>
            <label className="text-[10px] text-[#64748b] uppercase block mb-1">Capital (INR)</label>
            <input
              type="number"
              value={capital}
              onChange={(e) => setCapital(Number(e.target.value))}
              className="bg-[#0c1220] border border-[#1f2937] rounded px-3 py-2 text-xs font-mono text-[#f1f5f9] w-40 focus:border-blue-500/40 outline-none"
            />
          </div>
          <button
            onClick={handleEqualWeight}
            className="px-3 py-2 bg-[#0c1220] border border-[#1f2937] text-[#94a3b8] rounded text-xs font-mono hover:border-[#64748b] transition-colors"
          >
            Equal Weight
          </button>
          <button
            onClick={handleAnalyze}
            disabled={portfolio.length === 0 || loading}
            className="px-4 py-2 bg-blue-500/20 border border-blue-500/40 text-blue-400 rounded text-xs font-mono font-bold hover:bg-blue-500/30 transition-colors disabled:opacity-30 flex items-center gap-2"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            Analyze Portfolio
          </button>
        </div>

        {/* Holdings table */}
        {portfolio.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#1f2937]">
                  {['Stock', 'Weight (%)', 'Allocation (INR)', ''].map((h) => (
                    <th key={h} className="text-left text-[10px] text-[#64748b] uppercase tracking-wider pb-2 px-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {portfolio.map((p) => (
                  <tr key={p.symbol} className="border-b border-[#1f2937]/50">
                    <td className="py-2 px-3 text-xs font-mono text-blue-400 font-bold">{p.symbol}</td>
                    <td className="py-2 px-3">
                      <input
                        type="number"
                        min="0"
                        max="100"
                        step="1"
                        value={parseFloat((p.weight * 100).toFixed(1))}
                        onChange={(e) => updateWeights(p.symbol, Number(e.target.value) / 100)}
                        className="bg-[#0c1220] border border-[#1f2937] rounded px-2 py-1 text-xs font-mono text-[#f1f5f9] w-20 focus:border-blue-500/40 outline-none"
                      />
                    </td>
                    <td className="py-2 px-3 text-xs font-mono text-[#94a3b8]">
                      {new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(capital * p.weight)}
                    </td>
                    <td className="py-2 px-3">
                      <button
                        onClick={() => removeFromPortfolio(p.symbol)}
                        className="text-[#64748b] hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex items-center gap-2 mt-2 px-3">
              <span className="text-[10px] font-mono text-[#64748b]">Total Weight:</span>
              <span className={`text-xs font-mono font-bold ${Math.abs(totalWeight - 1) < 0.05 ? 'text-emerald-400' : 'text-red-400'}`}>
                {(totalWeight * 100).toFixed(1)}%
              </span>
              {Math.abs(totalWeight - 1) > 0.05 && (
                <span className="text-[10px] font-mono text-red-400">(Must be ~100%)</span>
              )}
            </div>
          </div>
        ) : (
          <p className="text-[#64748b] text-sm text-center py-4">
            Add stocks to build your portfolio
          </p>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
          <p className="text-red-400 font-mono text-sm">{error}</p>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          <span className="ml-3 text-sm text-[#94a3b8]">Analyzing portfolio risk...</span>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <div className="space-y-6">
          {/* Pie Chart + Position Sizing */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Allocation Pie */}
            <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
              <h3 className="text-xs text-[#64748b] uppercase tracking-wider mb-4">
                Portfolio Composition
              </h3>
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={2}
                    dataKey="value"
                    label={({ name, value }) => `${name} ${value}%`}
                  >
                    {pieData.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(val) => `${val}%`}
                    contentStyle={{ backgroundColor: '#111827', border: '1px solid #1f2937', borderRadius: '8px', fontFamily: 'monospace', fontSize: '11px' }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Position Sizing */}
            <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
              <h3 className="text-xs text-[#64748b] uppercase tracking-wider mb-4">
                Position Sizing
              </h3>
              <div className="overflow-y-auto max-h-[280px]">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-[#1f2937]">
                      {['Stock', 'Weight', 'Ann. Return', 'Ann. Vol', 'Allocation'].map((h) => (
                        <th key={h} className="text-left text-[9px] font-mono text-[#64748b] uppercase pb-2 px-2">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {stockSummaries.map((s) => (
                      <tr key={s.symbol} className="border-b border-[#1f2937]/50">
                        <td className="py-2 px-2 text-xs font-mono text-blue-400 font-bold">{s.symbol}</td>
                        <td className="py-2 px-2 text-[10px] font-mono text-[#94a3b8]">{(s.weight * 100).toFixed(1)}%</td>
                        <td className={`py-2 px-2 text-[10px] font-mono font-bold ${s.annualized_return > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {(s.annualized_return * 100).toFixed(1)}%
                        </td>
                        <td className="py-2 px-2 text-[10px] font-mono text-amber-400">
                          {(s.annualized_volatility * 100).toFixed(1)}%
                        </td>
                        <td className="py-2 px-2 text-[10px] font-mono text-[#f1f5f9]">
                          {new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(s.allocation_inr)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* VaR Cards */}
          {varData && (
            <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
              <h3 className="text-xs text-[#64748b] uppercase tracking-wider mb-4">
                Value at Risk (VaR)
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {[
                  { label: 'Historical VaR', data: varData.historical },
                  { label: 'Parametric VaR', data: varData.parametric },
                  { label: 'Monte Carlo VaR', data: varData.monte_carlo },
                ].map((v) => (
                  <div key={v.label} className="bg-[#0c1220] border border-[#1f2937] rounded-lg p-4">
                    <span className="text-[10px] text-[#64748b] uppercase">{v.label}</span>
                    {v.data ? (
                      <div className="mt-2 space-y-1">
                        <div className="flex justify-between">
                          <span className="text-[10px] font-mono text-[#64748b]">95% VaR</span>
                          <span className="text-xs font-mono font-bold text-amber-400">
                            {(v.data['95%'] != null ? (v.data['95%'] * 100) : 0).toFixed(2)}%
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[10px] font-mono text-[#64748b]">99% VaR</span>
                          <span className="text-xs font-mono font-bold text-red-400">
                            {(v.data['99%'] != null ? (v.data['99%'] * 100) : 0).toFixed(2)}%
                          </span>
                        </div>
                      </div>
                    ) : (
                      <p className="text-[#64748b] font-mono text-xs mt-2">N/A</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Risk Metrics Dashboard */}
          <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
            <h3 className="text-xs text-[#64748b] uppercase tracking-wider mb-4">
              Risk Metrics
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
              <MetricCard
                label="Sharpe"
                value={perf.sharpe_ratio?.toFixed(2)}
                color={perf.sharpe_ratio > 1 ? 'text-emerald-400' : perf.sharpe_ratio < 0 ? 'text-red-400' : 'text-amber-400'}
              />
              <MetricCard
                label="Sortino"
                value={perf.sortino_ratio?.toFixed(2)}
                color={perf.sortino_ratio > 1.5 ? 'text-emerald-400' : perf.sortino_ratio < 0 ? 'text-red-400' : 'text-amber-400'}
              />
              <MetricCard
                label="Calmar"
                value={perf.calmar_ratio?.toFixed(2)}
                color={perf.calmar_ratio > 1 ? 'text-emerald-400' : 'text-amber-400'}
              />
              <MetricCard
                label="Treynor"
                value={perf.treynor_ratio?.toFixed(4)}
                color="text-[#f1f5f9]"
              />
              <MetricCard
                label="Info Ratio"
                value={perf.information_ratio?.toFixed(2)}
                color="text-[#f1f5f9]"
              />
              <MetricCard
                label="Max Drawdown"
                value={result.drawdown?.max_drawdown != null ? `${(result.drawdown.max_drawdown * 100).toFixed(1)}%` : 'N/A'}
                color="text-red-400"
              />
            </div>
          </div>

          {/* Correlation Heatmap */}
          <CorrelationHeatmap
            matrix={corrMatrix}
            stocks={result.portfolio?.stocks || []}
          />

          {/* Monte Carlo Fan Chart */}
          {monteCarloChart && (
            <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
              <h3 className="text-xs text-[#64748b] uppercase tracking-wider mb-4">
                Monte Carlo Simulation
              </h3>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart
                  data={
                    monteCarloChart.p50
                      ? monteCarloChart.p50.map((v, i) => ({
                          day: i,
                          p5: monteCarloChart.p5?.[i],
                          p25: monteCarloChart.p25?.[i],
                          p50: v,
                          p75: monteCarloChart.p75?.[i],
                          p95: monteCarloChart.p95?.[i],
                        }))
                      : []
                  }
                >
                  <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="day"
                    tick={{ fontSize: 10, fill: '#475569', fontFamily: 'monospace' }}
                    axisLine={{ stroke: '#1f2937' }}
                    label={{ value: 'Days', position: 'insideBottom', offset: -5, style: { fontSize: 10, fill: '#475569', fontFamily: 'monospace' } }}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: '#475569', fontFamily: 'monospace' }}
                    axisLine={{ stroke: '#1f2937' }}
                    tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize: '10px', fontFamily: 'monospace' }} />
                  <Area type="monotone" dataKey="p95" name="95th" stroke="#22c55e" fill="#22c55e" fillOpacity={0.05} strokeWidth={1} />
                  <Area type="monotone" dataKey="p75" name="75th" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.08} strokeWidth={1} />
                  <Area type="monotone" dataKey="p50" name="Median" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.1} strokeWidth={2} />
                  <Area type="monotone" dataKey="p25" name="25th" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.08} strokeWidth={1} />
                  <Area type="monotone" dataKey="p5" name="5th" stroke="#ef4444" fill="#ef4444" fillOpacity={0.05} strokeWidth={1} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Efficient Frontier */}
          {efChartData.length > 0 && (
            <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
              <h3 className="text-xs text-[#64748b] uppercase tracking-wider mb-4">
                Efficient Frontier
              </h3>
              <ResponsiveContainer width="100%" height={300}>
                <ScatterChart>
                  <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="volatility"
                    name="Volatility"
                    tick={{ fontSize: 10, fill: '#475569', fontFamily: 'monospace' }}
                    axisLine={{ stroke: '#1f2937' }}
                    tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                    label={{ value: 'Volatility', position: 'insideBottom', offset: -5, style: { fontSize: 10, fill: '#475569', fontFamily: 'monospace' } }}
                  />
                  <YAxis
                    dataKey="ret"
                    name="Return"
                    tick={{ fontSize: 10, fill: '#475569', fontFamily: 'monospace' }}
                    axisLine={{ stroke: '#1f2937' }}
                    tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                    label={{ value: 'Return', angle: -90, position: 'insideLeft', style: { fontSize: 10, fill: '#475569', fontFamily: 'monospace' } }}
                  />
                  <Tooltip
                    content={({ payload }) => {
                      if (!payload?.length) return null;
                      const d = payload[0].payload;
                      return (
                        <div className="bg-[#111827] border border-[#1f2937] rounded px-3 py-2 shadow-xl">
                          <p className="text-xs font-mono text-[#94a3b8]">Vol: {(d.volatility * 100).toFixed(2)}%</p>
                          <p className="text-xs font-mono text-[#94a3b8]">Ret: {(d.ret * 100).toFixed(2)}%</p>
                          <p className="text-xs font-mono text-blue-400">Sharpe: {d.sharpe?.toFixed(2)}</p>
                        </div>
                      );
                    }}
                  />
                  <Scatter
                    data={efChartData.filter((_, i) => i % Math.max(1, Math.floor(efChartData.length / 500)) === 0)}
                    fill="#3b82f6"
                  >
                    {efChartData
                      .filter((_, i) => i % Math.max(1, Math.floor(efChartData.length / 500)) === 0)
                      .map((d, i) => {
                        const sharpe = d.sharpe || 0;
                        const color = sharpe > 1.5 ? '#22c55e' : sharpe > 0.5 ? '#3b82f6' : sharpe > 0 ? '#f59e0b' : '#ef4444';
                        return <Cell key={i} fill={color} fillOpacity={0.6} />;
                      })}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
              {efData?.max_sharpe_portfolio && (
                <div className="mt-4 flex items-center gap-6 text-xs font-mono">
                  <span className="text-[#64748b]">Max Sharpe Portfolio:</span>
                  <span className="text-emerald-400">
                    Return: {((efData.max_sharpe_portfolio.return || 0) * 100).toFixed(2)}%
                  </span>
                  <span className="text-amber-400">
                    Vol: {((efData.max_sharpe_portfolio.volatility || 0) * 100).toFixed(2)}%
                  </span>
                  <span className="text-blue-400">
                    Sharpe: {(efData.max_sharpe_portfolio.sharpe || 0).toFixed(2)}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
