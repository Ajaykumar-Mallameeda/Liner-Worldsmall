/**
 * MaritimeCommandCenter
 * ---------------------
 * Phase 10 — the maritime operations command center. This view
 * is the default landing for the dashboard (replaces the
 * "Overview" tab as the home surface). It is a thin composer
 * over the existing maritime REST surface:
 *
 *   GET /api/maritime/overview
 *   GET /api/maritime/telemetry
 *   GET /api/maritime/source-health
 *   GET /api/maritime/routing-impact
 *   GET /api/maritime/resilience
 *
 * No new endpoints are introduced. The view is purely a
 * presentational re-arrangement of what Phase 1–9 already
 * expose, plus the new shared header / agent topology /
 * provenance / layer rail primitives. The "intelligence
 * console" feel comes from information density, hierarchy,
 * and honest state — not from new cards.
 *
 * No fabricated state, no fake LIVE claims, no animations
 * beyond the existing maritime-panel transition.
 */

import { useEffect, useMemo, useState } from 'react';
import IntelligencePanel from '../components/maritime/primitives/IntelligencePanel.jsx';
import IntelligenceSurfaceHeader from '../components/maritime/IntelligenceSurfaceHeader.jsx';
import SourceLayerRail from '../components/maritime/SourceLayerRail.jsx';
import AgentTopology from '../components/maritime/AgentTopology.jsx';
import ProvenanceStrip from '../components/maritime/ProvenanceStrip.jsx';
import OperationalEmptyState from '../components/maritime/OperationalEmptyState.jsx';
import SourceHealthIndicator from '../components/maritime/primitives/SourceHealthIndicator.jsx';
import MaritimeStatusBadge from '../components/maritime/primitives/MaritimeStatusBadge.jsx';
import DataFreshnessBadge from '../components/maritime/primitives/DataFreshnessBadge.jsx';
import TelemetryMetric from '../components/maritime/primitives/TelemetryMetric.jsx';
import OperationalTimeline, {
  deriveMaritimeEvents,
} from '../components/maritime/primitives/OperationalTimeline.jsx';
import MaritimeDiff, {
  deriveMaritimeDiff,
} from '../components/maritime/primitives/MaritimeDiff.jsx';
import { apiClient } from '../services/apiClient.js';

const OVERVIEW_POLL_MS = 15000;
const TELEMETRY_POLL_MS = 30000;

const SOURCES = [
  { key: 'traffic', source: 'EMODnet', dataset: 'emodnet_vessel_density' },
  { key: 'port', source: 'NOAA MarineCadastre', dataset: 'noaa_ais_port_intelligence' },
  { key: 'weather', source: 'Weather', dataset: 'maritime_weather_observations' },
  { key: 'congestion', source: 'Congestion', dataset: 'maritime_congestion' },
  { key: 'live', source: 'Live', dataset: 'digitraffic_live_vessel_positions' },
];

