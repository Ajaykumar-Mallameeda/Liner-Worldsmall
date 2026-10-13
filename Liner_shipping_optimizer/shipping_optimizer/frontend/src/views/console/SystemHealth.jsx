/**
 * SystemHealth -- Phase 12 REVISION
 * ---------------------------------
 * The System Health instrument. Read-only roll-up of the
 * runtime health: API, WebSocket, maritime data plane, LLM
 * provider, and orchestrator state. All data is from real
 * backend endpoints; no fake heartbeat, no setInterval
 * randomizeMetric.
 *
 * Data contracts UNCHANGED.
 */

import { useEffect, useState, createElement, Fragment } from 'react';
import { useOptimizationState } from '../../hooks/useOptimizationState.js';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import { Pill, Kv, Stat, Empty, Tag, Dot, Provenance } from '../../components/console/p12.jsx';
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
  return h('div', { className: 'cx-row', style: { padding: '8px 10px' } },
    h('div', { style: { fontFamily: 'var(--cx-mono)', fontSize: 10, color: 'var(--cx-text-faint)', textTransform: 'uppercase', letterSpacing: '0.14em' } }, label),
    h('div', null,
      h('span', { style: { display: 'inline-flex', gap: 6, alignItems: 'center' } },
        h(Dot, { tone: state }),
        h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 11, color: 'var(--cx-text)' } }, value || EM)
      )
    ),
    h('div', { style: { textAlign: 'right', color: 'var(--cx-text-faint)', fontFamily: 'var(--cx-mono)', fontSize: 9 } }, sub || '')
  );
}

export default function SystemHealth(props) {
  const maritimeOverview = props && props.maritimeOverview;
  const hookState = useOptimizationState();
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

  const ws = telemetry && telemetry.ws ? telemetry.ws : null;
  const orchestrator = hookState.global || {};
  const llm = hookState.llm || null;
  const overallState = health ? 'available' : 'no_data';

  return h(F, null,
    h(PageHead, {
      section: 'System',
      eyebrow: 'Health',
      title: 'System Health',
      subtitle: 'A read-only roll-up of runtime health: API, WebSocket, maritime data plane, LLM provider, and orchestrator state. No synthetic values; missing endpoints show as unknown.',
      pills: [
        { tone: overallState, label: overallState === 'available' ? 'api on disk' : 'no api' },
        { tone: ws ? 'connected' : 'offline', label: ws ? 'ws link' : 'ws off' },
        { tone: orchestrator.run_id ? 'available' : 'no_data', label: orchestrator.run_id ? 'orchestrator run' : 'no run' },
        { tone: llm ? 'available' : 'no_data', label: llm ? 'llm on disk' : 'no llm' },
      ],
    }),

    h('div', { className: 'cx-page-body' },

      loading
        ? h(Empty, { tone: 'unknown', label: 'loading', title: 'Loading system health' })
        : h(F, null,
            h('div', { className: 'cx-grid-12' },
              h('div', { className: 'cx-span-6' },
                h(InstrumentPanel, {
                  title: 'Runtime',
                  right: 'api + ws + orchestrator',
                  bodyPadding: 'flush',
                },
                  h('div', { className: 'cx-rows' },
                    h(HealthRow, {
                      label: 'API',
                      value: (health && health.status) || 'unknown',
                      sub: health ? ('version ' + (health.version || EM)) : 'no /api/health',
                      state: (health && (health.status === 'ok' || health.status === 'healthy')) ? 'available' : (health ? 'warn' : 'unknown'),
                    }),
                    h(HealthRow, {
                      label: 'WebSocket',
                      value: (ws && ws.state) || 'unknown',
                      sub: ws && ws.last_event_at ? ('last ' + fmtTime(ws.last_event_at)) : 'no events',
                      state: ws && ws.state === 'connected' ? 'connected' : (ws ? 'warn' : 'offline'),
                    }),
                    h(HealthRow, {
                      label: 'Orchestrator',
                      value: orchestrator.run_id || EM,
                      sub: orchestrator.iter != null ? ('selected iter ' + String(orchestrator.iter).padStart(2, '0')) : 'no selection',
                      state: orchestrator.run_id ? 'available' : 'no_data',
                    }),
                    h(HealthRow, {
                      label: 'Pipeline output',
                      value: orchestrator.run_id ? 'loaded' : 'absent',
                      sub: orchestrator.created_at ? ('created ' + fmtTime(orchestrator.created_at)) : '',
                      state: orchestrator.run_id ? 'available' : 'no_data',
                    })
                  )
                )
              ),
              h('div', { className: 'cx-span-6' },
                h(InstrumentPanel, {
                  title: 'LLM Provider',
                  right: 'read from the orchestrator audit; the dashboard never fabricates a model name',
                  bodyPadding: 'flush',
                },
                  !llm
                    ? h(Empty, { tone: 'no_data', label: 'no llm', title: 'No LLM provider state' })
                    : h('div', { className: 'cx-rows' },
                        h(HealthRow, {
                          label: 'Active provider',
                          value: llm.active_provider || EM,
                          sub: llm.active_model || '',
                          state: llm.active_provider ? 'available' : 'unknown',
                        }),
                        h(HealthRow, {
                          label: 'Failover enabled',
                          value: llm.failover_enabled ? 'yes' : 'no',
                          sub: llm.failover_count != null ? (llm.failover_count + ' failovers') : '',
                          state: llm.failover_enabled ? 'available' : 'unknown',
                        }),
                        h(HealthRow, {
                          label: 'Last trace',
                          value: llm.last_trace_id || EM,
                          sub: llm.last_trace_at ? ('at ' + fmtTime(llm.last_trace_at)) : '',
                          state: llm.last_trace_id ? 'available' : 'unknown',
                        }),
                        h(HealthRow, {
                          label: 'Trace count',
                          value: llm.trace_count != null ? String(llm.trace_count) : EM,
                          sub: '',
                          state: llm.trace_count != null ? 'available' : 'unknown',
                        })
                      )
                )
              )
            ),

            h(InstrumentPanel, {
              title: 'Maritime Data Plane',
              right: 'per-source health for the maritime data plane — honest state per source',
              bodyPadding: 'flush',
            },
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
                : h(Empty, { tone: 'no_data', label: 'no data plane', title: 'No maritime data plane state' })
            )
          ),

      h(Provenance, {
        source: '/api/health + /api/maritime/telemetry + pipeline_output.json',
        sourceStatus: (health || telemetry) ? 'available' : 'no_data',
        attribution: 'Local backend',
        license: 'Internal',
      })
    )
  );
}
