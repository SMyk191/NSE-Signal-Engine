import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search, Filter, ChevronDown, ChevronUp, Loader2,
  ArrowUpDown, SlidersHorizontal, RotateCcw,
} from 'lucide-react';
import SignalBadge from '../components/SignalBadge';
import { screenStocks } from '../services/api';

const SECTORS = [
  'Oil & Gas', 'IT', 'Banking', 'Financial Services', 'FMCG',
  'Automobile', 'Pharma', 'Metals', 'Infrastructure', 'Cement',
  'Telecom', 'Power', 'Insurance', 'Consumer Goods', 'Healthcare',
];

const SIGNAL_TYPES = ['STRONG BUY', 'BUY', 'HOLD', 'SELL', 'STRONG SELL'];

export default function Screener() {
  const navigate = useNavigate();
  const [filtersOpen, setFiltersOpen] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);
  const [sortField, setSortField] = useState('composite_score');
  const [sortOrder, setSortOrder] = useState('desc');

  // Filter state
  const [rsiMin, setRsiMin] = useState(0);
  const [rsiMax, setRsiMax] = useState(100);
  const [macdSignal, setMacdSignal] = useState('');
  const [selectedSectors, setSelectedSectors] = useState([]);
  const [scoreMin, setScoreMin] = useState(-100);
  const [scoreMax, setScoreMax] = useState(100);
  const [selectedSignals, setSelectedSignals] = useState([]);
  const [aboveSma200, setAboveSma200] = useState(false);
  const [volumeSpike, setVolumeSpike] = useState(false);

  const toggleSector = (sector) => {
    setSelectedSectors((prev) =>
      prev.includes(sector) ? prev.filter((s) => s !== sector) : [...prev, sector]
    );
  };

  const toggleSignal = (sig) => {
    setSelectedSignals((prev) =>
      prev.includes(sig) ? prev.filter((s) => s !== sig) : [...prev, sig]
    );
  };

  const resetFilters = () => {
    setRsiMin(0);
    setRsiMax(100);
    setMacdSignal('');
    setSelectedSectors([]);
    setScoreMin(-100);
    setScoreMax(100);
    setSelectedSignals([]);
    setAboveSma200(false);
    setVolumeSpike(false);
  };

  const handleSearch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const filters = {
        sort_by: sortField,
        sort_order: sortOrder,
      };

      if (rsiMin > 0) filters.rsi_min = rsiMin;
      if (rsiMax < 100) filters.rsi_max = rsiMax;
      if (macdSignal) filters.macd_signal = macdSignal;
      if (selectedSectors.length === 1) filters.sector = selectedSectors[0];
      if (scoreMin > -100) filters.score_min = scoreMin;
      if (scoreMax < 100) filters.score_max = scoreMax;
      if (selectedSignals.length === 1) filters.signal_type = selectedSignals[0];
      if (aboveSma200) filters.above_sma200 = true;
      if (volumeSpike) filters.volume_spike = true;

      const res = await screenStocks(filters);

      // Client-side filter for multi-select sectors and signals (API supports single)
      let stocks = res.stocks || [];
      if (selectedSectors.length > 1) {
        stocks = stocks.filter((s) => selectedSectors.includes(s.sector));
      }
      if (selectedSignals.length > 1) {
        stocks = stocks.filter((s) => selectedSignals.includes(s.signal));
      }

      setResults({ ...res, stocks, count: stocks.length });
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  }, [rsiMin, rsiMax, macdSignal, selectedSectors, scoreMin, scoreMax, selectedSignals, aboveSma200, volumeSpike, sortField, sortOrder]);

  const handleSort = (field) => {
    if (sortField === field) {
      setSortOrder((prev) => (prev === 'desc' ? 'asc' : 'desc'));
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  // Sort results client-side when sort changes
  const sortedStocks = results?.stocks
    ? [...results.stocks].sort((a, b) => {
        const aVal = a[sortField] ?? 0;
        const bVal = b[sortField] ?? 0;
        return sortOrder === 'desc' ? bVal - aVal : aVal - bVal;
      })
    : [];

  const SortHeader = ({ field, children }) => (
    <th
      className="text-left text-[10px] text-[#64748b] uppercase tracking-wider pb-3 px-3 cursor-pointer hover:text-[#94a3b8] transition-colors select-none"
      onClick={() => handleSort(field)}
    >
      <div className="flex items-center gap-1">
        {children}
        {sortField === field ? (
          sortOrder === 'desc' ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />
        ) : (
          <ArrowUpDown className="w-3 h-3 opacity-30" />
        )}
      </div>
    </th>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4 animate-fade-up">
        <Search className="w-6 h-6 text-blue-500" />
        <div>
          <h1 className="text-xl font-bold text-[#f1f5f9]">Stock Screener</h1>
          <p className="text-xs text-[#64748b]">Filter NIFTY 50 stocks by technical and fundamental criteria</p>
        </div>
      </div>

      {/* Filter Panel */}
      <div className="bg-[#111827] border border-[#1f2937] rounded-xl animate-fade-up" style={{ animationDelay: '100ms' }}>
        <button
          onClick={() => setFiltersOpen(!filtersOpen)}
          className="w-full flex items-center justify-between px-6 py-4 hover:bg-[#0c1220]/50 transition-colors"
        >
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="w-4 h-4 text-blue-500" />
            <span className="text-xs text-[#94a3b8] font-bold uppercase tracking-wider">Filters</span>
          </div>
          {filtersOpen ? <ChevronUp className="w-4 h-4 text-[#64748b]" /> : <ChevronDown className="w-4 h-4 text-[#64748b]" />}
        </button>

        {filtersOpen && (
          <div className="px-6 pb-6 space-y-5 border-t border-[#1f2937]">
            <div className="pt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {/* RSI Range */}
              <div>
                <label className="text-[10px] text-[#64748b] uppercase block mb-2">
                  RSI Range: {rsiMin} - {rsiMax}
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={rsiMin}
                    onChange={(e) => setRsiMin(Math.min(Number(e.target.value), rsiMax))}
                    className="flex-1 accent-blue-500 h-1"
                  />
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={rsiMax}
                    onChange={(e) => setRsiMax(Math.max(Number(e.target.value), rsiMin))}
                    className="flex-1 accent-blue-500 h-1"
                  />
                </div>
              </div>

              {/* MACD Signal */}
              <div>
                <label className="text-[10px] text-[#64748b] uppercase block mb-2">MACD Signal</label>
                <select
                  value={macdSignal}
                  onChange={(e) => setMacdSignal(e.target.value)}
                  className="w-full bg-[#0c1220] border border-[#1f2937] rounded px-3 py-2 text-xs font-mono text-[#f1f5f9] focus:border-blue-500/40 outline-none"
                >
                  <option value="">Any</option>
                  <option value="bullish">Bullish (MACD &gt; Signal)</option>
                  <option value="bearish">Bearish (MACD &lt; Signal)</option>
                </select>
              </div>

              {/* Composite Score Range */}
              <div>
                <label className="text-[10px] text-[#64748b] uppercase block mb-2">
                  Composite Score: {scoreMin} to {scoreMax}
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min="-100"
                    max="100"
                    value={scoreMin}
                    onChange={(e) => setScoreMin(Math.min(Number(e.target.value), scoreMax))}
                    className="flex-1 accent-blue-500 h-1"
                  />
                  <input
                    type="range"
                    min="-100"
                    max="100"
                    value={scoreMax}
                    onChange={(e) => setScoreMax(Math.max(Number(e.target.value), scoreMin))}
                    className="flex-1 accent-blue-500 h-1"
                  />
                </div>
              </div>
            </div>

            {/* Sectors */}
            <div>
              <label className="text-[10px] text-[#64748b] uppercase block mb-2">Sectors</label>
              <div className="flex flex-wrap gap-2">
                {SECTORS.map((sector) => (
                  <button
                    key={sector}
                    onClick={() => toggleSector(sector)}
                    className={`px-2.5 py-1 rounded text-[10px] font-mono border transition-colors ${
                      selectedSectors.includes(sector)
                        ? 'bg-blue-500/20 border-blue-500/40 text-blue-400'
                        : 'bg-[#0c1220] border-[#1f2937] text-[#64748b] hover:border-[#64748b]'
                    }`}
                  >
                    {sector}
                  </button>
                ))}
              </div>
            </div>

            {/* Signal Types */}
            <div>
              <label className="text-[10px] text-[#64748b] uppercase block mb-2">Signal Type</label>
              <div className="flex flex-wrap gap-2">
                {SIGNAL_TYPES.map((sig) => {
                  const colors = {
                    'STRONG BUY': 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400',
                    'BUY': 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
                    'HOLD': 'bg-amber-500/20 border-amber-500/40 text-amber-400',
                    'SELL': 'bg-red-500/10 border-red-500/30 text-red-400',
                    'STRONG SELL': 'bg-red-500/20 border-red-500/40 text-red-400',
                  };
                  return (
                    <button
                      key={sig}
                      onClick={() => toggleSignal(sig)}
                      className={`px-2.5 py-1 rounded text-[10px] font-mono font-bold border transition-colors ${
                        selectedSignals.includes(sig)
                          ? colors[sig]
                          : 'bg-[#0c1220] border-[#1f2937] text-[#64748b] hover:border-[#64748b]'
                      }`}
                    >
                      {sig}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Toggles */}
            <div className="flex flex-wrap gap-6">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={aboveSma200}
                  onChange={(e) => setAboveSma200(e.target.checked)}
                  className="accent-blue-500 w-3.5 h-3.5"
                />
                <span className="text-xs text-[#94a3b8]">Price above SMA 200</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={volumeSpike}
                  onChange={(e) => setVolumeSpike(e.target.checked)}
                  className="accent-blue-500 w-3.5 h-3.5"
                />
                <span className="text-xs text-[#94a3b8]">Volume spike (&gt;2x avg)</span>
              </label>
            </div>

            {/* Action buttons */}
            <div className="flex items-center gap-3 pt-2">
              <button
                onClick={handleSearch}
                disabled={loading}
                className="px-5 py-2.5 bg-blue-500/20 border border-blue-500/40 text-blue-400 rounded text-xs font-mono font-bold hover:bg-blue-500/30 transition-colors disabled:opacity-30 flex items-center gap-2"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                Apply Filters
              </button>
              <button
                onClick={resetFilters}
                className="px-4 py-2.5 bg-[#0c1220] border border-[#1f2937] text-[#94a3b8] rounded text-xs font-mono hover:border-[#64748b] transition-colors flex items-center gap-2"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Reset
              </button>
            </div>
          </div>
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
          <span className="ml-3 text-sm text-[#94a3b8]">Screening stocks...</span>
        </div>
      )}

      {/* Results */}
      {results && !loading && (
        <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xs text-[#64748b] uppercase tracking-wider">
              Results
            </h3>
            <span className="text-xs font-mono text-blue-400 font-bold">
              {results.count} stock{results.count !== 1 ? 's' : ''} found
            </span>
          </div>

          {sortedStocks.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[#1f2937]">
                    <SortHeader field="symbol">Symbol</SortHeader>
                    <th className="text-left text-[10px] text-[#64748b] uppercase tracking-wider pb-3 px-3">
                      Sector
                    </th>
                    <SortHeader field="price">Price</SortHeader>
                    <SortHeader field="change_pct">Change%</SortHeader>
                    <SortHeader field="rsi">RSI</SortHeader>
                    <SortHeader field="macd">MACD</SortHeader>
                    <SortHeader field="composite_score">Score</SortHeader>
                    <th className="text-left text-[10px] text-[#64748b] uppercase tracking-wider pb-3 px-3">
                      Signal
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {sortedStocks.map((stock) => (
                    <tr
                      key={stock.symbol}
                      onClick={() => navigate(`/technical/${stock.symbol}`)}
                      className="border-b border-[#1f2937]/50 hover:bg-blue-500/5 cursor-pointer transition-colors"
                    >
                      <td className="py-3 px-3 text-xs font-mono text-blue-400 font-bold">
                        {stock.symbol}
                      </td>
                      <td className="py-3 px-3 text-[10px] font-mono text-[#64748b]">
                        {stock.sector}
                      </td>
                      <td className="py-3 px-3 text-xs font-mono text-[#f1f5f9]">
                        {stock.price?.toLocaleString('en-IN', { style: 'currency', currency: 'INR' })}
                      </td>
                      <td className={`py-3 px-3 text-xs font-mono font-bold ${
                        stock.change_pct > 0 ? 'text-emerald-400' : stock.change_pct < 0 ? 'text-red-400' : 'text-[#94a3b8]'
                      }`}>
                        {stock.change_pct > 0 ? '+' : ''}{stock.change_pct?.toFixed(2)}%
                      </td>
                      <td className={`py-3 px-3 text-xs font-mono ${
                        stock.rsi > 70 ? 'text-red-400' : stock.rsi < 30 ? 'text-emerald-400' : 'text-[#94a3b8]'
                      }`}>
                        {stock.rsi?.toFixed(1) ?? '-'}
                      </td>
                      <td className={`py-3 px-3 text-xs font-mono ${
                        stock.macd > (stock.macd_signal || 0) ? 'text-emerald-400' : 'text-red-400'
                      }`}>
                        {stock.macd?.toFixed(2) ?? '-'}
                      </td>
                      <td className={`py-3 px-3 text-xs font-mono font-bold ${
                        stock.composite_score >= 30 ? 'text-emerald-400'
                          : stock.composite_score <= -30 ? 'text-red-400'
                            : 'text-amber-400'
                      }`}>
                        {stock.composite_score?.toFixed(1)}
                      </td>
                      <td className="py-3 px-3">
                        <SignalBadge score={stock.composite_score} size="sm" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-[#64748b] text-sm text-center py-8">
              No stocks match the selected filters
            </p>
          )}
        </div>
      )}

      {/* Empty state */}
      {!results && !loading && !error && (
        <div className="flex flex-col items-center justify-center py-16">
          <Filter className="w-12 h-12 text-[#64748b] mb-4" />
          <p className="text-[#64748b] text-sm">
            Set your filters and click "Apply Filters" to screen stocks
          </p>
        </div>
      )}
    </div>
  );
}
