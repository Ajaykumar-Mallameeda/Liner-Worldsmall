/**
 * MaritimeLayerToggle
 * -------------------
 * A small button that can be toggled on/off. Used by the command
 * center to filter the visible sources and by the existing
 * maritime views to surface their layer state. Honors
 * `prefers-reduced-motion` (the only motion is a 150ms color
 * transition, which the global reduced-motion guard in
 * styles/index.css collapses to 0.001ms).
 */

export default function MaritimeLayerToggle({
  active = false,
  onClick,
  label,
  count,
  icon,
  size = 'sm',
}) {
  const pad =
    size === 'md' ? 'px-2.5 py-1' :
      size === 'lg' ? 'px-3 py-1.5' :
        'px-2 py-0.5';
  const font = size === 'lg' ? 'text-[12px]' : 'text-[12px]';
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`maritime-state-change ${pad} ${font} font-mono uppercase tracking-widest rounded inline-flex items-center gap-1.5`}
      style={{
        background: active
          ? 'rgba(0,212,255,0.12)'
          : 'rgba(255,255,255,0.04)',
        color: active ? '#00d4ff' : 'rgba(255,255,255,0.55)',
        border: active
          ? '1px solid rgba(0,212,255,0.30)'
          : '1px solid rgba(255,255,255,0.08)',
      }}
    >
      {icon && <span aria-hidden="true">{icon}</span>}
      <span>{label}</span>
      {count != null && (
        <span
          className="tabular-nums"
          style={{ opacity: 0.7 }}
        >
          {count}
        </span>
      )}
    </button>
  );
}
