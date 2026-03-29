import { useState, useCallback } from 'react';
import {
  LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import {
  History, Play, Loader2, TrendingUp, TrendingDown,
  DollarSign, Target, BarChart3,
} from 'lucide-react';
import StockSelector from '../components/StockSelector';
import useAppStore from '../stores/appStore';
import { runBacktest } from '../services/api';

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#111827] border border-[#1f2937] rounded px-3 py-2 shadow-xl">
      <p className="text-[10px] font-mono text-[#64748b]">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="text-xs font-mono" style={{ color: p.color }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toLocaleString('en-IN', { maximumFractionDigits: 2 }) : p.value}
        </p>
      ))}
    </div>
  );
}

function SummaryCard({ label, value, suffix = '', color, icon: Icon }) {
  return (
    <div className="bg-[#0c1220] border border-[#1f2937] rounded-lg p-4">
      <div className="flex items-center gap-2 mb-1">
        {Icon && <Icon className="w-3 h-3 text-[#64748b]" />}
        <span className="text-[10px] text-[#64748b] uppercase tracking-wider">{label}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span className={`text-lg font-bold font-mono ${color || 'text-[#f1f5f9]'}`}>
          {value ?? 'N/A'}
        </span>
        {suffix && <span className="text-xs font-mono text-[#94a3b8]">{suffix}</span>}
      </div>
    </div>
  );
}

