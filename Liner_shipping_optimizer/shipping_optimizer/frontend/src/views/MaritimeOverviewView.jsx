/**
 * MaritimeOverviewView
 * --------------------
 * Phase 8 — the cross-source "maritime intelligence command center".
 *
 * Single fetch: GET /api/maritime/overview (poll 15 s).
 * The endpoint already aggregates the existing per-source status
 * payloads (source-health, weather, congestion, live, resilience),
 * so this view is a pure consumer; it never reaches out to the
 * weather / congestion / live endpoints directly. No new network
 * surface is introduced.
 *
 * Failure / disabled / empty handling is exhaustive:
 *   - HTTP error                -> quiet "—" panels
 *   - master flag off           -> "DISABLED" placeholder with a hint
 *   - no snapshots on disk      -> the "OFFLINE" state
 *   - per-source error          -> the per-source row shows `unknown`
 *
 * The view never claims LIVE on insufficient evidence: the
 * MaritimeStatusBadge + DataFreshnessBadge pair are the only
 * authority for live/snapshot/historical.
 *
 * Phase 9 — source filter (Feature A), operational event
 * timeline (Feature B), maritime telemetry integration
 * (Feature C), and snapshot diff (Feature D). The filter is
 * purely client-side and presentation-layer: it never changes
 * the underlying data, never causes a new HTTP request, and
 * never hides disabled / offline / stale states from the
 * source-health row. Default = "all sources" preserves the
 * Phase 8 baseline.
 */

import { useEffect, useMemo, useState } from 'react';
import MaritimeSectionHeader from '../components/maritime/primitives/MaritimeSectionHeader.jsx';
import IntelligencePanel from '../components/maritime/primitives/IntelligencePanel.jsx';
import SourceHealthIndicator from '../components/maritime/primitives/SourceHealthIndicator.jsx';
import MaritimeStatusBadge from '../components/maritime/primitives/MaritimeStatusBadge.jsx';
import DataFreshnessBadge from '../components/maritime/primitives/DataFreshnessBadge.jsx';
import TelemetryMetric from '../components/maritime/primitives/TelemetryMetric.jsx';
import MaritimeLayerToggle from '../components/maritime/primitives/MaritimeLayerToggle.jsx';
import OperationalTimeline, {
  deriveMaritimeEvents,
} from '../components/maritime/primitives/OperationalTimeline.jsx';
import MaritimeDiff, {
  deriveMaritimeDiff,
} from '../components/maritime/primitives/MaritimeDiff.jsx';
import { apiClient } from '../services/apiClient.js';

const POLL_INTERVAL_MS = 15000;
const TELEMETRY_POLL_INTERVAL_MS = 30000;

// Ordered list of source keys; the order is the render order in
// the source-health panel. Phase 9 added a 'live' source key for
// Digitraffic; it was already part of /api/maritime/overview
// since Phase 4.
const SOURCE_KEYS = ['traffic', 'port', 'weather', 'congestion', 'live'];

const SOURCE_LABELS = {
  traffic: { source: 'EMODnet', dataset: 'emodnet_vessel_density' },
  port: { source: 'NOAA MarineCadastre', dataset: 'noaa_ais_port_intelligence' },
  weather: { source: 'Weather', dataset: 'maritime_weather_observations' },
  congestion: { source: 'Congestion', dataset: 'maritime_congestion' },
  live: { source: 'Live', dataset: 'digitraffic_live_vessel_positions' },
};

const RESILIENCE_KEYS = ['traffic', 'port'];

const RESILIENCE_LABELS = {
  traffic: { source: 'EMODnet', dataset: 'emodnet_vessel_density' },
  port: { source: 'NOAA', dataset: 'noaa_ais_port_intelligence' },
};

const FILTER_ALL = 'all';

function fmtTimestamp(iso) {
  if (!iso) return '—';
  try {
    return iso.replace('T', ' ').replace('Z', ' UTC').slice(0, 19);
  } catch (_) {
    return iso;
  }
}

function flagSummary(featureFlags = {}) {
  const on = Object.entries(featureFlags).filter(([k, v]) => v && k !== 'maritime_intelligence');
  if (on.length === 0) return 'no sub-flags active';
  return on.map(([k]) => k).join(' · ');
}

