/**
 * MaritimeRoutingImpactView
 * -------------------------
 * Phase 8 — explanatory view of how maritime intelligence flowed
 * into the optimizer. Single fetch:
 *
 *   GET /api/maritime/routing-impact
 *
 * The endpoint reads the additive `maritime_intelligence` key
 * that the Phase 7 IP-5 integration writes into
 * pipeline_output.json and classifies each feature as
 *
 *   applied | rejected | stale | fallback_used | baseline
 *
 * This view is purely explanatory. It never alters an
 * optimizer decision, never reaches an external provider, and
 * never mutates pipeline state. When the endpoint reports
 * `available: false` (e.g. maritime was disabled in the run),
 * the view degrades to a quiet "baseline retained" panel.
 *
 * Phase 9 — Feature E: the per-feature cards now also show
 * the additive explainability fields
 *   - consumed               (was the feature actually consumed?)
 *   - affected_input         (which optimizer input was modified?)
 *   - final_route_affected   (was the final route changed?)
 * and the headline panel surfaces a top-level
 *   - explainability.wording
 * so the operator can see at a glance whether maritime
 * intelligence is advisory (input changed) or deterministic
 * (route changed). Per T0-1, final_route_affected is always
 * false in this release.
 */

import { useEffect, useState } from 'react';
import MaritimeSectionHeader from '../components/maritime/primitives/MaritimeSectionHeader.jsx';
import IntelligenceSurfaceHeader from '../components/maritime/IntelligenceSurfaceHeader.jsx';
import ProvenanceStrip from '../components/maritime/ProvenanceStrip.jsx';
import IntelligencePanel from '../components/maritime/primitives/IntelligencePanel.jsx';
import TelemetryMetric from '../components/maritime/primitives/TelemetryMetric.jsx';
import ConfidenceIndicator from '../components/maritime/primitives/ConfidenceIndicator.jsx';
import DataFreshnessBadge from '../components/maritime/primitives/DataFreshnessBadge.jsx';
import ProviderStatusRow from '../components/maritime/primitives/ProviderStatusRow.jsx';

const POLL_INTERVAL_MS = 30000;

// Per-feature colour/label map. Five states are documented in the
// brief; "baseline" is the same neutral as "unknown" so the
// dashboard can collapse them onto the same visual without
// pretending they are the same status.
const FEATURE_STATE_COLOR = {
  applied: '#10b981',
  rejected: '#f59e0b',
  stale: '#f59e0b',
  fallback_used: '#94a3b8',
  baseline: '#64748b',
};
const FEATURE_STATE_LABEL = {
  applied: 'APPLIED',
  rejected: 'REJECTED',
  stale: 'STALE',
  fallback_used: 'FALLBACK',
  baseline: 'BASELINE',
};

const FEATURE_META = {
  traffic: {
    title: 'Traffic',
    subtitle: 'Phase 1/2 EMODnet vessel-density feature (informational).',
  },
  port: {
    title: 'Port',
    subtitle: 'Phase 2 NOAA port-intelligence feature (informational).',
  },
  weather: {
    title: 'Weather',
    subtitle: 'Phase 5 weather speed factor — forwarded into IP-2 (fuel cost).',
  },
  congestion: {
    title: 'Congestion',
    subtitle: 'Phase 6 per-port congestion override — forwarded into IP-3 (MILP capacity).',
  },
};

function Pill({ value }) {
  const color = FEATURE_STATE_COLOR[value] || FEATURE_STATE_COLOR.baseline;
  const label = FEATURE_STATE_LABEL[value] || value?.toUpperCase() || 'UNKNOWN';
  return (
    <span
      className="maritime-state-change text-[12px] font-mono uppercase tracking-widest px-2 py-1 rounded"
      style={{
        background: `${color}1a`,
        color,
        border: `1px solid ${color}33`,
      }}
    >
      {label}
    </span>
  );
}

function fmtTimestamp(iso) {
  if (!iso) return '—';
  try {
    return iso.replace('T', ' ').replace('Z', ' UTC').slice(0, 19);
  } catch (_) {
    return iso;
  }
}

function primaryValue(feature) {
  if (feature.feature === 'weather') {
    return feature.speed_factor != null ? Number(feature.speed_factor).toFixed(3) : '—';
  }
  if (feature.feature === 'congestion') {
    if (feature.score == null) return '—';
    return `${Number(feature.score).toFixed(2)} (${feature.level || '—'})`;
  }
  // traffic / port are informational; show record count when
  // surfaced via diagnostics, otherwise the confidence proxy.
  if (feature.diagnostics && feature.diagnostics.record_count != null) {
    return `${feature.diagnostics.record_count} rec`;
  }
  return feature.confidence != null ? Number(feature.confidence).toFixed(2) : '—';
}