function MonthlyHeatmap({ trades }) {
  if (!trades || trades.length === 0) return null;

  // Group P&L by month/year
  const monthly = {};
  const allYears = new Set();
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  trades.forEach((t) => {
    const exitDate = t.exit_date || t.Exit_Date;
    if (!exitDate) return;
    const d = new Date(exitDate);
    const year = d.getFullYear();
    const month = d.getMonth();
    allYears.add(year);
    const key = `${year}-${month}`;
    monthly[key] = (monthly[key] || 0) + (t.pnl || t.PnL || t.pnl_pct || 0);
  });

  const years = [...allYears].sort();

  if (years.length === 0) return null;

  const getColor = (val) => {
    if (val === undefined) return { bg: 'bg-[#1f2937]/30', text: 'text-[#64748b]' };
    if (val > 5) return { bg: 'bg-emerald-500/30', text: 'text-emerald-400' };
    if (val > 0) return { bg: 'bg-emerald-500/15', text: 'text-emerald-400' };
    if (val > -5) return { bg: 'bg-red-500/15', text: 'text-red-400' };
    return { bg: 'bg-red-500/30', text: 'text-red-400' };
  };

  return (
    <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
      <h3 className="text-xs text-[#64748b] uppercase tracking-wider mb-4">
        Monthly Returns Heatmap
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr>
              <th className="text-[10px] text-[#64748b] p-2 text-right">Year</th>
              {months.map((m) => (
                <th key={m} className="text-[10px] text-[#64748b] p-2 text-center">{m}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {years.map((year) => (
              <tr key={year}>
                <td className="text-[10px] font-mono text-[#94a3b8] p-2 text-right font-bold">{year}</td>
                {months.map((_, mi) => {
                  const val = monthly[`${year}-${mi}`];
                  const { bg, text } = getColor(val);
                  return (
                    <td key={mi} className="p-1 text-center">
                      <div className={`rounded py-2 px-1 text-[10px] font-mono font-bold ${bg} ${text}`}>
                        {val !== undefined ? `${val > 0 ? '+' : ''}${val.toFixed(0)}` : '-'}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function BacktestResults() {
  const { selectedStock } = useAppStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  // Configuration
  const [entryThreshold, setEntryThreshold] = useState(30);
  const [exitThreshold, setExitThreshold] = useState(-10);
  const [initialCapital, setInitialCapital] = useState(100000);
  const [period, setPeriod] = useState('2y');

  const handleRun = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await runBacktest({
        symbol: selectedStock,
        entry_threshold: entryThreshold,
        exit_threshold: exitThreshold,
        initial_capital: initialCapital,
        period,
      });
      setResult(res);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  }, [selectedStock, entryThreshold, exitThreshold, initialCapital, period]);

  const summary = result?.summary || {};
  const equityCurve = result?.equity_curve || [];
  const trades = result?.trades || [];

  // Build drawdown data from equity curve
  const drawdownData = equityCurve.length > 0
    ? (() => {
        let peak = equityCurve[0]?.equity || initialCapital;
        return equityCurve.map((d) => {
          if (d.equity > peak) peak = d.equity;
          const dd = ((d.equity - peak) / peak) * 100;
          return { date: d.date, drawdown: dd };
        });
      })()
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between animate-fade-up">
        <div className="flex items-center gap-4">
          <History className="w-6 h-6 text-blue-500" />
          <div>
            <h1 className="text-xl font-bold text-[#f1f5f9]">Backtest</h1>
            <p className="text-xs text-[#64748b]">Signal-based strategy backtesting engine</p>
          </div>
        </div>
        <StockSelector />
      </div>

      {/* Configuration Panel */}
      <div className="bg-[#111827] border border-[#1f2937] rounded-xl p-6 animate-fade-up" style={{ animationDelay: '100ms' }}>
        <h3 className="text-xs text-[#64748b] uppercase tracking-wider mb-4">
          Backtest Configuration
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {/* Period */}
          <div>
            <label className="text-[10px] text-[#64748b] uppercase block mb-1">Period</label>
            <select
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              className="w-full bg-[#0c1220] border border-[#1f2937] rounded px-3 py-2 text-xs font-mono text-[#f1f5f9] focus:border-blue-500/40 outline-none"
            >
              <option value="6mo">6 Months</option>
              <option value="1y">1 Year</option>
              <option value="2y">2 Years</option>
              <option value="5y">5 Years</option>
            </select>
          </div>

          {/* Entry Threshold */}
          <div>
            <label className="text-[10px] text-[#64748b] uppercase block mb-1">
              Entry Threshold: {entryThreshold}
            </label>
            <input
              type="range"
              min="-50"
              max="80"
              value={entryThreshold}
              onChange={(e) => setEntryThreshold(Number(e.target.value))}
              className="w-full accent-emerald-500 h-1"
            />
            <div className="flex justify-between text-[9px] font-mono text-[#64748b] mt-1">
              <span>-50</span>
              <span>80</span>
            </div>
          </div>

          {/* Exit Threshold */}
          <div>
            <label className="text-[10px] text-[#64748b] uppercase block mb-1">
              Exit Threshold: {exitThreshold}
            </label>
            <input
              type="range"
              min="-80"
              max="50"
              value={exitThreshold}
              onChange={(e) => setExitThreshold(Number(e.target.value))}
              className="w-full accent-red-500 h-1"
            />
            <div className="flex justify-between text-[9px] font-mono text-[#64748b] mt-1">
              <span>-80</span>
              <span>50</span>
            </div>
          </div>

          {/* Initial Capital */}
          <div>
            <label className="text-[10px] text-[#64748b] uppercase block mb-1">Capital (INR)</label>
            <input
              type="number"
              value={initialCapital}
              onChange={(e) => setInitialCapital(Number(e.target.value))}
              min="1000"
              step="10000"
              className="w-full bg-[#0c1220] border border-[#1f2937] rounded px-3 py-2 text-xs font-mono text-[#f1f5f9] focus:border-blue-500/40 outline-none"
            />
          </div>

          {/* Run Button */}
          <div className="flex items-end">
            <button
              onClick={handleRun}
              disabled={loading}
              className="w-full px-4 py-2 bg-blue-500/20 border border-blue-500/40 text-blue-400 rounded text-xs font-mono font-bold hover:bg-blue-500/30 transition-colors disabled:opacity-30 flex items-center justify-center gap-2"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              Run Backtest
            </button>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
          <p className="text-red-400 font-mono text-sm">{error}</p>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          <span className="ml-3 text-sm text-[#94a3b8]">
            Running backtest for {selectedStock}... This may take a minute.
          </span>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <div className="space-y-6">
          {/* Performance Summary */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <SummaryCard
              label="Total Return"
              value={summary.total_return_pct != null ? `${summary.total_return_pct > 0 ? '+' : ''}${summary.total_return_pct.toFixed(2)}` : null}
              suffix="%"
              color={summary.total_return_pct > 0 ? 'text-emerald-400' : 'text-red-400'}
              icon={TrendingUp}
            />
            <SummaryCard
              label="CAGR"
              value={summary.cagr_pct != null ? summary.cagr_pct.toFixed(2) : null}
              suffix="%"
              color={summary.cagr_pct > 0 ? 'text-emerald-400' : 'text-red-400'}
              icon={BarChart3}
            />
            <SummaryCard
              label="Max Drawdown"
              value={summary.max_drawdown_pct != null ? summary.max_drawdown_pct.toFixed(2) : null}
              suffix="%"
              color="text-red-400"
              icon={TrendingDown}
            />
            <SummaryCard
              label="Sharpe Ratio"
              value={summary.sharpe_ratio != null ? summary.sharpe_ratio.toFixed(2) : null}
              color={summary.sharpe_ratio > 1 ? 'text-emerald-400' : summary.sharpe_ratio > 0 ? 'text-amber-400' : 'text-red-400'}
              icon={Target}
            />
            <SummaryCard
              label="Win Rate"
              value={summary.win_rate_pct != null ? summary.win_rate_pct.toFixed(1) : null}
              suffix="%"
              color={summary.win_rate_pct > 50 ? 'text-emerald-400' : 'text-red-400'}
              icon={Target}
            />
            <SummaryCard
              label="Profit Factor"
              value={summary.profit_factor != null ? summary.profit_factor.toFixed(2) : null}
              color={summary.profit_factor > 1.5 ? 'text-emerald-400' : summary.profit_factor > 1 ? 'text-amber-400' : 'text-red-400'}
              icon={DollarSign}
            />
            <SummaryCard
              label="Total Trades"
              value={summary.total_trades}
              color="text-[#f1f5f9]"
              icon={History}
            />
            <SummaryCard
              label="Total Costs"
              value={summary.total_costs != null ? `${summary.total_costs.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : null}
              suffix="INR"
              color="text-amber-400"
              icon={DollarSign}
            />
          </div>

          {/* Equity Curve */}
          {equityCurve.length > 0 && (
            <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
              <h3 className="text-xs text-[#64748b] uppercase tracking-wider mb-4">
                Equity Curve
              </h3>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={equityCurve}>
                  <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 9, fill: '#475569', fontFamily: 'monospace' }}
                    axisLine={{ stroke: '#1f2937' }}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: '#475569', fontFamily: 'monospace' }}
                    axisLine={{ stroke: '#1f2937' }}
                    tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Line
                    type="monotone"
                    dataKey="equity"
                    name="Portfolio Value"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Drawdown Chart */}
          {drawdownData.length > 0 && (
            <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
              <h3 className="text-xs text-[#64748b] uppercase tracking-wider mb-4">
                Drawdown
              </h3>
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={drawdownData}>
                  <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 9, fill: '#475569', fontFamily: 'monospace' }}
                    axisLine={{ stroke: '#1f2937' }}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: '#475569', fontFamily: 'monospace' }}
                    axisLine={{ stroke: '#1f2937' }}
                    tickFormatter={(v) => `${v.toFixed(0)}%`}
                    domain={['dataMin', 0]}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="drawdown"
                    name="Drawdown %"
                    stroke="#ef4444"
                    fill="#ef4444"
                    fillOpacity={0.15}
                    strokeWidth={1.5}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Trade Log */}
          {trades.length > 0 && (
            <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
              <h3 className="text-xs text-[#64748b] uppercase tracking-wider mb-4">
                Trade Log ({trades.length} trades)
              </h3>
              <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
                <table className="w-full">
                  <thead className="sticky top-0 bg-[#111827]">
                    <tr className="border-b border-[#1f2937]">
                      {['Entry Date', 'Entry Price', 'Exit Date', 'Exit Price', 'Shares', 'P&L', 'P&L %', 'Costs'].map((h) => (
                        <th key={h} className="text-left text-[10px] text-[#64748b] uppercase tracking-wider pb-3 px-3">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {trades.map((trade, i) => {
                      const pnl = trade.pnl ?? trade.PnL ?? trade.profit ?? 0;
                      const pnlPct = trade.pnl_pct ?? trade.PnL_pct ?? trade.return_pct ?? 0;
                      const isProfit = pnl > 0;
                      return (
                        <tr key={i} className="border-b border-[#1f2937]/50 hover:bg-[#0c1220]">
                          <td className="py-2 px-3 text-[10px] font-mono text-[#94a3b8]">
                            {trade.entry_date || trade.Entry_Date || '-'}
                          </td>
                          <td className="py-2 px-3 text-xs font-mono text-[#f1f5f9]">
                            {(trade.entry_price || trade.Entry_Price || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                          </td>
                          <td className="py-2 px-3 text-[10px] font-mono text-[#94a3b8]">
                            {trade.exit_date || trade.Exit_Date || '-'}
                          </td>
                          <td className="py-2 px-3 text-xs font-mono text-[#f1f5f9]">
                            {(trade.exit_price || trade.Exit_Price || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                          </td>
                          <td className="py-2 px-3 text-xs font-mono text-[#94a3b8]">
                            {trade.shares || trade.quantity || '-'}
                          </td>
                          <td className={`py-2 px-3 text-xs font-mono font-bold ${isProfit ? 'text-emerald-400' : 'text-red-400'}`}>
                            {isProfit ? '+' : ''}{pnl.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                          </td>
                          <td className={`py-2 px-3 text-xs font-mono font-bold ${isProfit ? 'text-emerald-400' : 'text-red-400'}`}>
                            {pnlPct > 0 ? '+' : ''}{(typeof pnlPct === 'number' ? pnlPct : 0).toFixed(2)}%
                          </td>
                          <td className="py-2 px-3 text-[10px] text-[#64748b]">
                            {(trade.costs || trade.total_costs || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Monthly Returns Heatmap */}
          <MonthlyHeatmap trades={trades} />
        </div>
      )}

      {/* Empty state */}
      {!result && !loading && !error && (
        <div className="flex flex-col items-center justify-center py-16">
          <History className="w-12 h-12 text-[#64748b] mb-4" />
          <p className="text-[#64748b] text-sm">
            Configure parameters and click "Run Backtest" to start
          </p>
        </div>
      )}
    </div>
  );
}
