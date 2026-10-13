/**
 * ConfidenceIndicator
 * -------------------
 * Compact confidence pill: numeric value + a thin progress bar
 * with green / amber / red thresholds (>=0.7 green, 0.4–0.7 amber,
 * <0.4 red). Wraps the existing `ProgressBar` primitive so the
 * dashboard does not duplicate the bar widget.
 *
 * Pure presentational. Accepts a number, a string ("0.91"), or
 * null. A null input renders a quiet "—" placeholder so callers
 * don't have to special-case missing confidence.
 */

import ProgressBar from '../../common/ProgressBar.jsx';

function normalize(v) {
  if (v == null) return null;
  if (typeof v === 'number') return v;
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : null;
}

function thresholdColor(v) {
  if (v == null) return '#64748b';
  if (v >= 0.7) return '#10b981';
  if (v >= 0.4) return '#f59e0b';
  return '#ef4444';
}

export default function ConfidenceIndicator({
  value,
  showBar = true,
  label = 'Q',
  size = 'sm',
}) {
  const v = normalize(value);
  const color = thresholdColor(v);
  const fontSize = size === 'lg' ? 11 : size === 'md' ? 10 : 9;
  return (
    <span className="inline-flex items-center gap-2 min-w-0">
      <span
        className="font-mono uppercase tracking-widest"
        style={{ color: 'rgba(255,255,255,0.45)', fontSize }}
      >
        {label}
      </span>
      <span
        className="font-mono tabular-nums"
        style={{ color, fontSize: size === 'lg' ? 12 : 11 }}
        title={v != null ? `confidence ${v.toFixed(2)}` : 'no confidence value'}
      >
        {v != null ? v.toFixed(2) : '—'}
      </span>
      {showBar && v != null && (
        <span
          className="inline-block"
          style={{ width: size === 'lg' ? 64 : 48 }}
        >
          <ProgressBar value={v * 100} max={100} color={color} animated={false} />
        </span>
      )}
    </span>
  );
}
