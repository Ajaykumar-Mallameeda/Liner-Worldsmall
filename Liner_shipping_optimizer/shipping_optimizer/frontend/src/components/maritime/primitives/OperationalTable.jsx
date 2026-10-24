/**
 * OperationalTable
 * ----------------
 * A small, dense, scrollable table primitive for the maritime
 * command center. Centralises the visual conventions used in
 * MaritimeWeatherView (records preview) and MaritimeCongestionView
 * (records table) so the rest of the dashboard can reuse a
 * single table style. Pure presentational.
 *
 * The table does not paginate or filter. The parent decides
 * what rows to show. `density` controls row padding; `maxHeight`
 * caps the scroll area.
 */

export default function OperationalTable({
  columns,           // [{ key, label, align?, width?, render? }]
  rows = [],         // array of plain objects
  emptyMessage = 'No records.',
  loading = false,
  density = 'normal', // compact | normal
  maxHeight = 320,
  rowKey = 'id',
  monospace = true,
}) {
  const padY = density === 'compact' ? 'py-1' : 'py-1.5';
  const fontClass = monospace ? 'font-mono' : '';
  const fontSize = monospace ? 'text-[12px]' : 'text-xs';
  return (
    <div
      className="overflow-x-auto"
      style={{ maxHeight, scrollbarWidth: 'thin' }}
    >
      <table className={`w-full ${fontClass} ${fontSize} text-white/60`}>
        <thead>
          <tr className="text-white/60 text-left">
            {columns.map((c) => (
              <th
                key={c.key}
                className={`${padY} pr-3 font-normal uppercase tracking-widest`}
                style={{
                  textAlign: c.align || 'left',
                  width: c.width,
                  fontSize: 12,
                  letterSpacing: '0.08em',
                }}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className={`${padY} text-center text-white/60`}
              >
                {loading ? 'Loading...' : emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((r, i) => (
              <tr
                key={r[rowKey] != null ? r[rowKey] : i}
                style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}
              >
                {columns.map((c) => {
                  const v = c.render ? c.render(r, i) : r[c.key];
                  return (
                    <td
                      key={c.key}
                      className={`${padY} pr-3`}
                      style={{
                        textAlign: c.align || 'left',
                        color: c.toneColor ? c.toneColor(r, v) : undefined,
                        minWidth: c.minWidth,
                      }}
                      title={typeof v === 'string' ? v : undefined}
                    >
                      {v == null ? '—' : v}
                    </td>
                  );
                })}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
