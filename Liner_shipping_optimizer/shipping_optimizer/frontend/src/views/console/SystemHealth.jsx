/**
 * SystemHealth -- Phase 12 REVISION
 * ---------------------------------
 * The System Health instrument. Read-only roll-up of the
 * runtime health: API, live pipeline link, maritime data plane,
 * the LLM providers the shown run used, and orchestrator state.
 * All data is from real backend endpoints or the run on disk;
 * no fake heartbeat, no setInterval randomizeMetric.
 *
 * Data contracts UNCHANGED.
 */

import { useEffect, useState, createElement, Fragment } from 'react';
import { useOptimizationState } from '../../hooks/useOptimizationState.js';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import { Empty, Dot, Provenance } from '../../components/console/p12.jsx';
import { selectedIterationOf, liveLinkOf } from '../../runtime/consoleSelectors.js';
const h = createElement;
const F = Fragment;

const EM = '—';
function fmtTime(iso) {
  if (!iso) return EM;
  try { return new Date(iso).toISOString().slice(0, 19).replace('T', ' '); }
  catch (_) { return String(iso); }
}

function HealthRow(props) {
  const label = props.label, value = props.value, sub = props.sub, state = props.state;
  return h('div', { className: 'cx-row', style: { padding: '8px 10px', gridTemplateColumns: 'minmax(120px, 170px) minmax(0, 1fr) minmax(0, auto)' } },
    h('div', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-faint)', textTransform: 'uppercase', letterSpacing: '0.1em' } }, label),
    h('div', { style: { minWidth: 0 } },
      h('span', { style: { display: 'inline-flex', gap: 6, alignItems: 'center', minWidth: 0 } },
        h(Dot, { tone: state }),
        h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 13, color: 'var(--cx-text)', overflowWrap: 'anywhere' } }, value || EM)
      )
    ),
    h('div', { style: { textAlign: 'right', color: 'var(--cx-text-faint)', fontFamily: 'var(--cx-mono)', fontSize: 12, overflowWrap: 'anywhere' } }, sub || '')
  );
}

