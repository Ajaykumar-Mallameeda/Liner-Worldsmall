/**
 * TelemetryMetric
 * ---------------
 * A single LABEL / VALUE / SUB row in a compact operational
 * typography stack. Mirrors the convention used inside the
 * existing maritime cards (MaritimeStatusCard, WeatherIntelligence,
 * CongestionIntelligence) but centralises the spacing and the
 * `tabular-nums` numeric alignment so tables and grids look
 * consistent across views.
 */

export default function TelemetryMetric({
  label,
  value,
  sub,
  align = 'left',
  tone = 'default', // default | emphasis | muted | warn | critical
  size = 'sm',      // sm | md
  valueNode,        // optional override (e.g. for a `<MaritimeStatusBadge>`)
  labelNode,        // optional override
}) {
  const tones = {
    default: { value: 'rgba(255,255,255,0.9)', label: 'rgba(255,255,255,0.4)' },
    emphasis: { value: '#00d4ff', label: 'rgba(255,255,255,0.5)' },
    muted: { value: 'rgba(255,255,255,0.6)', label: 'rgba(255,255,255,0.35)' },
    warn: { value: '#f59e0b', label: 'rgba(255,255,255,0.4)' },
    critical: { value: '#ef4444', label: 'rgba(255,255,255,0.4)' },
  };
  const palette = tones[tone] || tones.default;
  const valueSize = size === 'md' ? 14 : size === 'lg' ? 18 : 12;
  const labelSize = size === 'md' ? 10 : size === 'lg' ? 11 : 9;
  return (
    <div
      className="flex flex-col gap-0.5 min-w-0"
      style={{ textAlign: align }}
    >
      <div
        className="font-mono uppercase tracking-widest"
        style={{ color: palette.label, fontSize: labelSize, letterSpacing: '0.08em' }}
      >
        {labelNode || label}
      </div>
      {valueNode || (
        <div
          className="font-mono tabular-nums truncate"
          style={{ color: palette.value, fontSize: valueSize }}
          title={typeof value === 'string' ? value : undefined}
        >
          {value ?? '—'}
        </div>
      )}
      {sub != null && (
        <div
          className="font-mono truncate"
          style={{ color: 'rgba(255,255,255,0.35)', fontSize: 12 }}
          title={typeof sub === 'string' ? sub : undefined}
        >
          {sub}
        </div>
      )}
    </div>
  );
}
