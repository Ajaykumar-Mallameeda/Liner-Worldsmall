/**
 * Sparkline
 * ---------
 * Phase 11 - a compact numeric trace used in telemetry tiles.
 * Pure SVG. Honors prefers-reduced-motion for transitions.
 * When the values array is empty or non-numeric, the line is
 * rendered dim with a single dash.
 */

export default function Sparkline({
  values = [],
  width = 64,
  height = 18,
  stroke = 'var(--console-cyan)',
  fill = 'rgba(0, 212, 255, 0.08)',
  showDots = false,
  ariaLabel = 'sparkline',
}) {
  if (!Array.isArray(values) || values.length === 0) {
    return (
      <svg
        className="console-spark empty"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${ariaLabel} (no data)`}
      >
        <line
          x1="2" y1={height / 2} x2={width - 2} y2={height / 2}
          stroke="var(--console-text-faint)" strokeWidth="1" strokeDasharray="2 2"
        />
      </svg>
    );
  }
  const nums = values.map((v) => (typeof v === 'number' && isFinite(v) ? v : 0));
  const min = Math.min(...nums);
  const max = Math.max(...nums);
  const range = max - min || 1;
  const stepX = (width - 4) / Math.max(nums.length - 1, 1);
  const points = nums.map((v, i) => {
    const x = 2 + i * stepX;
    const y = height - 2 - ((v - min) / range) * (height - 4);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const path = points.join(' ');
  const areaPath = `M${points[0]} L${points.join(' L')} L${2 + (nums.length - 1) * stepX},${height - 2} L2,${height - 2} Z`;
  return (
    <svg
      className="console-spark"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={ariaLabel}
    >
      <path d={areaPath} fill={fill} stroke="none" />
      <polyline points={path} stroke={stroke} />
      {showDots && nums.map((_, i) => {
        const [x, y] = points[i].split(',').map(Number);
        return <circle key={i} cx={x} cy={y} r="1.2" fill={stroke} />;
      })}
    </svg>
  );
}
