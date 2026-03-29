export default function SignalBadge({ score, size = 'md' }) {
  const getSignal = (s) => {
    if (s == null)
      return {
        label: 'N/A',
        classes: 'bg-[#1f2937] text-[#64748b] ring-1 ring-[#1f2937] font-medium',
      };
    if (s >= 60)
      return {
        label: 'STRONG BUY',
        classes: 'bg-emerald-500 text-white font-semibold shadow-sm shadow-emerald-500/25',
      };
    if (s >= 30)
      return {
        label: 'BUY',
        classes: 'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20 font-medium',
      };
    if (s >= -30)
      return {
        label: 'HOLD',
        classes: 'bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20 font-medium',
      };
    if (s >= -60)
      return {
        label: 'SELL',
        classes: 'bg-red-500/10 text-red-400 ring-1 ring-red-500/20 font-medium',
      };
    return {
      label: 'STRONG SELL',
      classes: 'bg-red-500 text-white font-semibold shadow-sm shadow-red-500/25',
    };
  };

  const signal = getSignal(score);

  const sizeClasses = {
    sm: 'text-[10px] px-2 py-0.5',
    md: 'text-xs px-2.5 py-1',
    lg: 'text-sm px-3 py-1.5',
  };

  return (
    <span
      className={`inline-flex items-center font-sans rounded-full tracking-wide ${signal.classes} ${sizeClasses[size]}`}
    >
      {signal.label}
    </span>
  );
}