function primaryLabel(feature) {
  if (feature.feature === 'weather') return 'speed factor';
  if (feature.feature === 'congestion') return 'max score';
  return 'snapshot';
}

// Phase 9 — Feature E. Per-feature explainability micro-strip.
// Renders consumed / affected_input / final_route_affected as a
// small 3-column row. All values originate from the additive
// explainability fields in the per-feature payload returned by
// the endpoint. NEVER fabricates a value.
function ExplainabilityStrip({ feature }) {
  const consumed = feature && feature.consumed === true;
  const inputName = feature && feature.affected_input ? feature.affected_input : null;
  const routeAffected = feature && feature.final_route_affected === true;

  const consumedColor = consumed ? '#10b981' : '#94a3b8';
  const inputColor = inputName ? '#38bdf8' : '#94a3b8';
  // Per T0-1, the final route is deterministically selected by
  // iteration_selection, so routeAffected is always false in
  // this release. We still render the row so the operator can
  // see that the invariant is being respected.
  const routeColor = '#94a3b8';

  return (
    <div
      className="mt-2 pt-2 grid grid-cols-3 gap-2 text-[12px] font-mono uppercase tracking-widest"
      style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}
      role="group"
      aria-label="Feature explainability"
    >
      <div className="flex flex-col gap-0.5 min-w-0">
        <div className="text-white/35">consumed</div>
        <div className="flex items-center gap-1 truncate" style={{ color: consumedColor }}>
          <span
            className="inline-block w-1.5 h-1.5 rounded-full"
            style={{ background: consumedColor, flexShrink: 0 }}
            aria-hidden="true"
          />
          <span className="truncate">{consumed ? 'yes' : 'no'}</span>
        </div>
      </div>
      <div className="flex flex-col gap-0.5 min-w-0">
        <div className="text-white/35">input</div>
        <div
          className="truncate"
          style={{ color: inputColor }}
          title={inputName || 'no input affected'}
        >
          {inputName || '—'}
        </div>
      </div>
      <div className="flex flex-col gap-0.5 min-w-0">
        <div className="text-white/35">route</div>
        <div
          className="truncate"
          style={{ color: routeColor }}
          title="T0-1 deterministic iteration selection"
        >
          {routeAffected ? 'changed' : 'deterministic'}
        </div>
      </div>
    </div>
  );
}

// Phase 9 — Feature E. Top-level explainability headline.
// Surfaces the endpoint's `explainability` rollup so the
// operator can see at a glance whether any optimization input
// was changed by maritime intelligence. Never claims causal
// impact on the final route.
function ExplainabilityHeadline({ explainability }) {
  if (!explainability || typeof explainability !== 'object') {
    return null;
  }
  const attached = explainability.features_attached ?? 0;
  const consumed = explainability.features_consumed ?? 0;
  const inputsAffected = explainability.inputs_affected === true;
  const routeAffected = explainability.route_affected === true;
  const wording = explainability.wording || '';

  return (
    <div
      className="mt-3 pt-3 grid gap-2"
      style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
      role="group"
      aria-label="Routing-impact explainability"
    >
      <div className="text-[12px] font-mono uppercase tracking-widest text-white/60">
        Explainability
      </div>
      <div className="text-[12px] font-mono text-white/75 leading-relaxed">
        {wording}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-[12px] font-mono">
        <TelemetryMetric
          label="Attached"
          value={attached}
          tone={attached > 0 ? 'emphasis' : 'muted'}
          size="sm"
        />
        <TelemetryMetric
          label="Consumed"
          value={consumed}
          tone={consumed > 0 ? 'emphasis' : 'muted'}
          size="sm"
        />
        <TelemetryMetric
          label="Inputs affected"
          value={inputsAffected ? 'yes' : 'no'}
          tone={inputsAffected ? 'emphasis' : 'muted'}
          size="sm"
        />
        <TelemetryMetric
          label="Route affected"
          value={routeAffected ? 'yes' : 'no'}
          tone={routeAffected ? 'warn' : 'muted'}
          sub="T0-1 invariant"
          size="sm"
        />
      </div>
    </div>
  );
}

