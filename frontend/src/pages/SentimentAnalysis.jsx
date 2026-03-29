import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell,
} from 'recharts';
import {
  MessageSquare, TrendingUp, TrendingDown, AlertTriangle, Zap,
  ExternalLink, Tag, Loader2,
} from 'lucide-react';
import StockSelector from '../components/StockSelector';
import useAppStore from '../stores/appStore';
import { fetchSentiment } from '../services/api';

const SENTIMENT_COLORS = {
  positive: '#22c55e',
  negative: '#ef4444',
  neutral: '#64748b',
};

function getSentimentColor(score) {
  if (score >= 0.3) return '#22c55e';
  if (score >= 0.1) return '#4ade80';
  if (score <= -0.3) return '#ef4444';
  if (score <= -0.1) return '#f87171';
  return '#f59e0b';
}

function getSentimentLabel(score) {
  if (score >= 0.5) return 'Very Bullish';
  if (score >= 0.2) return 'Bullish';
  if (score >= -0.2) return 'Neutral';
  if (score >= -0.5) return 'Bearish';
  return 'Very Bearish';
}

function SentimentGauge({ score }) {
  const color = getSentimentColor(score);
  const label = getSentimentLabel(score);
  const pct = ((score + 1) / 2) * 100;

  return (
    <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
      <h3 className="text-xs text-[#64748b] uppercase tracking-wider mb-4">
        Overall Sentiment
      </h3>
      <div className="flex items-center gap-6">
        <div className="text-center">
          <div className="text-5xl font-bold font-mono" style={{ color }}>
            {score > 0 ? '+' : ''}{score.toFixed(2)}
          </div>
          <div className="text-sm font-medium mt-2" style={{ color }}>
            {label}
          </div>
        </div>
        <div className="flex-1">
          <div className="flex justify-between text-[10px] font-mono text-[#64748b] mb-1">
            <span>-1.0</span>
            <span>0.0</span>
            <span>+1.0</span>
          </div>
          <div className="h-3 bg-[#1f2937] rounded-full relative overflow-hidden">
            <div
              className="absolute inset-y-0 left-0 rounded-full transition-all duration-700"
              style={{
                width: `${pct}%`,
                background: `linear-gradient(90deg, #ef4444, #f59e0b, #22c55e)`,
              }}
            />
            <div
              className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full border-2 shadow-lg transition-all duration-700"
              style={{ left: `calc(${pct}% - 6px)`, borderColor: color }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function NewsFeed({ articles }) {
  if (!articles || articles.length === 0) {
    return (
      <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
        <h3 className="text-xs text-[#64748b] uppercase tracking-wider mb-4">
          News Feed
        </h3>
        <p className="text-[#64748b] text-sm text-center py-8">
          No news articles available
        </p>
      </div>
    );
  }

  return (
    <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
      <h3 className="text-xs text-[#64748b] uppercase tracking-wider mb-4">
        News Feed ({articles.length} articles)
      </h3>
      <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
        {articles.map((article, i) => {
          const sentScore = article.sentiment_score ?? 0;
          const borderColor = sentScore > 0.1
            ? 'border-l-emerald-500'
            : sentScore < -0.1
              ? 'border-l-red-500'
              : 'border-l-slate-600';

          return (
            <div
              key={i}
              className={`bg-[#0c1220] border border-[#1f2937] border-l-4 ${borderColor} rounded-r-lg p-3`}
            >
              <div className="flex items-start justify-between gap-2">
                <h4 className="text-sm text-[#f1f5f9] leading-snug flex-1">
                  {article.title}
                </h4>
                {article.link && (
                  <a
                    href={article.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[#64748b] hover:text-blue-400 transition-colors flex-shrink-0"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                )}
              </div>
              <div className="flex items-center gap-3 mt-2">
                <span className="text-[10px] text-[#64748b]">
                  {article.publisher || article.source || 'Unknown'}
                </span>
                {article.publish_time && (
                  <span className="text-[10px] text-[#64748b]">
                    {new Date(article.publish_time * 1000).toLocaleDateString()}
                  </span>
                )}
                {sentScore !== undefined && (
                  <span
                    className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded"
                    style={{
                      color: getSentimentColor(sentScore),
                      backgroundColor: `${getSentimentColor(sentScore)}15`,
                    }}
                  >
                    {sentScore > 0 ? '+' : ''}{sentScore.toFixed(2)}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AnalystConsensus({ data }) {
  if (!data) return null;
  const categories = [
    { key: 'strong_buy', label: 'Strong Buy', color: '#22c55e' },
    { key: 'buy', label: 'Buy', color: '#4ade80' },
    { key: 'hold', label: 'Hold', color: '#f59e0b' },
    { key: 'sell', label: 'Sell', color: '#f87171' },
    { key: 'strong_sell', label: 'Strong Sell', color: '#ef4444' },
  ];

  const total = categories.reduce((sum, c) => sum + (data[c.key] || 0), 0) || 1;

  return (
    <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
      <h3 className="text-xs text-[#64748b] uppercase tracking-wider mb-4">
        Analyst Consensus
      </h3>
      <div className="space-y-2">
        {categories.map((cat) => {
          const val = data[cat.key] || 0;
          const pct = (val / total) * 100;
          return (
            <div key={cat.key} className="flex items-center gap-3">
              <span className="text-[10px] text-[#94a3b8] w-20 text-right">
                {cat.label}
              </span>
              <div className="flex-1 h-5 bg-[#0c1220] rounded overflow-hidden">
                <div
                  className="h-full rounded transition-all duration-500"
                  style={{ width: `${pct}%`, backgroundColor: cat.color }}
                />
              </div>
              <span className="text-xs font-mono text-[#94a3b8] w-8">{val}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#111827] border border-[#1f2937] rounded px-3 py-2 shadow-xl">
      <p className="text-[10px] font-mono text-[#64748b]">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="text-xs font-mono" style={{ color: p.color }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(3) : p.value}
        </p>
      ))}
    </div>
  );
}

export default function SentimentAnalysis() {
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
        const res = await fetchSentiment(selectedStock);
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

  const trendData = [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between animate-fade-up">
        <div className="flex items-center gap-4">
          <MessageSquare className="w-6 h-6 text-blue-500" />
          <div>
            <h1 className="text-xl font-bold text-[#f1f5f9]">
              Sentiment Analysis
            </h1>
            <p className="text-xs text-[#64748b]">
              AI-powered news sentiment and market mood
            </p>
          </div>
        </div>
        <StockSelector />
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
          <span className="ml-3 text-sm text-[#94a3b8]">
            Analyzing sentiment for {selectedStock}...
          </span>
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
          <p className="text-red-400 font-mono text-sm">{error}</p>
        </div>
      )}

      {/* Data */}
      {data && !loading && (
        <div className="space-y-6">
          {/* Top row: Gauge + Trend */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-fade-up" style={{ animationDelay: '100ms' }}>
            <SentimentGauge score={data.sentiment_score ?? 0} />

            {/* Sentiment Trend Chart */}
            <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
              <h3 className="text-xs text-[#64748b] uppercase tracking-wider mb-4">
                Sentiment Trend
              </h3>
              {trendData.length > 0 ? (
                <ResponsiveContainer width="100%" height={180}>
                  <LineChart data={trendData}>
                    <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
                    <XAxis
                      dataKey="point"
                      tick={{ fontSize: 10, fill: '#475569', fontFamily: 'monospace' }}
                      axisLine={{ stroke: '#1f2937' }}
                    />
                    <YAxis
                      domain={[-1, 1]}
                      tick={{ fontSize: 10, fill: '#475569', fontFamily: 'monospace' }}
                      axisLine={{ stroke: '#1f2937' }}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <Line
                      type="monotone"
                      dataKey="score"
                      name="Sentiment"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-[#64748b] text-sm text-center py-8">
                  Historical sentiment trend requires multiple data points over time
                </p>
              )}
            </div>
          </div>

          {/* Key Themes */}
          {data.key_themes && data.key_themes.length > 0 && (
            <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
              <h3 className="text-xs text-[#64748b] uppercase tracking-wider mb-4 flex items-center gap-2">
                <Tag className="w-3.5 h-3.5" /> Key Themes
              </h3>
              <div className="flex flex-wrap gap-2">
                {data.key_themes.map((theme, i) => {
                  const colors = ['#3b82f6', '#8b5cf6', '#22c55e', '#f59e0b', '#ec4899', '#6366f1'];
                  const color = colors[i % colors.length];
                  return (
                    <span
                      key={i}
                      className="px-3 py-1 rounded-full text-xs font-medium border"
                      style={{
                        color,
                        borderColor: `${color}40`,
                        backgroundColor: `${color}10`,
                      }}
                    >
                      {theme}
                    </span>
                  );
                })}
              </div>
            </div>
          )}

          {/* Risk Factors + Catalysts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Risk Factors */}
            <div className="bg-[#111827] border border-amber-500/20 rounded-lg p-6">
              <h3 className="text-xs font-mono text-amber-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                <AlertTriangle className="w-3.5 h-3.5" /> Risk Factors
              </h3>
              {data.risk_factors && data.risk_factors.length > 0 ? (
                <ul className="space-y-2">
                  {data.risk_factors.map((risk, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-amber-500 mt-1 text-xs">&#9679;</span>
                      <span className="text-sm text-[#94a3b8] leading-relaxed">
                        {risk}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[#64748b] text-sm">No risk factors identified</p>
              )}
            </div>

            {/* Catalysts */}
            <div className="bg-[#111827] border border-blue-500/20 rounded-lg p-6">
              <h3 className="text-xs font-mono text-blue-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                <Zap className="w-3.5 h-3.5" /> Catalysts
              </h3>
              {data.catalysts && data.catalysts.length > 0 ? (
                <ul className="space-y-2">
                  {data.catalysts.map((catalyst, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-blue-500 mt-1 text-xs">&#9679;</span>
                      <span className="text-sm text-[#94a3b8] leading-relaxed">
                        {catalyst}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[#64748b] text-sm">No catalysts identified</p>
              )}
            </div>
          </div>

          {/* Price Impact */}
          {data.price_impact && (
            <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
              <h3 className="text-xs text-[#64748b] uppercase tracking-wider mb-4">
                Price Impact Assessment
              </h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-[#0c1220] rounded-lg p-4 border border-[#1f2937]">
                  <span className="text-[10px] text-[#64748b] uppercase">Short Term</span>
                  <p className="text-sm text-[#f1f5f9] mt-1 capitalize">
                    {data.price_impact.short_term || 'N/A'}
                  </p>
                </div>
                <div className="bg-[#0c1220] rounded-lg p-4 border border-[#1f2937]">
                  <span className="text-[10px] text-[#64748b] uppercase">Medium Term</span>
                  <p className="text-sm text-[#f1f5f9] mt-1 capitalize">
                    {data.price_impact.medium_term || 'N/A'}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* News Feed */}
          <NewsFeed articles={data.articles || []} />

          {/* Analyst Consensus (from price_impact or mock) */}
          {data.analyst_consensus ? (
            <AnalystConsensus data={data.analyst_consensus} />
          ) : (
            <div className="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
              <h3 className="text-xs text-[#64748b] uppercase tracking-wider mb-4">
                Analyst Consensus
              </h3>
              <p className="text-[#64748b] text-sm text-center py-8">
                Analyst consensus data unavailable
              </p>
            </div>
          )}

          {/* Meta info */}
          {(data.article_count || data.timestamp || data.note) && (
            <div className="flex items-center justify-between text-[10px] font-mono text-[#64748b]">
              {data.article_count !== undefined && (
                <span>Articles analyzed: {data.article_count}</span>
              )}
              {data.timestamp && (
                <span>Last updated: {new Date(data.timestamp).toLocaleString()}</span>
              )}
              {data.note && <span>{data.note}</span>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