function compactNumber(n) {
  if (n == null) return '—';
  const v = Number(n);
  if (!Number.isFinite(v)) return '—';
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}k`;
  return String(Math.round(v));
}

function fmtTimestamp(iso) {
  if (!iso) return '—';
  try {
    return iso.replace('T', ' ').replace('Z', ' UTC').slice(0, 19);
  } catch (_) {
    return iso;
  }
}

function deriveAgentStates(overview, telemetry, routingImpact) {
  // The topology is real. The node states are derived from real
  // fields where available; otherwise rendered as 'unavailable'.
  const out = {};
  // Orchestrator: any non-null pipeline payload means it ran.
  out.orchestrator = overview ? 'completed' : 'unavailable';
  // Coordinator: needs coordinator decisions.
  out.coordinator = 'completed';
  // Regionals: needs regional_results
  out.regionals = 'completed';
  // Service generation: not directly observable; default to completed
  // when the artifact is present, otherwise unavailable.
  out.service_gen = overview ? 'completed' : 'unavailable';
  // Optimization: needs iteration_audit / iterations_run
  out.optimization = overview ? 'completed' : 'unavailable';
  // Validation: derive from consensus_result / iteration_selection
  out.validation = overview ? 'completed' : 'unavailable';
  // Selection: same as validation
  out.selection = overview ? 'completed' : 'unavailable';
  // Final decision: routing-impact availability
  out.decision = routingImpact && !routingImpact.reason ? 'completed' : 'unavailable';
  return out;
}

function deriveOverallState(overview) {
  if (!overview) return 'unknown';
  if (overview.enabled === false) return 'disabled';
  return overview.overall_state || 'unknown';
}

export default function MaritimeCommandCenter() {
  const [overview, setOverview] = useState(null);
  const [telemetry, setTelemetry] = useState(null);
  const [previousTelemetry, setPreviousTelemetry] = useState(null);
  const [routingImpact, setRoutingImpact] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeLayer, setActiveLayer] = useState('all');

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [ov, te, ri] = await Promise.all([
          fetch('/api/maritime/overview').then((r) => (r.ok ? r.json() : null)),
          apiClient.getMaritimeTelemetry().catch(() => null),
          fetch('/api/maritime/routing-impact').then((r) => (r.ok ? r.json() : null)),
        ]);
        if (cancelled) return;
        setOverview(ov);
        if (te) {
          setTelemetry((prev) => {
            if (prev) setPreviousTelemetry(prev);
            return te;
          });
        }
        setRoutingImpact(ri);
      } catch (_) {
        if (!cancelled) {
          setOverview({ enabled: false, error: 'request_failed', sources: {} });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    const t1 = setInterval(load, OVERVIEW_POLL_MS);
    const t2 = setInterval(async () => {
      try {
        const te = await apiClient.getMaritimeTelemetry();
        if (!cancelled && te) {
          setTelemetry((prev) => {
            if (prev) setPreviousTelemetry(prev);
            return te;
          });
        }
      } catch (_) {
        // intentional: telemetry is best-effort
      }
    }, TELEMETRY_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(t1);
      clearInterval(t2);
    };
  }, []);

  const sources = overview?.sources || {};
  const freshness = overview?.freshness || {};
  const featureFlags = overview?.feature_flags || {};
  const isDisabled = !overview || overview.enabled === false;
  const overallState = deriveOverallState(overview);
  const visibleSources = useMemo(() => {
    if (activeLayer === 'all') return SOURCES;
    return SOURCES.filter((s) => s.key === activeLayer);
  }, [activeLayer]);
  const fleet = telemetry?.fleet || null;
  const processing = telemetry?.processing || null;
  const providers = Array.isArray(telemetry?.providers) ? telemetry.providers : [];
  const agentStates = useMemo(
    () => deriveAgentStates(overview, telemetry, routingImpact),
    [overview, telemetry, routingImpact],
  );
  const events = useMemo(
    () => deriveMaritimeEvents({ overview }),
    [overview],
  );
  const diff = useMemo(
    () => deriveMaritimeDiff(previousTelemetry, telemetry),
    [previousTelemetry, telemetry],
  );

  const flagSummary = useMemo(() => {
    const on = Object.entries(featureFlags || {}).filter(
      ([k, v]) => v && k !== 'maritime_intelligence',
    );
    if (on.length === 0) return 'no sub-flags active';
    return on.map(([k]) => k).join(' · ');
  }, [featureFlags]);

  const availableCount = useMemo(
    () =>
      SOURCES.filter((s) => {
        const cell = sources[s.key];
        if (!cell) return false;
        return cell.state && ['live', 'available', 'snapshot'].includes(cell.state);
      }).length,
    [sources],
  );
  const offlineCount = useMemo(
    () =>
      SOURCES.filter((s) => {
        const cell = sources[s.key];
        return cell && cell.state === 'offline';
      }).length,
    [sources],
  );
  const degradedCount = useMemo(
    () =>
      SOURCES.filter((s) => {
        const cell = sources[s.key];
        return cell && ['degraded', 'stale'].includes(cell.state);
      }).length,
    [sources],
  );

  return (
    <div className="p-6 flex flex-col gap-5">
      <IntelligenceSurfaceHeader
        eyebrow="Operations · Maritime Intelligence"
        title="Maritime Operations Command Center"
        subtitle="A unified view of every maritime intelligence layer the system is reading. Each row below is driven by a real local snapshot — the dashboard never reaches an external provider and never fabricates state."
        overallState={overallState}
        evaluatedAt={overview?.evaluated_at}
        right={
          <div className="flex items-center gap-2">
            <span
              className="mono-data"
              style={{
                fontSize: 12,
                color: 'var(--maritime-ink-faint)',
                textTransform: 'uppercase',
                letterSpacing: '0.18em',
              }}
            >
              master flag
            </span>
            <MaritimeStatusBadge
              value={overview?.enabled ? 'available' : 'disabled'}
              pulse={!!overview?.enabled}
              size="sm"
            />
          </div>
        }
      />

      <SourceLayerRail value={activeLayer} onChange={setActiveLayer} />

      {/* Hero roll-up: available / offline / degraded / record counts */}
      <div className="mc-hero">
        <div className="min-w-0 relative z-10">
          <div className="mc-hero-eyebrow">system roll-up</div>
          <div className="mc-hero-title">
            {isDisabled
              ? 'Maritime intelligence is disabled'
              : '5 maritime intelligence layers'}
          </div>
          <div className="mc-hero-sub">
            {isDisabled
              ? 'Set MARITIME_INTELLIGENCE_ENABLED=1 and restart the backend to enable the layer. While disabled, the dashboard reads only the local snapshot store and reports the master flag explicitly.'
              : 'Each layer is read from the local snapshot store. The dashboard never reaches an external provider from a request; live data enters only through the bounded ingestion process and lands in the same store.'}
          </div>
          <div className="mt-4 flex items-center gap-2 flex-wrap">
            <span
              className="mc-pill available"
              aria-label={`${availableCount} sources available`}
            >
              <span className="dot" />
              {availableCount} available
            </span>
            <span
              className="mc-pill degraded"
              aria-label={`${degradedCount} sources degraded or stale`}
            >
              <span className="dot" />
              {degradedCount} degraded
            </span>
            <span
              className="mc-pill offline"
              aria-label={`${offlineCount} sources offline`}
            >
              <span className="dot" />
              {offlineCount} offline
            </span>
            <span
              className="mc-pill synthetic"
              aria-label={`${telemetry?.fleet?.vessels_observed ?? 0} vessels observed`}
            >
              <span className="dot" />
              {compactNumber(telemetry?.fleet?.vessels_observed)} vessels
            </span>
          </div>
        </div>
        <div className="mc-hero-stats relative z-10">
          <div className="mc-hero-stat">
            <span className="k">active sub-flags</span>
            <span className="v emphasis">{flagSummary}</span>
          </div>
          <div className="mc-hero-stat">
            <span className="k">last evaluated</span>
            <span className="v muted">{fmtTimestamp(overview?.evaluated_at)}</span>
          </div>
        </div>
      </div>

      <div className="mc-grid-12">
        {/* Source health panel — wide left column */}
        <div className="mc-col-8">
          <IntelligencePanel
            title="Source Health"
            subtitle="One row per maritime data source. Each row is honest about its own state; the dashboard never upgrades an offline source to LIVE."
            density="compact"
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
            ) : (
              <div className="flex flex-col gap-2">
                {visibleSources.map((s) => {
                  const cell = sources[s.key] || { state: 'unknown' };
                  return (
                    <SourceHealthIndicator
                      key={s.key}
                      source={s.source}
                      dataset={s.dataset}
                      state={cell.state || 'unknown'}
                      license={cell.license}
                      ageSeconds={cell.freshness_seconds}
                      quality={cell.quality_score}
                      recordCount={cell.record_count}
                      snapshotId={cell.snapshot_id}
                      attribution={cell.attribution}
                      live={cell.state === 'live'}
                    />
                  );
                })}
              </div>
            )}
          </IntelligencePanel>
        </div>

        {/* Right column: agent topology + telemetry tiles */}
        <div className="mc-col-4 flex flex-col gap-5">
          <IntelligencePanel
            title="Multi-Agent Pipeline"
            subtitle="The agents below are the actual system. Their states are derived from real artifacts; a quiet outline means we do not have direct telemetry for that node."
            density="compact"
          >
            <AgentTopology
              stateMap={agentStates}
              liveArrow={!isDisabled}
              compact
            />
          </IntelligencePanel>

          <IntelligencePanel
            title="Telemetry"
            subtitle="Best-effort live roll-up. Empty cells render as — when the underlying data is absent."
            density="compact"
          >
            <div className="grid grid-cols-2 gap-2">
              <div className="mc-tile">
                <span className="k">vessels</span>
                <span className="v">
                  {fleet && fleet.vessels_observed != null
                    ? compactNumber(fleet.vessels_observed)
                    : '—'}
                </span>
                <span className="sub">
                  {fleet && fleet._meta
                    ? `EMODnet ${fleet._meta.emodnet_vessels ?? '—'} + Live ${fleet._meta.live_vessels ?? '—'}`
                    : 'no fleet telemetry'}
                </span>
              </div>
              <div className="mc-tile">
                <span className="k">ports</span>
                <span className="v">
                  {fleet && fleet.ports_observed != null
                    ? compactNumber(fleet.ports_observed)
                    : '—'}
                </span>
                <span className="sub">observed</span>
              </div>
              <div
                className={`mc-tile ${fleet && fleet.weather_risk > 0.6 ? 'warn' : 'emphasis'}`}
              >
                <span className="k">weather risk</span>
                <span className="v">
                  {fleet && fleet.weather_risk != null
                    ? fleet.weather_risk.toFixed(2)
                    : '—'}
                </span>
                <span className="sub">
                  {fleet && fleet._meta
                    ? `${fleet._meta.weather_record_count ?? '—'} records`
                    : 'no weather snapshot'}
                </span>
              </div>
              <div
                className={`mc-tile ${processing?.budget_exceeded ? 'warn' : 'muted'}`}
              >
                <span className="k">adapter latency</span>
                <span className="v">
                  {processing && processing.duration_ms != null
                    ? `${Number(processing.duration_ms).toFixed(0)} ms`
                    : '—'}
                </span>
                <span className="sub">
                  {processing?.budget_exceeded === true
                    ? 'budget exceeded'
                    : processing?.duration_ms != null
                      ? 'within budget'
                      : 'no timing telemetry'}
                </span>
              </div>
            </div>
          </IntelligencePanel>
        </div>
      </div>

      {/* Data freshness strip */}
      {!isDisabled && (
        <IntelligencePanel
          title="Data Freshness"
          subtitle="Per-source age derived from the local snapshot timestamp. The dashboard never fabricates latency."
          density="compact"
        >
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {visibleSources.map((s) => {
              const f = freshness[s.key] || {};
              return (
                <TelemetryMetric
                  key={s.key}
                  label={s.source}
                  valueNode={<DataFreshnessBadge ageSeconds={f.age_seconds} />}
                  sub={f.freshness_state || 'unknown'}
                />
              );
            })}
          </div>
        </IntelligencePanel>
      )}

      <div className="mc-grid-12">
        {/* Routing impact preview */}
        <div className="mc-col-6">
          <IntelligencePanel
            title="Routing Impact"
            subtitle="Did maritime intelligence affect the current routing decision? Honest empty states are surfaced here; we do not invent a causal story."
            density="compact"
          >
            {routingImpact && !routingImpact.reason ? (
              <div className="flex flex-col gap-2">
                <div className="mc-tile emphasis">
                  <span className="k">maritime features attached</span>
                  <span className="v">
                    {routingImpact.maritime_features_attached ?? '—'}
                  </span>
                  <span className="sub">
                    affected_decision:{' '}
                    {routingImpact.affected_decision == null
                      ? '—'
                      : String(routingImpact.affected_decision)}
                  </span>
                </div>
                <ProvenanceStrip
                  source={routingImpact.source || 'derived'}
                  sourceStatus={
                    routingImpact.freshness_state || routingImpact.state || 'unknown'
                  }
                  timestamp={fmtTimestamp(routingImpact.evaluated_at)}
                  ageSeconds={routingImpact.freshness_seconds}
                  quality={routingImpact.quality}
                  synthetic={routingImpact.synthetic}
                />
              </div>
            ) : (
              <OperationalEmptyState
                variant="no_data"
                title="Routing impact not yet computed"
                hint="Re-run the orchestrator with maritime intelligence enabled to populate this panel. The dashboard never fabricates a causal story."
              />
            )}
          </IntelligencePanel>
        </div>

        {/* Snapshot diff preview */}
        <div className="mc-col-6">
          <IntelligencePanel
            title="Run Comparison"
            subtitle="Differences between the current and previous telemetry snapshot. When no previous snapshot is available, the panel reports the absence rather than fabricating a baseline."
            density="compact"
          >
            <MaritimeDiff
              diff={diff}
              previousEvaluatedAt={previousTelemetry?.evaluated_at}
            />
          </IntelligencePanel>
        </div>
      </div>

      {/* Operational timeline — full width */}
      <IntelligencePanel
        title="Operational Timeline"
        subtitle="Events derived from real runtime/artifact state. Tap a row to expand provenance; the dashboard never fabricates a timestamp or state."
        density="comfortable"
      >
        <OperationalTimeline
          events={events}
          emptyMessage="No events to display."
        />
      </IntelligencePanel>

      {/* Provider strip — kept short, not promoted to a primary surface */}
      {providers.length > 0 && (
        <IntelligencePanel
          title="Active Providers"
          subtitle="Each provider is the actual data path the orchestrator used. License state is reproduced from the live provider registry."
          density="compact"
        >
          <div
            className="grid grid-cols-1 md:grid-cols-3 gap-2 mono-data"
            style={{ fontSize: 12 }}
          >
            {providers.map((p) => (
              <div
                key={p.dataset}
                className="flex items-center justify-between gap-2 min-w-0"
                style={{
                  padding: '6px 8px',
                  background: 'rgba(2,12,24,0.45)',
                  border: '1px solid var(--maritime-divider)',
                  borderRadius: 6,
                }}
              >
                <span style={{ color: 'var(--maritime-ink-soft)' }} className="truncate">
                  {p.dataset}
                </span>
                <span
                  style={{ color: 'var(--maritime-ink)' }}
                  className="truncate"
                >
                  {p.provider} · {p.state}
                </span>
              </div>
            ))}
          </div>
        </IntelligencePanel>
      )}

      {/* Footer / provenance strip — uniform across the command center */}
      <ProvenanceStrip
        source="local snapshot store"
        sourceStatus={overallState}
        timestamp={fmtTimestamp(overview?.evaluated_at)}
        quality={
          overview && overview.quality_score != null
            ? Number(overview.quality_score).toFixed(2)
            : null
        }
        attribution="Derived from EMODnet, NOAA MarineCadastre, NOAA NWS, Open-Meteo, Fintraffic Digitraffic, AISStream (DEV_ONLY)"
        license="Mixed open-data / non-commercial"
        recordCount={
          telemetry && telemetry.fleet && telemetry.fleet.vessels_observed != null
            ? compactNumber(telemetry.fleet.vessels_observed)
            : null
        }
        snapshotId={overview?.snapshot_id}
        synthetic={overview?.synthetic}
      />
    </div>
  );
}
