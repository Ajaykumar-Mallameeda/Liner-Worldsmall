/**
 * OperationalEmptyState
 * ---------------------
 * Phase 10 — uniform empty / offline / stale / no-snapshot
 * state for any intelligence view. Each state has:
 *
 *   - a short mono-caps label
 *   - a one-line prose title
 *   - a hint explaining what the user can do (or, more often,
 *     what the system is doing — and that it is honest)
 *
 * The intent is to never render a blank card. A user who
 * navigates to a view should always see why they are looking
 * at an empty surface, and what would change it.
 */
import { useMemo } from 'react';
import MaritimeStatusBadge from './primitives/MaritimeStatusBadge.jsx';

const VARIANTS = {
  loading: {
    label: 'loading',
    title: 'Reading local snapshot…',
    hint:
      'The dashboard reads only the local snapshot store. The first request usually completes in under a second; subsequent polls happen every 15 seconds.',
    state: 'checking',
  },
  no_data: {
    label: 'no data',
    title: 'No snapshot available for this layer',
    hint:
      'This layer is enabled, but the local snapshot directory is empty. The dashboard will start showing live intelligence as soon as the orchestrator publishes a snapshot.',
    state: 'unknown',
  },
  offline: {
    label: 'offline',
    title: 'Upstream source is offline',
    hint:
      'The system has tried to read a snapshot but the source is not reachable. The dashboard will keep trying and will surface real data the moment it is published.',
    state: 'offline',
  },
  stale: {
    label: 'stale',
    title: 'Data is older than the freshness policy',
    hint:
      'A snapshot is on disk but its timestamp is past the freshness window. The dashboard shows it as STALE rather than LIVE so it cannot be mistaken for a fresh read.',
    state: 'stale',
  },
  disabled: {
    label: 'disabled',
    title: 'Maritime intelligence is disabled',
    hint:
      'Set MARITIME_INTELLIGENCE_ENABLED=1 (and any sub-flags) and restart the backend. Until then, the dashboard reads only the local snapshot store and reports the master flag explicitly.',
    state: 'disabled',
  },
  synthetic: {
    label: 'synthetic',
    title: 'Synthetic fixture in use',
    hint:
      'No upstream data is available, so the orchestrator has published a labelled synthetic snapshot. The dashboard marks every record as synthetic; nothing here is presented as a production read.',
    state: 'unknown',
  },
  degraded: {
    label: 'degraded',
    title: 'Partial intelligence available',
    hint:
      'At least one input is missing or stale. The dashboard surfaces the available signal and reports each missing input in the per-source row.',
    state: 'degraded',
  },
  error: {
    label: 'error',
    title: 'Snapshot read failed',
    hint:
      'The backend could not complete this query. The dashboard never fabricates a value; check the backend log for the underlying reason.',
    state: 'error',
  },
};

export default function OperationalEmptyState({
  variant = 'no_data',
  title,
  hint,
  statusBadge = true,
}) {
  const v = VARIANTS[variant] || VARIANTS.no_data;
  const useTitle = title || v.title;
  const useHint = hint || v.hint;
  return (
    <div className="mc-empty" role="status" aria-live="polite">
      <div className="flex items-center gap-3">
        <span className="label">{v.label}</span>
        {statusBadge && <MaritimeStatusBadge value={v.state} size="sm" />}
      </div>
      <div className="title">{useTitle}</div>
      <div className="hint">{useHint}</div>
    </div>
  );
}