export default function SystemHealth(props) {
  const hookState = useOptimizationState();
  const runtime = props && props.runtime;
  const opt = (runtime && runtime.global) ? runtime : hookState;
  const [health, setHealth] = useState(null);
  const [telemetry, setTelemetry] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(function() {
    let cancelled = false;
    const load = async function() {
      try {
        const h2 = await fetch('/api/health').then(function(r) { return r.ok ? r.json() : null; }).catch(function() { return null; });
        const t = await fetch('/api/maritime/telemetry').then(function(r) { return r.ok ? r.json() : null; }).catch(function() { return null; });
        if (!cancelled) {
          setHealth(h2);
          setTelemetry(t);
        }
      } catch (_) { /* noop */ }
      finally { if (!cancelled) setLoading(false); }
    };
    load();
    return function() { cancelled = true; };
  }, []);

  const link = liveLinkOf(hookState);
  const g = opt.global || {};
  const source = opt.source || hookState.source || null;
  const runLabel = (source && source.label) || g.run_id || null;
  const selIter = selectedIterationOf(opt);
  const loaded = Boolean((g.selected_services || []).length) || g.weeklyProfit != null;

  // LLM state of the run being shown (llm_runtime_aggregate / llm_runtime_metrics in pipeline_output.json).
  const agg = opt.llm_runtime_aggregate || g.llm_runtime_aggregate || {};
  const met = opt.llm_runtime_metrics || g.llm_runtime_metrics || {};
  const pt = agg.provider_telemetry || {};
  // providers_used / models_used are { name: calls } in pipeline_output.json; older runs may carry a plain list.
  const namesWithCounts = function(v) {
    if (Array.isArray(v)) return v.map(String);
    if (v && typeof v === 'object') return Object.entries(v).map(function(e) { return e[0] + ' × ' + e[1]; });
    return [];
  };
  const providers = namesWithCounts(agg.providers_used || pt.provider_order || pt.provider_call_counts);
  const models = namesWithCounts(agg.models_used || pt.model_call_counts);
  const breakers = Object.entries(pt.breakers || {});
  const openBreakers = breakers.filter(function(b) { return b[1] && b[1].state && b[1].state !== 'closed'; }).length;
  const errorCounts = Object.entries(pt.error_type_counts || {}).map(function(e) { return e[1] + ' × ' + e[0]; }).join(', ');
  const hasLlm = providers.length > 0 || pt.attempts != null || met.llm_calls != null;

  const apiOk = health && (health.status === 'ok' || health.status === 'healthy');

  return h(F, null,
    h(PageHead, {
      section: 'System',
      eyebrow: 'Health',
      title: 'System Health',
      subtitle: 'Read-only roll-up: backend API, the live pipeline link, the run on screen, the LLM providers that run used, and the maritime data plane. Missing endpoints show as unknown.',
      pills: [
        { tone: apiOk ? 'available' : (health ? 'warn' : 'offline'), label: apiOk ? 'api ok' : (health ? 'api degraded' : 'api unreachable') },
        { tone: link.tone === 'ok' ? 'connected' : (link.tone === 'warn' ? 'warn' : 'offline'), label: link.label.toLowerCase() },
        { tone: loaded ? 'available' : 'no_data', label: loaded ? 'results loaded' : 'no results' },
        { tone: hasLlm ? 'available' : 'no_data', label: hasLlm ? 'llm telemetry in run' : 'no llm telemetry' },
      ],
    }),

    h('div', { className: 'cx-page-body' },

      loading
        ? h(Empty, { tone: 'unknown', label: 'loading', title: 'Loading system health' })
        : h(F, null,
            h('div', { className: 'cx-grid-12' },
              h('div', { className: 'cx-span-6' },
                h(InstrumentPanel, { title: 'Runtime', right: 'api · link · run', bodyPadding: 'flush' },
                  h('div', { className: 'cx-rows' },
                    h(HealthRow, {
                      label: 'API',
                      value: (health && health.status) || 'unreachable',
                      sub: health ? ('version ' + (health.version || EM)) : 'GET /api/health failed',
                      state: apiOk ? 'available' : (health ? 'warn' : 'offline'),
                    }),
                    h(HealthRow, {
                      label: 'Live link',
                      value: link.label,
                      sub: link.title,
                      state: link.tone === 'ok' ? 'connected' : (link.tone === 'warn' ? 'warn' : 'unknown'),
                    }),
                    h(HealthRow, {
                      label: 'Run shown',
                      value: runLabel || EM,
                      sub: selIter != null ? ('selected iter ' + String(selIter).padStart(2, '0')) : 'no selection',
                      state: loaded ? 'available' : 'no_data',
                    }),
                    h(HealthRow, {
                      label: 'Results file',
                      value: loaded ? 'loaded' : 'absent',
                      sub: source && source.modifiedIso ? ('modified ' + fmtTime(source.modifiedIso) + ' UTC') : '',
                      state: loaded ? 'available' : 'no_data',
                    })
                  )
                )
              ),
              h('div', { className: 'cx-span-6' },
                h(InstrumentPanel, { title: 'LLM Providers', right: 'from the run on screen', bodyPadding: 'flush' },
                  !hasLlm
                    ? h(Empty, { tone: 'no_data', label: 'no llm', title: 'This run recorded no LLM telemetry' })
                    : h('div', { className: 'cx-rows' },
                        h(HealthRow, {
                          label: 'Providers',
                          value: providers.join(', ') || EM,
                          sub: models.join(', '),
                          state: providers.length ? 'available' : 'unknown',
                        }),
                        h(HealthRow, {
                          label: 'Calls',
                          value: pt.attempts != null ? (pt.successes + ' ok / ' + pt.attempts + ' attempts') : (met.llm_calls != null ? String(met.llm_calls) : EM),
                          sub: pt.cache_hits != null ? (pt.cache_hits + ' cache hits') : '',
                          state: pt.failures ? 'warn' : 'available',
                        }),
                        h(HealthRow, {
                          label: 'Failures',
                          value: pt.failures != null ? String(pt.failures) : EM,
                          sub: errorCounts,
                          state: pt.failures ? 'warn' : 'available',
                        }),
                        h(HealthRow, {
                          label: 'Fallbacks',
                          value: pt.fallback_uses != null ? String(pt.fallback_uses) : EM,
                          sub: met.servicegen_fallback_count != null ? ('service gen: ' + met.servicegen_fallback_count + ' of ' + (met.servicegen_regions ?? EM) + ' regions') : '',
                          state: pt.fallback_uses ? 'warn' : 'available',
                        }),
                        h(HealthRow, {
                          label: 'Circuit breakers',
                          value: breakers.length ? (openBreakers + ' open / ' + breakers.length) : EM,
                          sub: pt.circuit_breaker_events != null ? (pt.circuit_breaker_events + ' breaker events') : '',
                          state: openBreakers ? 'warn' : 'available',
                        })
                      )
                )
              )
            ),

            h(InstrumentPanel, { title: 'Maritime Data Plane', right: 'per source', bodyPadding: 'flush' },
              telemetry && telemetry.sources
                ? h('div', { className: 'cx-rows' },
                    Object.entries(telemetry.sources).map(function(entry) {
                      const key = entry[0], cell = entry[1];
                      return h(HealthRow, {
                        key: key,
                        label: String(key).toUpperCase(),
                        value: cell.state || 'unknown',
                        sub: cell.freshness_seconds != null ? (cell.freshness_seconds + 's · ' + (cell.record_count != null ? cell.record_count : EM) + ' rec') : '',
                        state: cell.state || 'unknown',
                      });
                    })
                  )
                : h('div', { className: 'cx-compact-empty' }, 'Maritime layers are off for this run, so there is no per-source state to show.')
            )
          ),

      h(Provenance, {
        source: '/api/health + /api/maritime/telemetry + ' + ((source && source.url) || 'pipeline_output.json'),
        sourceStatus: (health || telemetry) ? 'available' : 'no_data',
        attribution: 'Local backend',
        license: 'Internal',
      })
    )
  );
}
