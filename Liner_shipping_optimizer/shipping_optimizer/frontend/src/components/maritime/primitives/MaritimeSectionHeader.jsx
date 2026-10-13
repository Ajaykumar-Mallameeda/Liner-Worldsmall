/**
 * MaritimeSectionHeader
 * ---------------------
 * The eyebrow / title / subtitle triplet used at the top of every
 * maritime view. Replaces the ad-hoc headers in
 * MaritimeStatusView, MaritimeOpsView, MaritimeResilienceView,
 * MaritimeLiveView, MaritimeWeatherView, and MaritimeCongestionView.
 *
 * Pure presentational. The parent supplies the eyebrow, title,
 * optional subtitle, and optional right slot (e.g. a status pill
 * or a small "evaluated at" timestamp).
 */

export default function MaritimeSectionHeader({
  eyebrow = 'Operations · Maritime Intelligence',
  title,
  subtitle,
  right,
  size = 'lg', // lg | md
}) {
  const titleSize = size === 'md' ? 'text-xl' : 'text-2xl';
  return (
    <div className="flex items-start justify-between gap-4 mb-1">
      <div className="min-w-0">
        <div
          className="text-[10px] font-mono uppercase tracking-widest text-white/40"
          style={{ letterSpacing: '0.18em' }}
        >
          {eyebrow}
        </div>
        <h1
          className={`${titleSize} text-white/90 font-semibold mt-1 truncate`}
        >
          {title}
        </h1>
        {subtitle && (
          <div className="text-xs text-white/40 font-mono mt-1 max-w-3xl">
            {subtitle}
          </div>
        )}
      </div>
      {right && (
        <div className="flex items-center gap-2 pt-1 flex-shrink-0">
          {right}
        </div>
      )}
    </div>
  );
}
