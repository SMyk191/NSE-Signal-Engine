import { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { AlertTriangle, ChevronDown, TrendingUp, TrendingDown, Minus, ShieldCheck, BarChart3, Layers } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

/* ── Helpers ───────────────────────────────────────────────────── */
function pct(current, target) {
  if (!current || !target) return null;
  return (((target - current) / current) * 100).toFixed(1);
}

function fmt(v) {
  if (v == null) return '--';
  return `\u20B9${Number(v).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
}

/* ── Animated number hook ──────────────────────────────────────── */
function useCountUp(target, duration = 800) {
  const [value, setValue] = useState(0);
  const rafRef = useRef(null);

  useEffect(() => {
    if (target == null) return;
    const start = performance.now();
    const from = 0;
    const to = Number(target);

    function tick(now) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      setValue(from + (to - from) * eased);
      if (progress < 1) rafRef.current = requestAnimationFrame(tick);
    }

    rafRef.current = requestAnimationFrame(tick);
    return () => rafRef.current && cancelAnimationFrame(rafRef.current);
  }, [target, duration]);

  return value;
}

/* ── Confidence bar (thin, animated) ───────────────────────────── */
function ConfidenceBar({ value }) {
  const [width, setWidth] = useState(0);
  const displayVal = useCountUp(value, 1000);

  useEffect(() => {
    const timer = setTimeout(() => setWidth(Math.min(value, 100)), 100);
    return () => clearTimeout(timer);
  }, [value]);

  const color =
    value >= 70 ? '#22c55e' : value >= 45 ? '#f59e0b' : '#ef4444';

  return (
    <div className="flex flex-col items-end gap-1 min-w-[72px]">
      <span className="price-font text-xs font-semibold" style={{ color }}>
        {Math.round(displayVal)}% conf.
      </span>
      <div className="w-full h-[4px] rounded-full bg-[#1f2937] overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-1000 ease-out"
          style={{ width: `${width}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

/* ── Collapsible section ───────────────────────────────────────── */
function Collapsible({ label, sublabel, icon: Icon, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const contentRef = useRef(null);
  const [height, setHeight] = useState(0);

  useEffect(() => {
    if (contentRef.current) {
      setHeight(open ? contentRef.current.scrollHeight : 0);
    }
  }, [open]);

  // Re-measure on children change
  useEffect(() => {
    if (open && contentRef.current) {
      setHeight(contentRef.current.scrollHeight);
    }
  }, [children, open]);

  return (
    <div className="border-t border-[#1f2937]">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-2.5 px-5 py-3 group hover:bg-[#1a2332]/50 transition-colors"
      >
        {Icon && <Icon className="w-3.5 h-3.5 text-[#64748b] flex-shrink-0" />}
        <span className="text-[13px] font-medium text-[#94a3b8]">{label}</span>
        {sublabel && (
          <span className="text-[11px] text-[#64748b] truncate ml-1">{sublabel}</span>
        )}
        <ChevronDown
          className={`w-3.5 h-3.5 text-[#64748b] ml-auto flex-shrink-0 transition-transform duration-300 ${
            open ? 'rotate-180' : ''
          }`}
        />
      </button>
      <div
        className="overflow-hidden transition-[height] duration-300 ease-out"
        style={{ height }}
      >
        <div ref={contentRef}>
          {children}
        </div>
      </div>
    </div>
  );
}

/* ── Pill element for price targets ────────────────────────────── */
function Pill({ children, variant = 'neutral' }) {
  const styles = {
    green: 'bg-[#22c55e]/10 text-[#22c55e] border-[#22c55e]/10',
    red: 'bg-[#ef4444]/10 text-[#ef4444] border-[#ef4444]/10',
    blue: 'bg-[#3b82f6]/10 text-[#e2e8f0] border-[#3b82f6]/10',
    neutral: 'bg-[#1f2937]/60 text-[#94a3b8] border-[#1f2937]',
  };

  return (
    <span className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-full price-font text-[11px] font-semibold border ${styles[variant]} whitespace-nowrap`}>
      {children}
    </span>
  );
}

/* ── Stat block for options grid ───────────────────────────────── */
function StatBlock({ label, value, sub, color }) {
  return (
    <div className="bg-[#0c1220] rounded-lg px-3.5 py-3 border border-[#1f2937]/50">
      <div className="text-[10px] uppercase tracking-wider text-[#64748b] font-medium mb-1">
        {label}
      </div>
      <div className="price-font text-sm font-bold" style={{ color: color || '#f1f5f9' }}>
        {value ?? '--'}
      </div>
      {sub && (
        <div className="text-[10px] text-[#64748b] mt-0.5">{sub}</div>
      )}
    </div>
  );
}

/* ── Loading skeleton ──────────────────────────────────────────── */
function ActionPanelSkeleton() {
  return (
    <div className="card animate-fade-up overflow-hidden">
      {/* Row 1: Verdict */}
      <div className="p-5 flex items-center gap-4">
        <div className="flex items-center gap-3 flex-1">
          <div className="skeleton h-3 w-3 rounded-full" />
          <div className="skeleton h-5 w-14" />
          <div className="skeleton h-4 w-20 ml-2" />
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <div className="skeleton h-3 w-16" />
          <div className="skeleton h-1 w-[72px] rounded-full" />
        </div>
      </div>
      {/* Row 2: Pills */}
      <div className="px-5 pb-4 flex gap-2 overflow-hidden">
        <div className="skeleton h-7 w-36 rounded-full" />
        <div className="skeleton h-7 w-28 rounded-full" />
        <div className="skeleton h-7 w-28 rounded-full" />
        <div className="skeleton h-7 w-24 rounded-full" />
      </div>
      {/* Row 3: Collapsible placeholders */}
      <div className="border-t border-[#1f2937] px-5 py-3">
        <div className="skeleton h-3.5 w-48" />
      </div>
      <div className="border-t border-[#1f2937] px-5 py-3">
        <div className="skeleton h-3.5 w-40" />
      </div>
      {/* Row 4: Reasoning */}
      <div className="px-5 py-4 border-t border-[#1f2937] space-y-2">
        <div className="skeleton h-2.5 w-full" />
        <div className="skeleton h-2.5 w-4/5" />
        <div className="skeleton h-2.5 w-3/5" />
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   ActionPanel — The Trading Card
   ═══════════════════════════════════════════════════════════════════ */
export default function ActionPanel({ symbol }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!symbol) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    axios
      .get(`${API_BASE}/stocks/${symbol}/action`)
      .then((res) => {
        if (!cancelled) { setData(res.data); setLoading(false); }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err.response?.data?.detail ||
            'Option chain data unavailable \u2014 showing technical analysis only'
          );
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [symbol]);

  /* ── States ────────────────────────────────────────────────── */
  if (loading) return <ActionPanelSkeleton />;

  if (error && !data) {
    return (
      <div className="card animate-fade-up p-5">
        <div className="flex items-center gap-2.5">
          <AlertTriangle className="w-3.5 h-3.5 text-[#f59e0b] flex-shrink-0" />
          <p className="text-[12px] text-[#64748b]">{error}</p>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const {
    action = 'HOLD',
    confidence = 0,
    current_price: price,
    buy_range,
    sell_targets = [],
    stop_loss,
    supports = [],
    resistances = [],
    option_chain_analysis: option_chain = {},
    reasoning = [],
  } = data;

  const a = action.toUpperCase();

  const actionConfig = {
    BUY:  { color: '#22c55e', bg: '#22c55e', icon: TrendingUp,   label: 'BUY' },
    SELL: { color: '#ef4444', bg: '#ef4444', icon: TrendingDown,  label: 'SELL' },
    HOLD: { color: '#f59e0b', bg: '#f59e0b', icon: Minus,         label: 'HOLD' },
  };
  const ac = actionConfig[a] || actionConfig.HOLD;
  const ActionIcon = ac.icon;

  /* ── Option chain data ─────────────────────────────────────── */
  const {
    pcr, pcr_interpretation, max_pain, max_pain_interpretation,
    top_put_oi = [], top_call_oi = [], oi_buildup, iv_analysis,
  } = option_chain;

  const hasOptions = pcr != null || max_pain != null || top_put_oi.length > 0 || top_call_oi.length > 0;

  const oiOneLiner = [
    pcr != null ? `PCR ${Number(pcr).toFixed(2)}` : null,
    pcr_interpretation || null,
    oi_buildup || null,
  ].filter(Boolean).join(' \u00B7 ');

  /* ── Support & Resistance ──────────────────────────────────── */
  const levelCount = supports.length + resistances.length;

  const strengthOpacity = (str) => {
    const s = (str ?? '').toLowerCase();
    if (s === 'strong') return 'opacity-100';
    if (s === 'moderate') return 'opacity-70';
    return 'opacity-40';
  };

  /* ── Change % ──────────────────────────────────────────────── */
  const changePct = (buy_range?.low && price
    ? pct(buy_range.low, price)
    : null);
  const changeNeg = changePct != null && Number(changePct) < 0;

  /* ═══════════════════════════════════════════════════════════════
     RENDER
     ═══════════════════════════════════════════════════════════════ */
  return (
    <div className="card animate-fade-up overflow-hidden">

      {/* ── ROW 1: THE VERDICT ─────────────────────────────────── */}
      <div className="p-5 pb-4 flex items-center gap-4 stagger-1 animate-fade-up">
        {/* Left: Action signal */}
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <div className="flex items-center gap-2.5">
            {/* Colored dot with glow */}
            <span className="relative flex-shrink-0">
              <span
                className="block w-3 h-3 rounded-full"
                style={{ backgroundColor: ac.color }}
              />
              <span
                className="absolute inset-0 w-3 h-3 rounded-full animate-ping"
                style={{ backgroundColor: ac.color, opacity: 0.25 }}
              />
            </span>
            {/* Action label */}
            <span
              className="text-xl font-semibold tracking-tight"
              style={{ color: ac.color }}
            >
              {ac.label}
            </span>
          </div>

          {/* Stock name + price cluster */}
          <div className="flex flex-col ml-1 min-w-0">
            <span className="price-font text-lg font-bold text-[#f1f5f9] truncate">
              {fmt(price)}
            </span>
            <div className="flex items-center gap-2">
              {symbol && (
                <span className="text-[11px] font-medium text-[#64748b] uppercase tracking-wide">
                  {symbol}
                </span>
              )}
              {changePct != null && (
                <span
                  className="price-font text-[11px] font-semibold"
                  style={{ color: changeNeg ? '#ef4444' : '#22c55e' }}
                >
                  {changeNeg ? '\u25BC' : '\u25B2'} {changeNeg ? '' : '+'}{changePct}%
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Right: Confidence bar */}
        <ConfidenceBar value={confidence} />
      </div>

      {/* ── ROW 2: THE PLAY (price targets) ────────────────────── */}
      <div className="px-5 pb-4 stagger-2 animate-fade-up">
        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none -mx-1 px-1">
          {buy_range && (
            <>
              <Pill variant="green">
                Buy {fmt(buy_range.low)} &ndash; {fmt(buy_range.high)}
              </Pill>
              <span className="self-center w-px h-4 bg-[#1f2937] flex-shrink-0" />
            </>
          )}

          {sell_targets.map((t, i) => {
            const d = pct(price, t.target);
            return (
              <span key={i} className="contents">
                <Pill variant="blue">
                  T{i + 1} {fmt(t.target)}
                  {d != null && (
                    <span className="text-[#94a3b8]/60 ml-0.5">
                      ({d > 0 ? '+' : ''}{d}%)
                    </span>
                  )}
                </Pill>
                {i < sell_targets.length - 1 && (
                  <span className="self-center w-px h-4 bg-[#1f2937] flex-shrink-0" />
                )}
              </span>
            );
          })}

          {stop_loss != null && (
            <>
              <span className="self-center w-px h-4 bg-[#1f2937] flex-shrink-0" />
              <Pill variant="red">
                SL {fmt(stop_loss)}
                {price != null && (
                  <span className="text-[#ef4444]/60 ml-0.5">({pct(price, stop_loss)}%)</span>
                )}
              </Pill>
            </>
          )}
        </div>
      </div>

      {/* ── ROW 3: KEY LEVELS (collapsible) ────────────────────── */}
      {levelCount > 0 && (
        <Collapsible
          label="Support & Resistance"
          sublabel={`(${levelCount} levels)`}
          icon={Layers}
        >
          <div className="px-5 pb-4 pt-1">
            <div className="grid grid-cols-2 gap-3">
              {/* Support column */}
              <div>
                <div className="text-[10px] uppercase tracking-widest text-[#22c55e]/50 font-semibold mb-2">
                  Support
                </div>
                <div className="space-y-0.5">
                  {supports.map((s, i) => (
                    <div
                      key={i}
                      className={`flex items-center justify-between py-1.5 px-2.5 rounded-md bg-[#22c55e]/[0.04] ${strengthOpacity(s.strength)}`}
                    >
                      <span className="price-font text-[12px] font-semibold text-[#22c55e]">
                        {fmt(s.level)}
                      </span>
                      {s.source && (
                        <span className="text-[9px] text-[#64748b] uppercase tracking-wide">
                          {s.source}
                        </span>
                      )}
                    </div>
                  ))}
                  {supports.length === 0 && (
                    <span className="text-[11px] text-[#64748b]">No support levels</span>
                  )}
                </div>
              </div>

              {/* Resistance column */}
              <div>
                <div className="text-[10px] uppercase tracking-widest text-[#ef4444]/50 font-semibold mb-2">
                  Resistance
                </div>
                <div className="space-y-0.5">
                  {resistances.map((r, i) => (
                    <div
                      key={i}
                      className={`flex items-center justify-between py-1.5 px-2.5 rounded-md bg-[#ef4444]/[0.04] ${strengthOpacity(r.strength)}`}
                    >
                      <span className="price-font text-[12px] font-semibold text-[#ef4444]">
                        {fmt(r.level)}
                      </span>
                      {r.source && (
                        <span className="text-[9px] text-[#64748b] uppercase tracking-wide">
                          {r.source}
                        </span>
                      )}
                    </div>
                  ))}
                  {resistances.length === 0 && (
                    <span className="text-[11px] text-[#64748b]">No resistance levels</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </Collapsible>
      )}

      {/* ── ROW 4: OPTIONS INSIGHT (collapsible) ───────────────── */}
      {hasOptions && (
        <Collapsible
          label="Options Analysis"
          sublabel={oiOneLiner ? `\u2014 ${oiOneLiner}` : ''}
          icon={BarChart3}
        >
          <div className="px-5 pb-4 pt-1">
            {/* 2x2 stat grid */}
            <div className="grid grid-cols-2 gap-2.5">
              {pcr != null && (
                <StatBlock
                  label="Put/Call Ratio"
                  value={Number(pcr).toFixed(2)}
                  sub={pcr_interpretation}
                  color={
                    pcr_interpretation?.toLowerCase() === 'bullish' ? '#22c55e' :
                    pcr_interpretation?.toLowerCase() === 'bearish' ? '#ef4444' : '#f1f5f9'
                  }
                />
              )}
              {max_pain != null && (
                <StatBlock
                  label="Max Pain"
                  value={fmt(max_pain)}
                  sub={max_pain_interpretation}
                />
              )}
              {oi_buildup && (
                <StatBlock
                  label="OI Buildup"
                  value={oi_buildup}
                  color={
                    oi_buildup.toLowerCase().includes('long') ? '#22c55e' :
                    oi_buildup.toLowerCase().includes('short') ? '#ef4444' : '#f1f5f9'
                  }
                />
              )}
              {iv_analysis && (
                <StatBlock
                  label="IV Analysis"
                  value={iv_analysis}
                />
              )}
            </div>

            {/* OI distribution */}
            {(top_put_oi.length > 0 || top_call_oi.length > 0) && (
              <div className="grid grid-cols-2 gap-3 mt-3">
                {/* Puts */}
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-[#22c55e]/50 font-semibold mb-1.5">
                    Top Put OI
                  </div>
                  <div className="space-y-1">
                    {top_put_oi.map((s, i) => (
                      <div key={i} className="flex justify-between items-center price-font text-[11px]">
                        <span className="text-[#22c55e] font-semibold">{fmt(s.strike ?? s)}</span>
                        {s.oi != null && (
                          <span className="text-[#64748b]">{Number(s.oi).toLocaleString('en-IN')}</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
                {/* Calls */}
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-[#ef4444]/50 font-semibold mb-1.5">
                    Top Call OI
                  </div>
                  <div className="space-y-1">
                    {top_call_oi.map((s, i) => (
                      <div key={i} className="flex justify-between items-center price-font text-[11px]">
                        <span className="text-[#ef4444] font-semibold">{fmt(s.strike ?? s)}</span>
                        {s.oi != null && (
                          <span className="text-[#64748b]">{Number(s.oi).toLocaleString('en-IN')}</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </Collapsible>
      )}

      {/* ── Inline error (option chain unavailable) ────────────── */}
      {error && (
        <div className="px-5 py-2.5 border-t border-[#1f2937] flex items-center gap-2">
          <AlertTriangle className="w-3 h-3 text-[#f59e0b] flex-shrink-0" />
          <p className="text-[11px] text-[#64748b]">{error}</p>
        </div>
      )}

      {/* ── ROW 5: WHY (reasoning) ─────────────────────────────── */}
      {reasoning.length > 0 && (
        <div className="px-5 py-4 border-t border-[#1f2937] stagger-3 animate-fade-up">
          <ul className="columns-1 sm:columns-2 gap-x-6 space-y-1.5">
            {reasoning.map((r, i) => (
              <li
                key={i}
                className="flex items-start gap-2 text-[11px] text-[#94a3b8] leading-relaxed break-inside-avoid"
              >
                <span className="mt-[6px] w-1 h-1 rounded-full bg-[#64748b] flex-shrink-0" />
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── FOOTER: Disclaimer ─────────────────────────────────── */}
      <div className="px-5 py-2.5 border-t border-[#1f2937]/50">
        <p className="text-[9px] text-[#64748b]/60 leading-relaxed flex items-center gap-1.5">
          <ShieldCheck className="w-2.5 h-2.5 flex-shrink-0" />
          Algorithmic signal based on technical indicators &amp; option chain data. Not investment advice. Consult a SEBI-registered advisor.
        </p>
      </div>
    </div>
  );
}