export default function MaritimeRoutingImpactView() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const resp = await fetch('/api/maritime/routing-impact');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const j = await resp.json();
        if (cancelled) return;
        setData(j);
      } catch (_) {
        if (!cancelled) {
          setData({
            available: false,
            reason: 'request_failed',
            features: [],
            summary: {
              applied: 0, rejected: 0, stale: 0,
              fallback_used: 0, baseline_retained: 0,
            },
            explainability: {
              available: false,
              features_attached: 0,
              features_consumed: 0,
              inputs_affected: false,
              route_affected: false,
              wording:
                'Maritime routing-impact endpoint unreachable; the dashboard fell back to a no-data view. No optimizer state is affected.',
            },
            explanation:
              'Could not reach /api/maritime/routing-impact. The endpoint is read-only; this view is purely informational.',
          });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    const t = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  const available = data?.available === true;
  const summary = data?.summary || {};
  const features = data?.features || [];
  const sourcesUsed = data?.sources_used || [];
  const sourcesMissing = data?.sources_missing || [];

  return (
    <div className="p-6 flex flex-col gap-5">
      <IntelligenceSurfaceHeader
        eyebrow="Operations · Maritime Intelligence"
        title="Routing Impact"
        subtitle="How maritime intelligence flowed into the optimizer. The dashboard reads the Phase 7 IP-5 block; no policy is altered here."
        overallState={available ? "applied" : (data ? "available" : "unknown")}
        evaluatedAt={data?.retrieved_at}
        right={
          available ? (
            <Pill value="applied" />
          ) : (
            <Pill value="baseline" />
          )
        }
      />

      {/* Headline + provenance strip */}
      <IntelligencePanel
        title="Run summary"
        density="compact"
      >
        <div className="text-[12px] text-white/80 font-mono leading-relaxed mb-3">
          {data?.explanation || 'Loading…'}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <TelemetryMetric
            label="Snapshot"
            value={fmtTimestamp(data?.retrieved_at)}
            sub={data?.snapshot_id ? `id ${data.snapshot_id.slice(0, 12)}…` : '—'}
            size="md"
          />
          <TelemetryMetric
            label="Duration"
            value={
              data?.duration_ms != null
                ? `${Number(data.duration_ms).toFixed(0)} ms`
                : '—'
            }
            sub={data?.budget_exceeded ? 'budget exceeded' : 'within budget'}
            tone={data?.budget_exceeded ? 'warn' : 'default'}
            size="md"
          />
          <TelemetryMetric
            label="Sources used"
            value={sourcesUsed.length}
            tone="emphasis"
            size="md"
          />
          <TelemetryMetric
            label="Sources missing"
            value={sourcesMissing.length}
            tone={sourcesMissing.length > 0 ? 'warn' : 'muted'}
            size="md"
          />
        </div>
        <ExplainabilityHeadline explainability={data?.explainability} />
      </IntelligencePanel>

      {/* Summary strip */}
      <IntelligencePanel
        title="Feature impact summary"
        density="compact"
      >
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <TelemetryMetric
            label="Applied"
            value={summary.applied ?? 0}
            tone="emphasis"
            size="md"
          />
          <TelemetryMetric
            label="Rejected"
            value={summary.rejected ?? 0}
            tone={summary.rejected > 0 ? 'warn' : 'muted'}
            size="md"
          />
          <TelemetryMetric
            label="Stale"
            value={summary.stale ?? 0}
            tone={summary.stale > 0 ? 'warn' : 'muted'}
            size="md"
          />
          <TelemetryMetric
            label="Fallback used"
            value={summary.fallback_used ?? 0}
            tone="muted"
            size="md"
          />
          <TelemetryMetric
            label="Baseline retained"
            value={summary.baseline_retained ?? 0}
            tone="muted"
            size="md"
          />
        </div>
      </IntelligencePanel>

      {/* Per-feature cards */}
      <IntelligencePanel
        title="Per-feature impact"
        subtitle="Each feature is classified independently. The 'reason' is the operator-readable explanation returned by the endpoint."
        density="comfortable"
      >
        {loading ? (
          <div
            className="rounded-lg p-3 animate-pulse"
            style={{
              background: 'rgba(2,12,24,0.5)',
              border: '1px solid rgba(148,163,184,0.12)',
            }}
          >
            <div className="h-3 w-32 bg-white/10 rounded mb-2" />
            <div className="h-3 w-24 bg-white/10 rounded" />
          </div>
        ) : features.length === 0 ? (
          <div className="text-[12px] text-white/35 font-mono">
            No features were attached in this run.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {features.map((f) => {
              const meta = FEATURE_META[f.feature] || {};
              return (
                <div
                  key={f.feature}
                  className="rounded-xl px-4 py-3"
                  style={{
                    background: 'rgba(2,12,24,0.55)',
                    border: `1px solid ${FEATURE_STATE_COLOR[f.state] || '#64748b'}33`,
                  }}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <div>
                      <div className="text-[12px] text-white/85 font-mono uppercase tracking-widest">
                        {meta.title || f.feature}
                      </div>
                      {meta.subtitle && (
                        <div className="text-[12px] text-white/60 font-mono mt-0.5">
                          {meta.subtitle}
                        </div>
                      )}
                    </div>
                    <Pill value={f.state} />
                  </div>
                  <div className="text-[12px] text-white/65 font-mono leading-relaxed mt-1.5">
                    {f.reason}
                  </div>
                  <div
                    className="mt-2 pt-2 grid grid-cols-2 gap-2"
                    style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}
                  >
                    <TelemetryMetric
                      label={primaryLabel(f)}
                      value={primaryValue(f)}
                      size="sm"
                    />
                    <TelemetryMetric
                      label="Confidence"
                      valueNode={
                        <ConfidenceIndicator
                          value={f.confidence}
                          showBar
                          size="sm"
                        />
                      }
                    />
                  </div>
                  <div className="mt-2 flex items-center justify-between text-[12px] font-mono text-white/60">
                    <DataFreshnessBadge ageSeconds={f.freshness_seconds} />
                    {f.synthetic != null && (
                      <span
                        className="uppercase tracking-widest"
                        title="When synthetic is true, the record is a bundled fixture, not a real-world observation."
                      >
                        {f.synthetic ? 'synthetic' : 'derived'}
                      </span>
                    )}
                  </div>
                  <ExplainabilityStrip feature={f} />
                </div>
              );
            })}
          </div>
        )}
      </IntelligencePanel>

      {/* Sources */}
      <IntelligencePanel
        title="Sources"
        subtitle="What the IP-1 attach actually used vs. what was unavailable in this run."
        density="compact"
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {sourcesUsed.length === 0 && sourcesMissing.length === 0 ? (
            <div className="text-[12px] text-white/35 font-mono">
              No source rollup available.
            </div>
          ) : (
            <>
              {sourcesUsed.map((s) => (
                <ProviderStatusRow
                  key={`u-${s}`}
                  name={s}
                  label={s}
                  status="available"
                  license="attached"
                />
              ))}
              {sourcesMissing.map((s) => (
                <ProviderStatusRow
                  key={`m-${s}`}
                  name={s}
                  label={s}
                  status="unavailable"
                  license="missing"
                />
              ))}
            </>
          )}
        </div>
      </IntelligencePanel>

      {/* Diagnostics */}
      {data?.diagnostics && Object.keys(data.diagnostics || {}).length > 0 && (
        <IntelligencePanel
          title="Diagnostics"
          subtitle="Raw attach diagnostics surfaced from IP-1 (read-only)."
          density="compact"
        >
          <pre
            className="text-[12px] font-mono text-white/55 overflow-x-auto max-h-48 p-2 rounded"
            style={{
              background: 'rgba(2,12,24,0.6)',
              border: '1px solid rgba(255,255,255,0.04)',
            }}
          >
            {JSON.stringify(data.diagnostics, null, 2)}
          </pre>
        </IntelligencePanel>
      )}

      {/* Disabled / unavailable hint */}
      {!available && !loading && (
        <IntelligencePanel
          title="No maritime impact recorded"
          density="compact"
        >
          <div className="text-[12px] text-white/35 font-mono leading-relaxed">
            The current run did not attach maritime features to the
            optimizer. This is the expected state when
            <code className="mx-1 px-1 rounded"
              style={{
                background: 'rgba(255,255,255,0.06)',
                color: 'rgba(255,255,255,0.7)',
              }}
            >MARITIME_INTELLIGENCE_ENABLED=0</code>
            or when no maritime snapshots are on disk. The optimizer
            used the pre-maritime baseline path; no decision was
            influenced by maritime intelligence in this run.
          </div>
        </IntelligencePanel>
      )}

      <div className="text-[12px] text-white/60 font-mono leading-relaxed max-w-3xl">
        Phase 8 routing-impact view, Phase 9 explainability overlay.
        The endpoint
        <code className="mx-1">/api/maritime/routing-impact</code> reads
        the additive <code className="mx-1">maritime_intelligence</code>
        block in <code className="mx-1">pipeline_output.json</code> (the
        IP-5 output) and now also reports, per feature, whether it
        was consumed, which optimizer input it modified, and whether
        the final route was affected. Per the T0-1 invariant, the
        final route is deterministically selected by
        <code className="mx-1">iteration_selection</code>; the
        explainability strip shows <em>deterministic</em> in the
        route column for every feature in this release. No optimizer
        contract is altered, and no existing test fixture is
        invalidated.
      </div>

      <ProvenanceStrip
        source="pipeline_output.json"
        sourceStatus={data ? (data.reason || (data.available ? "available" : "offline")) : "unknown"}
        timestamp={data?.retrieved_at || data?.evaluated_at}
        quality={null}
        attribution="Derived from orchestrator return dict (Phase 7 IP-5 block)"
        license="internal artifact"
        snapshotId={data?.snapshot_id}
      />
    </div>
  );
}