export default function MaritimeOverviewView() {
  const [overview, setOverview] = useState(null);
  const [telemetry, setTelemetry] = useState(null);
  const [previousTelemetry, setPreviousTelemetry] = useState(null);
  const [loading, setLoading] = useState(true);
  // Phase 9 — source filter state. Default = "all" preserves the
  // Phase 8 baseline render. The filter is purely presentational.
  const [activeFilter, setActiveFilter] = useState(FILTER_ALL);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const resp = await fetch('/api/maritime/overview');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        if (cancelled) return;
        setOverview(data);
      } catch (_) {
        if (!cancelled) {
          setOverview({ enabled: false, error: 'request_failed', sources: {} });
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

  // Phase 9 — Feature C + D. The telemetry endpoint is polled on
  // a slower cadence (30s). Each fresh response overwrites
  // `previousTelemetry` only AFTER a successful fetch, so a
  // transient error never erases history. The diff is derived
  // client-side from the two snapshots.
  useEffect(() => {
    let cancelled = false;
    const loadTelemetry = async () => {
      try {
        const data = await apiClient.getMaritimeTelemetry();
        if (cancelled) return;
        setTelemetry((prev) => {
          if (prev) setPreviousTelemetry(prev);
          return data;
        });
      } catch (_) {
        if (!cancelled) {
          setTelemetry({ enabled: false, reason: 'request_failed' });
        }
      }
    };
    loadTelemetry();
    const t = setInterval(loadTelemetry, TELEMETRY_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  const isDisabled = !overview || overview.enabled === false;
  const overallState = overview?.overall_state || (isDisabled ? 'disabled' : 'unknown');
  const sources = overview?.sources || {};
  const freshness = overview?.freshness || {};
  const featureFlags = overview?.feature_flags || {};
  const resilience = overview?.resilience || {};

  // Phase 9 — derive the visible-source list from the active
  // filter. An unknown filter value falls back to "all" so the
  // view never renders a blank panel by accident.
  const effectiveFilter = useMemo(() => {
    if (activeFilter === FILTER_ALL) return FILTER_ALL;
    if (SOURCE_KEYS.includes(activeFilter)) return activeFilter;
    return FILTER_ALL;
  }, [activeFilter]);

  const visibleSourceKeys = useMemo(
    () => (effectiveFilter === FILTER_ALL
      ? SOURCE_KEYS
      : SOURCE_KEYS.filter((k) => k === effectiveFilter)),
    [effectiveFilter],
  );
  const visibleResilienceKeys = useMemo(
    () => (effectiveFilter === FILTER_ALL
      ? RESILIENCE_KEYS
      : RESILIENCE_KEYS.filter((k) => k === effectiveFilter)),
    [effectiveFilter],
  );

  // Phase 9 — Feature B: derive the timeline events from the
  // overview payload. No fabrication: if a field is missing,
  // the helper returns an event with state=unknown and no
  // timestamp.
  const events = useMemo(
    () => deriveMaritimeEvents({ overview }),
    [overview],
  );

  // Phase 9 — Feature D: derive the snapshot diff from the two
  // most recent telemetry snapshots. The previous snapshot is
  // only set once a fresh one arrives, so the very first poll
  // has no diff.
  const diff = useMemo(
    () => deriveMaritimeDiff(previousTelemetry, telemetry),
    [previousTelemetry, telemetry],
  );

  // Phase 9 — Feature C: render the fleet telemetry strip.
  const fleet = telemetry && telemetry.fleet ? telemetry.fleet : null;
  const processing = telemetry && telemetry.processing ? telemetry.processing : null;
  const providers = telemetry && Array.isArray(telemetry.providers) ? telemetry.providers : [];

  return (
    <div className="p-6 flex flex-col gap-5">
      <MaritimeSectionHeader
        eyebrow="Operations · Maritime Intelligence"
        title="Command Center"
        subtitle="Cross-source maritime intelligence status. Every layer is read from the local snapshot store; the dashboard never reaches an external provider."
        right={
          <div className="flex items-center gap-2">
            <span className="text-[12px] font-mono uppercase tracking-widest text-white/60">
              overall
            </span>
            <MaritimeStatusBadge value={overallState} pulse={overallState === 'live'} size="md" />
          </div>
        }
      />

      {/* Top telemetry strip — 4 metrics */}
      <IntelligencePanel
        title="Evaluation"
        density="compact"
        right={
          <span className="text-[12px] font-mono text-white/60">
            poll {POLL_INTERVAL_MS / 1000}s
          </span>
        }
      >
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <TelemetryMetric
            label="Evaluated at"
            value={fmtTimestamp(overview?.evaluated_at)}
            size="md"
          />
          <TelemetryMetric
            label="Master flag"
            value={overview?.enabled ? 'ENABLED' : 'DISABLED'}
            tone={overview?.enabled ? 'emphasis' : 'muted'}
            size="md"
          />
          <TelemetryMetric
            label="Active sub-flags"
            value={flagSummary(featureFlags)}
            tone="muted"
            size="md"
          />
          <TelemetryMetric
            label="Source count"
            value={Object.keys(sources).length}
            tone="muted"
            size="md"
          />
        </div>
      </IntelligencePanel>

      {/* Phase 9 — Feature C: fleet + processing telemetry */}
      {!isDisabled && (
        <IntelligencePanel
          title="Maritime telemetry"
          subtitle="Fleet-level roll-up from the local snapshot store. Empty cells render as — when the underlying data is absent (the dashboard never invents a value)."
          density="compact"
          right={
            <span className="text-[12px] font-mono text-white/60">
              poll {TELEMETRY_POLL_INTERVAL_MS / 1000}s
            </span>
          }
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <TelemetryMetric
              label="Vessels observed"
              value={fleet && fleet.vessels_observed != null ? fleet.vessels_observed : '—'}
              sub={fleet && fleet._meta ? `EMODnet ${fleet._meta.emodnet_vessels ?? '—'} + Live ${fleet._meta.live_vessels ?? '—'}` : '—'}
              tone={fleet && fleet.vessels_observed != null ? 'emphasis' : 'muted'}
              size="md"
            />
            <TelemetryMetric
              label="Ports observed"
              value={fleet && fleet.ports_observed != null ? fleet.ports_observed : '—'}
              tone={fleet && fleet.ports_observed != null ? 'emphasis' : 'muted'}
              size="md"
            />
            <TelemetryMetric
              label="Weather risk"
              value={fleet && fleet.weather_risk != null ? fleet.weather_risk.toFixed(2) : '—'}
              sub={fleet && fleet._meta ? `${fleet._meta.weather_record_count ?? '—'} records` : '—'}
              tone={fleet && fleet.weather_risk != null
                ? (fleet.weather_risk > 0.6 ? 'warn' : 'default')
                : 'muted'}
              size="md"
            />
            <TelemetryMetric
              label="Processing latency"
              value={processing && processing.duration_ms != null
                ? `${Number(processing.duration_ms).toFixed(0)} ms`
                : '—'}
              sub={processing && processing.budget_exceeded === true
                ? 'budget exceeded'
                : (processing && processing.duration_ms != null ? 'within budget' : '—')}
              tone={processing && processing.budget_exceeded === true
                ? 'warn'
                : (processing && processing.duration_ms != null ? 'default' : 'muted')}
              size="md"
            />
          </div>
          {providers.length > 0 && (
            <div className="mt-3 pt-2 grid grid-cols-2 md:grid-cols-3 gap-2 text-[12px] font-mono"
                 style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
              {providers.map((p) => (
                <div key={p.dataset} className="flex items-center justify-between gap-2 min-w-0">
                  <span className="text-white/60 truncate">{p.dataset}</span>
                  <span className="text-white/70 truncate">{p.provider} · {p.state}</span>
                </div>
              ))}
            </div>
          )}
        </IntelligencePanel>
      )}

      {/* Phase 9 — Feature D: snapshot diff (current vs previous) */}
      {!isDisabled && (
        <IntelligencePanel
          title="Run comparison"
          subtitle="Differences between the current and previous telemetry snapshot. When no previous snapshot is available, the panel reports the absence rather than fabricating a baseline."
          density="compact"
        >
          <MaritimeDiff diff={diff} previousEvaluatedAt={previousTelemetry?.evaluated_at} />
        </IntelligencePanel>
      )}

      {/* Phase 9 — source filter strip.
          Pure client-side state. No new HTTP request. "All" is
          the default and the Phase 8 baseline. Toggling a source
          narrows the per-source-health, freshness, and resilience
          rows to that single key. Disabled / offline / stale
          states remain visible. */}
      <IntelligencePanel
        title="Source filter"
        subtitle="Narrow the command center to a single maritime layer. Default is all sources."
        density="compact"
      >
        <div className="flex flex-wrap items-center gap-2">
          <MaritimeLayerToggle
            active={effectiveFilter === FILTER_ALL}
            onClick={() => setActiveFilter(FILTER_ALL)}
            label="All sources"
            count={SOURCE_KEYS.length}
          />
          {SOURCE_KEYS.map((key) => {
            const labels = SOURCE_LABELS[key];
            return (
              <MaritimeLayerToggle
                key={key}
                active={effectiveFilter === key}
                onClick={() => setActiveFilter(key)}
                label={labels.source}
              />
            );
          })}
          <span className="text-[12px] font-mono text-white/60 ml-auto">
            {effectiveFilter === FILTER_ALL
              ? 'rendering all sources'
              : `rendering ${SOURCE_LABELS[effectiveFilter]?.source || effectiveFilter} only`}
          </span>
        </div>
      </IntelligencePanel>

      {/* Per-source health */}
      <IntelligencePanel
        title="Source Health"
        subtitle={
          isDisabled
            ? 'Maritime intelligence is disabled. Set MARITIME_INTELLIGENCE_ENABLED=1 to enable.'
            : 'One row per maritime data source. Tap a row to expand provenance and attribution.'
        }
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
            {visibleSourceKeys.map((key) => {
              const labels = SOURCE_LABELS[key];
              const cell = sources[key] || { state: 'unknown' };
              return (
                <SourceHealthIndicator
                  key={key}
                  source={labels.source}
                  dataset={labels.dataset}
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

      {/* Per-source freshness strip — visible only when enabled */}
      {!isDisabled && (
        <IntelligencePanel
          title="Data Freshness"
          subtitle="Derived from the local snapshot timestamp on each source. The dashboard never fabricates latency; missing timestamps render as —."
          density="compact"
        >
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {visibleSourceKeys.map((key) => {
              const f = freshness[key] || {};
              return (
                <TelemetryMetric
                  key={key}
                  label={SOURCE_LABELS[key].source}
                  valueNode={
                    <DataFreshnessBadge ageSeconds={f.age_seconds} />
                  }
                  sub={f.freshness_state || 'unknown'}
                />
              );
            })}
          </div>
        </IntelligencePanel>
      )}

      {/* Resilience summary */}
      <IntelligencePanel
        title="Resilience"
        subtitle="Phase 3 source-health + freshness classification. When the master flag is off, both rows report DISABLED."
        density="compact"
      >
        <div className="flex flex-col gap-2">
          {visibleResilienceKeys.length === 0 ? (
            <div className="text-[12px] text-white/35 font-mono">
              No resilience rows for the active filter.
            </div>
          ) : (
            visibleResilienceKeys.map((key) => {
              const labels = RESILIENCE_LABELS[key];
              const cell = resilience[key] || { state: isDisabled ? 'offline' : 'unknown' };
              return (
                <SourceHealthIndicator
                  key={key}
                  source={labels.source}
                  dataset={labels.dataset}
                  state={cell.state || (isDisabled ? 'disabled' : 'unknown')}
                  license={undefined}
                  ageSeconds={cell.age_seconds}
                  quality={cell.quality_score}
                  recordCount={cell.record_count}
                  snapshotId={cell.snapshot_id}
                />
              );
            })
          )}
        </div>
      </IntelligencePanel>

      {/* Phase 9 — Feature B: operational event timeline */}
      <IntelligencePanel
        title="Operational timeline"
        subtitle="Events derived from real runtime/artifact state. Tap a row to expand provenance; the dashboard never fabricates a timestamp or state."
        density="comfortable"
      >
        <OperationalTimeline events={events} emptyMessage="No events to display." />
      </IntelligencePanel>

      {/* Disabled placeholder */}
      {isDisabled && (
        <IntelligencePanel
          title="Maritime Intelligence · DISABLED"
          density="compact"
        >
          <div className="text-[12px] text-white/35 font-mono leading-relaxed">
            The maritime intelligence layer is disabled. The dashboard reads
            only the local snapshot store — no external provider is ever
            contacted. To enable, set
            <code className="mx-1 px-1 rounded"
              style={{
                background: 'rgba(255,255,255,0.06)',
                color: 'rgba(255,255,255,0.7)',
              }}
            >MARITIME_INTELLIGENCE_ENABLED=1</code>
            and restart the backend.
          </div>
        </IntelligencePanel>
      )}

      <div className="text-[12px] text-white/60 font-mono leading-relaxed max-w-3xl">
        Phase 9 maritime command center. The endpoints
        <code className="mx-1">/api/maritime/overview</code> and
        <code className="mx-1">/api/maritime/telemetry</code> aggregate the
        existing per-source status responses into single, safe-empty
        payloads. No /ws/pipeline events are touched, no optimizer logic
        is modified, and no external provider is contacted from the
        dashboard. The source filter is purely presentational.
      </div>
    </div>
  );
}
