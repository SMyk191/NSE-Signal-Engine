import SignalBadge from './SignalBadge';

export default function ScoreGauge({ score = 0, size = 140 }) {
  const clampedScore = Math.max(-100, Math.min(100, score));

  // Gauge geometry — 180° semicircle arc
  const strokeWidth = 8;
  const padding = 12;
  const radius = (size - padding * 2 - strokeWidth) / 2;
  const cx = size / 2;
  const cy = padding + radius + strokeWidth / 2;

  // Arc background path (left to right, 180°)
  const arcPath = `M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`;

  // Score to position on arc: -100 = left (180°), 100 = right (0°)
  const normalized = (clampedScore + 100) / 200; // 0 to 1
  const angle = Math.PI * (1 - normalized); // π to 0
  const dotX = cx + radius * Math.cos(angle);
  const dotY = cy - radius * Math.sin(angle);

  const getScoreColor = (s) => {
    if (s >= 60) return '#22c55e';
    if (s >= 30) return '#4ade80';
    if (s >= -30) return '#f59e0b';
    if (s >= -60) return '#f87171';
    return '#ef4444';
  };

  const scoreColor = getScoreColor(clampedScore);
  const gradientId = `gauge-arc-${size}`;
  const glowId = `dot-glow-${size}`;

  // SVG total height: arc area + score text + badge spacing
  const svgHeight = cy + 6;

  return (
    <div className="flex flex-col items-center" style={{ height: size * 0.86 }}>
      <svg
        width={size}
        height={svgHeight}
        viewBox={`0 0 ${size} ${svgHeight}`}
      >
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#ef4444" />
            <stop offset="30%" stopColor="#f59e0b" />
            <stop offset="70%" stopColor="#4ade80" />
            <stop offset="100%" stopColor="#22c55e" />
          </linearGradient>
          <filter id={glowId} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Background arc */}
        <path
          d={arcPath}
          fill="none"
          stroke="#1f2937"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />

        {/* Gradient arc */}
        <path
          d={arcPath}
          fill="none"
          stroke={`url(#${gradientId})`}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />

        {/* Indicator dot with glow */}
        <circle
          cx={dotX}
          cy={dotY}
          r={4}
          fill="white"
          filter={`url(#${glowId})`}
          style={{ filter: `drop-shadow(0 0 6px ${scoreColor})` }}
        />
      </svg>

      {/* Score number */}
      <div
        className="price-font tabular-nums font-bold leading-none -mt-1"
        style={{
          fontSize: size * 0.19,
          color: scoreColor,
        }}
      >
        {clampedScore > 0 ? '+' : ''}{clampedScore.toFixed(0)}
      </div>

      {/* Signal badge */}
      <div className="mt-1.5">
        <SignalBadge score={clampedScore} size="sm" />
      </div>
    </div>
  );
}
