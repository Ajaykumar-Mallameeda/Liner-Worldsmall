/**
 * InspectBanner
 * -------------
 * Shown while a page displays an iteration other than the run's selected one, so the
 * figures on the page are never mistaken for the final plan. Renders nothing otherwise.
 */

const pad2 = (n) => String(n).padStart(2, '0');

export default function InspectBanner({ inspecting, selected, onReset }) {
  if (inspecting == null || inspecting === selected) return null;
  return (
    <div className="cx-inspect-banner" role="status">
      <span>
        Inspecting <b>iter {pad2(inspecting)}</b>. The run selected <b>iter {selected != null ? pad2(selected) : '—'}</b>; iteration figures on this page are for iter {pad2(inspecting)}.
      </span>
      <button type="button" onClick={onReset}>Back to selected</button>
    </div>
  );
}
