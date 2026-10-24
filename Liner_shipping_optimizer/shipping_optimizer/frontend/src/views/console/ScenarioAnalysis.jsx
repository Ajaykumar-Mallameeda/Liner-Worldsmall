/**
 * ScenarioAnalysis — Scenario Playground Console
 * ===============================================
 * What-if maritime deployment and economic sensitivity analysis sandbox.
 * Allows operators to dynamically simulate fuel shocks, severe weather,
 * chokepoint delays, port closures, and demand shifts against the baseline.
 *
 * Sourced deterministically from pipeline_output.json.
 * 100% isolated in-memory what-if state with zero mutation of optimizer truth.
 */

import { useState, useMemo, useCallback, createElement, Fragment } from 'react';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import { Stat, Provenance } from '../../components/console/p12.jsx';
import {
  DEFAULT_PARAMETERS,
  SCENARIO_PRESETS,
} from '../../services/scenario/scenarioTypes.js';
import {
  extractBaselineState,
  evaluateScenario,
} from '../../services/scenario/scenarioEngine.js';

const h = createElement;
const F = Fragment;

// ─── Formatters ────────────────────────────────────────────────────────────
const EM = '—';

function fmtUsd(v) {
  if (v == null || v !== v) return EM;
  const n = Number(v);
  const neg = n < 0;
  const abs = Math.abs(n);
  let s = abs >= 1e9 ? '$' + (abs / 1e9).toFixed(2) + 'B'
        : abs >= 1e6 ? '$' + (abs / 1e6).toFixed(1) + 'M'
        : abs >= 1e3 ? '$' + (abs / 1e3).toFixed(0) + 'K'
        : '$' + Math.round(abs);
  return neg ? '-' + s : s;
}

function fmtNum(v, dec = 0) {
  if (v == null || v !== v) return EM;
  const n = Number(v);
  if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(0) + 'K';
  return n.toFixed(dec);
}

function fmtPct(v, dec = 1) {
  if (v == null || v !== v) return EM;
  let n = Number(v);
  if (n > 0 && n <= 1) n = n * 100;
  return n.toFixed(dec) + '%';
}

function fmtDeltaUsd(v) {
  if (v == null || v !== v) return EM;
  const n = Number(v);
  const sign = n >= 0 ? '+' : '';
  const abs = Math.abs(n);
  return abs >= 1e9 ? sign + '$' + (n / 1e9).toFixed(2) + 'B'
       : abs >= 1e6 ? sign + '$' + (n / 1e6).toFixed(1) + 'M'
       : abs >= 1e3 ? sign + '$' + (n / 1e3).toFixed(0) + 'K'
       : sign + '$' + Math.round(n);
}

function fmtDeltaPct(v, dec = 1) {
  if (v == null || v !== v) return EM;
  const n = Number(v);
  return (n >= 0 ? '+' : '') + n.toFixed(dec) + ' pp';
}

function deltaColor(v, invert = false) {
  if (v == null || v === 0) return 'var(--cx-text-faint)';
  const isPos = Number(v) > 0;
  if (invert) {
    return isPos ? '#ef4444' : '#10b981';
  }
  return isPos ? '#10b981' : '#ef4444';
}

// ─── Reusable Key-Value Rows ───────────────────────────────────────────────
function ComparisonRow({ label, base, scenario, delta, isUsd = false, isPct = false, invertDelta = false }) {
  const dVal = delta != null ? (isUsd ? fmtDeltaUsd(delta) : isPct ? fmtDeltaPct(delta) : (delta >= 0 ? '+' : '') + fmtNum(delta)) : EM;
  const col = deltaColor(delta, invertDelta);

  return h('div', {
    style: {
      display: 'grid',
      gridTemplateColumns: '1.4fr 1fr 1fr 1fr',
      alignItems: 'center',
      padding: '4px 6px',
      borderBottom: '1px solid rgba(255,255,255,0.04)',
      fontFamily: 'var(--cx-mono)',
      fontSize: 12,
    },
  },
    h('span', { style: { color: 'var(--cx-text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em' } }, label),
    h('span', { style: { color: 'var(--cx-text-faint)', textAlign: 'right' } }, isUsd ? fmtUsd(base) : isPct ? fmtPct(base) : fmtNum(base)),
    h('span', { style: { color: 'var(--cx-text)', fontWeight: 600, textAlign: 'right' } }, isUsd ? fmtUsd(scenario) : isPct ? fmtPct(scenario) : fmtNum(scenario)),
    h('span', { style: { color: col, fontWeight: 700, textAlign: 'right' } }, dVal),
  );
}

// ─── Sensitivity SVG Line Chart ────────────────────────────────────────────
function SensitivityChart({ points = [], currentMult = 1.0, title = 'Fuel Price Sensitivity ($ Weekly Profit)' }) {
  const W = 380;
  const H = 120;
  const PAD = { top: 14, right: 18, bottom: 24, left: 45 };
  const cW = W - PAD.left - PAD.right;
  const cH = H - PAD.top - PAD.bottom;

  if (!points || points.length === 0) return null;

  const profits = points.map(p => p.profit);
  const minP = Math.min(...profits);
  const maxP = Math.max(...profits);
  const range = maxP === minP ? 1 : maxP - minP;

  const stepX = cW / (points.length - 1);
  const pts = points.map((p, i) => ({
    x: PAD.left + i * stepX,
    y: PAD.top + cH - ((p.profit - minP) / range) * cH,
    label: p.step,
    profit: p.profit,
    isCurrent: Math.abs((p.multiplier || 1) - currentMult) < 0.05,
  }));

  const linePath = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
  const areaPath = `M ${PAD.left} ${PAD.top + cH} ` +
    pts.map(p => `L ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ') +
    ` L ${(PAD.left + cW).toFixed(1)} ${PAD.top + cH} Z`;

  return h('div', { style: { width: '100%', overflow: 'hidden' } },
    h('div', {
      style: {
        display: 'flex', justifyContent: 'space-between',
        fontFamily: 'var(--cx-mono)', fontSize: 12,
        color: 'var(--cx-text-faint)', textTransform: 'uppercase', marginBottom: 4,
      },
    },
      h('span', null, title),
      h('span', { style: { color: '#fbbf24' } }, 'Curve: $ Profit vs Step'),
    ),
    h('svg', {
      width: '100%', height: H, viewBox: `0 0 ${W} ${H}`,
      preserveAspectRatio: 'none', style: { display: 'block', overflow: 'visible' },
    },
      h('defs', null,
        h('linearGradient', { id: 'sens-grad', x1: '0', y1: '0', x2: '0', y2: '1' },
          h('stop', { offset: '0%', stopColor: '#fbbf24', stopOpacity: 0.28 }),
          h('stop', { offset: '100%', stopColor: '#fbbf24', stopOpacity: 0 }),
        ),
      ),
      h('line', {
        x1: PAD.left, x2: PAD.left + cW, y1: PAD.top + cH, y2: PAD.top + cH,
        stroke: 'rgba(255,255,255,0.08)', strokeWidth: 1,
      }),
      h('path', { d: areaPath, fill: 'url(#sens-grad)' }),
      h('path', { d: linePath, fill: 'none', stroke: '#fbbf24', strokeWidth: 1.8, strokeLinecap: 'round' }),
      pts.map((p, i) =>
        h('g', { key: i },
          h('circle', {
            cx: p.x, cy: p.y, r: p.isCurrent ? 4 : 2.5,
            fill: p.isCurrent ? '#fbbf24' : '#0a0e1a',
            stroke: '#fbbf24', strokeWidth: 1.5,
          }),
          h('text', {
            x: p.x, y: H - 4, textAnchor: 'middle',
            fontFamily: 'monospace', fontSize: 12, fill: p.isCurrent ? '#fbbf24' : 'rgba(255,255,255,0.4)',
            fontWeight: p.isCurrent ? 700 : 400,
          }, p.label),
        )
      ),
      h('text', {
        x: PAD.left - 4, y: PAD.top + 3, textAnchor: 'end',
        fontFamily: 'monospace', fontSize: 12, fill: 'rgba(255,255,255,0.4)',
      }, fmtUsd(maxP)),
      h('text', {
        x: PAD.left - 4, y: PAD.top + cH + 2, textAnchor: 'end',
        fontFamily: 'monospace', fontSize: 12, fill: 'rgba(255,255,255,0.4)',
      }, fmtUsd(minP)),
    ),
  );
}

// ─── Main Component ────────────────────────────────────────────────────────
export default function ScenarioAnalysis(props) {
  const runtimeProp = props && props.runtime;
  const optStateProp = props && props.optimizationState;

  // Authoritative baseline loaded from latest pipeline output
  const baseline = useMemo(() => {
    return extractBaselineState(runtimeProp || optStateProp);
  }, [runtimeProp, optStateProp]);

  // Active scenario state
  const [activeScenarios, setActiveScenarios] = useState([]);
  const [parameters, setParameters] = useState(DEFAULT_PARAMETERS);
  const [serviceSearch, setServiceSearch] = useState('');
  const [serviceRegionFilter, setServiceRegionFilter] = useState('ALL');
  const [serviceStatusFilter, setServiceStatusFilter] = useState('ALL');
  const [inspectedService, setInspectedService] = useState(null);

  // Toggle single scenario
  const toggleScenario = useCallback((scenarioKey) => {
    setActiveScenarios(prev =>
      prev.includes(scenarioKey)
        ? prev.filter(k => k !== scenarioKey)
        : [...prev, scenarioKey]
    );
  }, []);

  // Apply Preset
  const applyPreset = useCallback((preset) => {
    setActiveScenarios(preset.activeScenarios || []);
    setParameters(prev => ({
      ...prev,
      ...preset.parameters,
    }));
  }, []);

  // Reset Scenarios to Nominal Baseline
  const handleReset = useCallback(() => {
    setActiveScenarios([]);
    setParameters(DEFAULT_PARAMETERS);
    setInspectedService(null);
  }, []);

  // Evaluate scenario deterministically in-memory
  const scenarioResult = useMemo(() => {
    return evaluateScenario(baseline, activeScenarios, parameters);
  }, [baseline, activeScenarios, parameters]);

  // Filtered services list
  const filteredServices = useMemo(() => {
    if (!scenarioResult) return [];
    return scenarioResult.services.filter(s => {
      if (serviceRegionFilter !== 'ALL' && s.region.toLowerCase() !== serviceRegionFilter.toLowerCase()) return false;
      if (serviceStatusFilter !== 'ALL' && s.status !== serviceStatusFilter) return false;
      if (serviceSearch.trim()) {
        const query = serviceSearch.toLowerCase().trim();
        const idMatch = s.id.toLowerCase().includes(query);
        const portMatch = s.ports.some(p => p.toLowerCase().includes(query));
        const vMatch = s.vessel_class.toLowerCase().includes(query);
        if (!idMatch && !portMatch && !vMatch) return false;
      }
      return true;
    });
  }, [scenarioResult, serviceRegionFilter, serviceStatusFilter, serviceSearch]);

  if (!baseline) {
    return h('div', { className: 'cx-page-body', style: { padding: 24, textAlign: 'center' } },
      h('div', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-amber)' } },
        'INITIALIZING SCENARIO PLAYGROUND: Awaiting authoritative baseline from pipeline_output.json...'
      ),
    );
  }

  const eco = scenarioResult.economics;
  const ops = scenarioResult.operations;
  const sev = scenarioResult.severity;
  const isShockActive = activeScenarios.length > 0;

  return h(F, null,
    h(PageHead, {
      section: 'AI Operations',
      eyebrow: 'Decision Support Sandbox',
      title: 'Scenario Analysis',
      subtitle: 'What-if sensitivity analysis and stress-testing sandbox. Simulates economic shocks, metocean weather, and maritime canal disruptions over the baseline solution.',
      pills: [
        { tone: 'selected', label: `BASELINE ITER ${String(baseline.selectedIteration).padStart(2, '0')}` },
        { tone: isShockActive ? 'warn' : 'good', label: isShockActive ? `${activeScenarios.length} SHOCKS ACTIVE` : 'NOMINAL BASELINE' },
        { tone: sev.level === 'CRITICAL' || sev.level === 'HIGH' ? 'bad' : sev.level === 'MODERATE' ? 'warn' : 'good', label: sev.badge },
        { tone: 'available', label: `${ops.servicesDeployed} ACTIVE SVCS` },
      ],
    }),

    h('div', { className: 'cx-page-body' },

      // ── Top Control & Presets Strip ──────────────────────────────────────
      h('div', {
        style: {
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'var(--cx-panel-bg)',
          border: '1px solid var(--cx-edge-soft)',
          padding: '8px 12px',
          marginBottom: 12,
          borderRadius: 2,
          flexWrap: 'wrap',
          gap: 8,
        },
      },
        h('div', { style: { display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' } },
          h('span', {
            style: {
              fontFamily: 'var(--cx-mono)', fontSize: 12,
              color: 'var(--cx-text-faint)', textTransform: 'uppercase', letterSpacing: '0.1em',
              marginRight: 4,
            },
          }, 'Quick Presets:'),
          SCENARIO_PRESETS.map(p =>
            h('button', {
              key: p.id,
              type: 'button',
              onClick: () => applyPreset(p),
              style: {
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid var(--cx-edge-soft)',
                color: 'var(--cx-text-dim)',
                fontFamily: 'var(--cx-mono)',
                fontSize: 12,
                padding: '3px 8px',
                cursor: 'pointer',
                borderRadius: 2,
                transition: 'all 0.15s ease',
              },
              onMouseOver: e => { e.currentTarget.style.borderColor = 'var(--cx-cyan-2)'; e.currentTarget.style.color = '#fff'; },
              onMouseOut: e => { e.currentTarget.style.borderColor = 'var(--cx-edge-soft)'; e.currentTarget.style.color = 'var(--cx-text-dim)'; },
            }, p.name)
          ),
        ),
        h('div', { style: { display: 'flex', gap: 8 } },
          h('button', {
            type: 'button',
            onClick: handleReset,
            style: {
              background: 'rgba(239,68,68,0.1)',
              border: '1px solid rgba(239,68,68,0.3)',
              color: '#ef4444',
              fontFamily: 'var(--cx-mono)',
              fontSize: 12,
              fontWeight: 600,
              padding: '4px 10px',
              cursor: 'pointer',
              borderRadius: 2,
            },
          }, 'RESET ALL SHOCKS'),
        ),
      ),

      // ── ROW 1: Telemetry & Overview Cards (4 Equal-Height Grid) ───────────
      h('div', { className: 'cx-grid-12 sa-row-stretch', style: { marginBottom: 12 } },
        // Card 1: Weekly Profit Shift
        h('div', { className: 'cx-span-3' },
          h(InstrumentPanel, {
            title: 'Weekly Net Profit',
            right: isShockActive ? 'WHAT-IF IMPACT' : 'BASELINE',
          },
            h('div', { style: { flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' } },
              h(Stat, {
                k: 'Scenario Profit',
                v: fmtUsd(eco.weeklyProfit),
                variant: eco.deltas.weeklyProfit >= 0 ? 'good' : 'bad',
                sub: isShockActive ? `Delta: ${fmtDeltaUsd(eco.deltas.weeklyProfit)} (${((eco.deltas.weeklyProfit / baseline.weeklyProfit) * 100).toFixed(1)}%)` : 'Nominal baseline solution',
              }),
              h('div', {
                style: {
                  display: 'flex', justifyContent: 'space-between',
                  fontFamily: 'var(--cx-mono)', fontSize: 12,
                  color: 'var(--cx-text-faint)', borderTop: '1px solid var(--cx-edge-soft)',
                  paddingTop: 4, marginTop: 4,
                },
              },
                h('span', null, 'Baseline: ' + fmtUsd(baseline.weeklyProfit)),
                h('span', { style: { color: deltaColor(eco.deltas.weeklyProfit) } }, isShockActive ? fmtDeltaUsd(eco.deltas.weeklyProfit) : 'Nominal'),
              ),
            ),
          )
        ),
        // Card 2: Demand Coverage Shift
        h('div', { className: 'cx-span-3' },
          h(InstrumentPanel, {
            title: 'Global Demand Coverage',
            right: `${fmtPct(ops.coverage)} EFF`,
          },
            h('div', { style: { flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' } },
              h(Stat, {
                k: 'Effective Coverage',
                v: fmtPct(ops.coverage),
                variant: ops.deltas.coverage >= 0 ? 'good' : 'warn',
                sub: `Served: ${fmtNum(ops.satisfiedDemand)} / ${fmtNum(baseline.totalDemand)} TEU`,
              }),
              h('div', {
                style: {
                  display: 'flex', justifyContent: 'space-between',
                  fontFamily: 'var(--cx-mono)', fontSize: 12,
                  color: 'var(--cx-text-faint)', borderTop: '1px solid var(--cx-edge-soft)',
                  paddingTop: 4, marginTop: 4,
                },
              },
                h('span', null, 'Baseline: ' + fmtPct(baseline.coverage)),
                h('span', { style: { color: deltaColor(ops.deltas.coverage) } }, isShockActive ? fmtDeltaPct(ops.deltas.coverage) : '+0.0 pp'),
              ),
            ),
          )
        ),
        // Card 3: Active Scenarios Pill List
        h('div', { className: 'cx-span-3' },
          h(InstrumentPanel, {
            title: 'Active Scenarios',
            right: `${activeScenarios.length} ENABLED`,
          },
            h('div', { style: { flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' } },
              activeScenarios.length > 0
                ? h('div', { style: { display: 'flex', flexDirection: 'column', gap: 4 } },
                    activeScenarios.map(scKey =>
                      h('div', {
                        key: scKey,
                        style: {
                          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                          background: 'rgba(0,245,255,0.06)', border: '1px solid var(--cx-edge-soft)',
                          padding: '3px 6px', borderRadius: 2, fontFamily: 'var(--cx-mono)', fontSize: 12,
                        },
                      },
                        h('span', { style: { color: 'var(--cx-cyan-2)' } }, scKey.replace(/_/g, ' ').toUpperCase()),
                        h('button', {
                          type: 'button',
                          onClick: () => toggleScenario(scKey),
                          style: { background: 'none', border: 'none', color: 'var(--cx-text-faint)', cursor: 'pointer', fontSize: 12 },
                        }, '✕'),
                      )
                    ),
                  )
                : h(Stat, {
                    k: 'Scenario State',
                    v: '0 Shocks Active',
                    variant: 'good',
                    sub: 'Nominal baseline envelope active',
                  }),
              h('div', {
                style: {
                  display: 'flex', justifyContent: 'space-between',
                  fontFamily: 'var(--cx-mono)', fontSize: 12,
                  color: 'var(--cx-text-faint)', borderTop: '1px solid var(--cx-edge-soft)',
                  paddingTop: 4, marginTop: 4,
                },
              },
                h('span', null, 'Mode: In-Memory Sandbox'),
                h('span', { style: { color: isShockActive ? 'var(--cx-amber)' : 'var(--cx-green)' } }, isShockActive ? `${activeScenarios.length} Applied` : 'Nominal'),
              ),
            ),
          )
        ),
        // Card 4: Scenario Severity Indicator
        h('div', { className: 'cx-span-3' },
          h(InstrumentPanel, {
            title: 'Scenario Severity',
            right: sev.level,
          },
            h('div', { style: { flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' } },
              h(Stat, {
                k: 'Impact Classification',
                v: sev.badge,
                variant: sev.level === 'CRITICAL' || sev.level === 'HIGH' ? 'bad' : sev.level === 'MODERATE' ? 'warn' : 'good',
                sub: isShockActive
                  ? `${ops.countAffected + ops.countDegraded + ops.countUnavailable} svcs impacted · Shift: ${((eco.deltas.weeklyProfit / (baseline.weeklyProfit || 1)) * 100).toFixed(1)}%`
                  : 'Zero operational or economic disruptions detected',
              }),
              h('div', {
                style: {
                  display: 'flex', justifyContent: 'space-between',
                  fontFamily: 'var(--cx-mono)', fontSize: 12,
                  color: 'var(--cx-text-faint)', borderTop: '1px solid var(--cx-edge-soft)',
                  paddingTop: 4, marginTop: 4,
                },
              },
                h('span', null, `Tier: ${sev.level}`),
                h('span', { style: { color: sev.color, fontWeight: 700 } }, sev.badge),
              ),
            ),
          )
        ),
      ),

      // ── ROW 2: Scenario Selector & Dynamic Parameter Workbench (Equal-Height) ──
      h('div', { className: 'cx-grid-12 sa-row-stretch', style: { marginBottom: 12 } },
        // Left: Scenario Category & Checkbox Toggles
        h('div', { className: 'cx-span-5' },
          h(InstrumentPanel, {
            title: 'Scenario Category Selector',
            right: 'toggle shocks',
          },
            h('div', { style: { flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: 6 } },
              // 1. Fuel Cost Shock
              h('label', {
                style: {
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '6px 8px', background: activeScenarios.includes('fuel_cost') ? 'rgba(251,191,36,0.1)' : 'rgba(255,255,255,0.02)',
                  border: `1px solid ${activeScenarios.includes('fuel_cost') ? '#fbbf24' : 'var(--cx-edge-soft)'}`,
                  borderRadius: 2, cursor: 'pointer', flex: 1,
                },
              },
                h('div', { style: { display: 'flex', alignItems: 'center', gap: 8 } },
                  h('input', {
                    type: 'checkbox',
                    checked: activeScenarios.includes('fuel_cost'),
                    onChange: () => toggleScenario('fuel_cost'),
                  }),
                  h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, fontWeight: 600, color: 'var(--cx-text)' } },
                    '💲 Bunker Fuel Price Shift'
                  ),
                ),
                h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: '#fbbf24', fontWeight: 600 } },
                  activeScenarios.includes('fuel_cost') ? `${Math.round((parameters.fuelPriceMultiplier - 1) * 100)}%` : 'OFF'
                ),
              ),

              // 2. Weather & Metocean Severity
              h('label', {
                style: {
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '6px 8px', background: activeScenarios.includes('weather_severity') ? 'rgba(56,189,248,0.1)' : 'rgba(255,255,255,0.02)',
                  border: `1px solid ${activeScenarios.includes('weather_severity') ? '#38bdf8' : 'var(--cx-edge-soft)'}`,
                  borderRadius: 2, cursor: 'pointer', flex: 1,
                },
              },
                h('div', { style: { display: 'flex', alignItems: 'center', gap: 8 } },
                  h('input', {
                    type: 'checkbox',
                    checked: activeScenarios.includes('weather_severity'),
                    onChange: () => toggleScenario('weather_severity'),
                  }),
                  h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, fontWeight: 600, color: 'var(--cx-text)' } },
                    '🌊 Metocean Storm & Speed Cut'
                  ),
                ),
                h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: '#38bdf8', fontWeight: 600 } },
                  activeScenarios.includes('weather_severity') ? `${Math.round(parameters.weatherSpeedFactor * 100)}% Spd` : 'OFF'
                ),
              ),

              // 3. Chokepoint Transit Congestion
              h('label', {
                style: {
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '6px 8px', background: activeScenarios.includes('chokepoint_delay') ? 'rgba(245,158,11,0.1)' : 'rgba(255,255,255,0.02)',
                  border: `1px solid ${activeScenarios.includes('chokepoint_delay') ? '#f59e0b' : 'var(--cx-edge-soft)'}`,
                  borderRadius: 2, cursor: 'pointer', flex: 1,
                },
              },
                h('div', { style: { display: 'flex', alignItems: 'center', gap: 8 } },
                  h('input', {
                    type: 'checkbox',
                    checked: activeScenarios.includes('chokepoint_delay'),
                    onChange: () => toggleScenario('chokepoint_delay'),
                  }),
                  h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, fontWeight: 600, color: 'var(--cx-text)' } },
                    '⚓ Canal / Chokepoint Queue'
                  ),
                ),
                h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: '#f59e0b', fontWeight: 600 } },
                  activeScenarios.includes('chokepoint_delay') ? `+${parameters.chokepointDelayHours}h` : 'OFF'
                ),
              ),

              // 4. Port Terminal Closure
              h('label', {
                style: {
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '6px 8px', background: activeScenarios.includes('port_closure') ? 'rgba(239,68,68,0.1)' : 'rgba(255,255,255,0.02)',
                  border: `1px solid ${activeScenarios.includes('port_closure') ? '#ef4444' : 'var(--cx-edge-soft)'}`,
                  borderRadius: 2, cursor: 'pointer', flex: 1,
                },
              },
                h('div', { style: { display: 'flex', alignItems: 'center', gap: 8 } },
                  h('input', {
                    type: 'checkbox',
                    checked: activeScenarios.includes('port_closure'),
                    onChange: () => toggleScenario('port_closure'),
                  }),
                  h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, fontWeight: 600, color: 'var(--cx-text)' } },
                    '🚫 Port Terminal Closure'
                  ),
                ),
                h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: '#ef4444', fontWeight: 600 } },
                  activeScenarios.includes('port_closure') ? (parameters.closedPortCode || 'USLAX') : 'OFF'
                ),
              ),

              // 5. Demand Shift
              h('label', {
                style: {
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '6px 8px', background: activeScenarios.includes('demand_change') ? 'rgba(167,139,250,0.1)' : 'rgba(255,255,255,0.02)',
                  border: `1px solid ${activeScenarios.includes('demand_change') ? '#a78bfa' : 'var(--cx-edge-soft)'}`,
                  borderRadius: 2, cursor: 'pointer', flex: 1,
                },
              },
                h('div', { style: { display: 'flex', alignItems: 'center', gap: 8 } },
                  h('input', {
                    type: 'checkbox',
                    checked: activeScenarios.includes('demand_change'),
                    onChange: () => toggleScenario('demand_change'),
                  }),
                  h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, fontWeight: 600, color: 'var(--cx-text)' } },
                    '📦 Demand Surge / Contraction'
                  ),
                ),
                h('span', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: '#a78bfa', fontWeight: 600 } },
                  activeScenarios.includes('demand_change') ? `${Math.round((parameters.globalDemandMultiplier - 1) * 100)}%` : 'OFF'
                ),
              ),
            )
          )
        ),

        // Right: Dynamic Parameter Workbench Controls
        h('div', { className: 'cx-span-7' },
          h(InstrumentPanel, {
            title: 'Scenario Parameter Workbench',
            right: 'live sliders',
          },
            h('div', { style: { flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: 10 } },
              // 1. Fuel Slider
              h('div', { style: { opacity: activeScenarios.includes('fuel_cost') ? 1 : 0.45 } },
                h('div', { style: { display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--cx-mono)', fontSize: 12, marginBottom: 3 } },
                  h('span', { style: { color: 'var(--cx-text-dim)' } }, 'BUNKER FUEL PRICE MULTIPLIER:'),
                  h('span', { style: { color: '#fbbf24', fontWeight: 700 } }, `${(parameters.fuelPriceMultiplier).toFixed(2)}× (${parameters.fuelPriceMultiplier >= 1 ? '+' : ''}${Math.round((parameters.fuelPriceMultiplier - 1) * 100)}%)`),
                ),
                h('input', {
                  type: 'range', min: 0.50, max: 2.50, step: 0.05,
                  value: parameters.fuelPriceMultiplier,
                  disabled: !activeScenarios.includes('fuel_cost'),
                  onChange: e => setParameters(p => ({ ...p, fuelPriceMultiplier: parseFloat(e.target.value) })),
                  style: { width: '100%', cursor: 'pointer' },
                }),
              ),

              // 2. Weather Speed Factor Slider
              h('div', { style: { opacity: activeScenarios.includes('weather_severity') ? 1 : 0.45 } },
                h('div', { style: { display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--cx-mono)', fontSize: 12, marginBottom: 3 } },
                  h('span', { style: { color: 'var(--cx-text-dim)' } }, 'WEATHER STEAMING SPEED FACTOR:'),
                  h('span', { style: { color: '#38bdf8', fontWeight: 700 } }, `${Math.round(parameters.weatherSpeedFactor * 100)}% (${Math.round((1 - parameters.weatherSpeedFactor) * 100)}% speed cut)`),
                ),
                h('input', {
                  type: 'range', min: 0.50, max: 1.0, step: 0.05,
                  value: parameters.weatherSpeedFactor,
                  disabled: !activeScenarios.includes('weather_severity'),
                  onChange: e => setParameters(p => ({ ...p, weatherSpeedFactor: parseFloat(e.target.value) })),
                  style: { width: '100%', cursor: 'pointer' },
                }),
              ),

              // 3. Chokepoint Selection & Delay Hours
              h('div', {
                style: {
                  display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10,
                  opacity: activeScenarios.includes('chokepoint_delay') ? 1 : 0.45,
                },
              },
                h('div', null,
                  h('div', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-dim)', marginBottom: 3 } }, 'CHOKEPOINT:'),
                  h('select', {
                    value: parameters.chokepointId,
                    disabled: !activeScenarios.includes('chokepoint_delay'),
                    onChange: e => setParameters(p => ({ ...p, chokepointId: e.target.value })),
                    style: { width: '100%', background: 'var(--cx-bg-3)', color: 'var(--cx-text)', border: '1px solid var(--cx-edge-soft)', padding: '3px 6px', fontFamily: 'var(--cx-mono)', fontSize: 12 },
                  },
                    h('option', { value: 'suez' }, 'Suez Canal (12% Global Trade)'),
                    h('option', { value: 'panama' }, 'Panama Canal (5% Global Trade)'),
                    h('option', { value: 'malacca' }, 'Strait of Malacca (25% Trade)'),
                    h('option', { value: 'hormuz' }, 'Strait of Hormuz (Oil Gateway)'),
                    h('option', { value: 'bab_el_mandeb' }, 'Bab el-Mandeb (Red Sea)'),
                  ),
                ),
                h('div', null,
                  h('div', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-dim)', marginBottom: 3 } },
                    `TRANSIT DELAY: +${parameters.chokepointDelayHours} HOURS`
                  ),
                  h('input', {
                    type: 'range', min: 0, max: 168, step: 12,
                    value: parameters.chokepointDelayHours,
                    disabled: !activeScenarios.includes('chokepoint_delay'),
                    onChange: e => setParameters(p => ({ ...p, chokepointDelayHours: parseInt(e.target.value, 10) })),
                    style: { width: '100%', cursor: 'pointer' },
                  }),
                ),
              ),

              // 4. Port Closure Selector & Demand Multiplier
              h('div', {
                style: {
                  display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10,
                },
              },
                h('div', { style: { opacity: activeScenarios.includes('port_closure') ? 1 : 0.45 } },
                  h('div', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-dim)', marginBottom: 3 } }, 'TERMINAL CLOSURE:'),
                  h('select', {
                    value: parameters.closedPortCode,
                    disabled: !activeScenarios.includes('port_closure'),
                    onChange: e => setParameters(p => ({ ...p, closedPortCode: e.target.value })),
                    style: { width: '100%', background: 'var(--cx-bg-3)', color: 'var(--cx-text)', border: '1px solid var(--cx-edge-soft)', padding: '3px 6px', fontFamily: 'var(--cx-mono)', fontSize: 12 },
                  },
                    h('option', { value: 'USLAX' }, 'USLAX — Port of Los Angeles'),
                    h('option', { value: 'NLRTM' }, 'NLRTM — Port of Rotterdam'),
                    h('option', { value: 'CNSHA' }, 'CNSHA — Port of Shanghai'),
                    h('option', { value: 'SGSIN' }, 'SGSIN — Port of Singapore'),
                    h('option', { value: 'DEBRV' }, 'DEBRV — Bremerhaven'),
                    h('option', { value: 'USEWR' }, 'USEWR — Port of New York/NJ'),
                  ),
                ),
                h('div', { style: { opacity: activeScenarios.includes('demand_change') ? 1 : 0.45 } },
                  h('div', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-dim)', marginBottom: 3 } },
                    `DEMAND SCALE: ${parameters.globalDemandMultiplier >= 1 ? '+' : ''}${Math.round((parameters.globalDemandMultiplier - 1) * 100)}%`
                  ),
                  h('input', {
                    type: 'range', min: 0.50, max: 1.50, step: 0.05,
                    value: parameters.globalDemandMultiplier,
                    disabled: !activeScenarios.includes('demand_change'),
                    onChange: e => setParameters(p => ({ ...p, globalDemandMultiplier: parseFloat(e.target.value) })),
                    style: { width: '100%', cursor: 'pointer' },
                  }),
                ),
              ),
            )
          )
        ),
      ),

      // ── ROW 3: Baseline vs Scenario Matrix (Economics & Operations) ────────
      h('div', { className: 'cx-grid-12 sa-row-stretch', style: { marginBottom: 12 } },
        // Left: Economic Breakdown Matrix
        h('div', { className: 'cx-span-6' },
          h(InstrumentPanel, {
            title: 'Baseline vs Scenario Economics',
            right: 'monetary impact',
          },
            h('div', {
              style: {
                display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr 1fr',
                fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-faint)',
                borderBottom: '1px solid var(--cx-edge-soft)', paddingBottom: 3, marginBottom: 4,
              },
            },
              h('span', null, 'METRIC'),
              h('span', { style: { textAlign: 'right' } }, 'BASELINE'),
              h('span', { style: { textAlign: 'right' } }, 'SCENARIO'),
              h('span', { style: { textAlign: 'right' } }, 'DELTA'),
            ),
            h(ComparisonRow, { label: 'Weekly Net Profit', base: baseline.weeklyProfit, scenario: eco.weeklyProfit, delta: eco.deltas.weeklyProfit, isUsd: true }),
            h(ComparisonRow, { label: 'Annual Net Profit', base: baseline.annualProfit, scenario: eco.annualProfit, delta: eco.deltas.annualProfit, isUsd: true }),
            h(ComparisonRow, { label: 'Gross Revenue', base: baseline.revenue, scenario: eco.revenue, delta: eco.deltas.revenue, isUsd: true }),
            h(ComparisonRow, { label: 'Bunker Fuel Cost', base: baseline.fuelCost, scenario: eco.fuelCost, delta: eco.deltas.fuelCost, isUsd: true, invertDelta: true }),
            h(ComparisonRow, { label: 'Port Tariff Fees', base: baseline.portCost, scenario: eco.portCost, delta: eco.deltas.portCost, isUsd: true, invertDelta: true }),
            h(ComparisonRow, { label: 'Total Network Cost', base: baseline.totalCost, scenario: eco.totalCost, delta: eco.deltas.totalCost, isUsd: true, invertDelta: true }),
            h(ComparisonRow, { label: 'Operating Margin', base: baseline.profitMargin, scenario: eco.profitMargin, delta: eco.deltas.margin, isPct: true }),
          )
        ),
        // Right: Operational Breakdown Matrix
        h('div', { className: 'cx-span-6' },
          h(InstrumentPanel, {
            title: 'Baseline vs Scenario Operations',
            right: 'service & cargo metrics',
          },
            h('div', {
              style: {
                display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr 1fr',
                fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-faint)',
                borderBottom: '1px solid var(--cx-edge-soft)', paddingBottom: 3, marginBottom: 4,
              },
            },
              h('span', null, 'OPERATIONAL METRIC'),
              h('span', { style: { textAlign: 'right' } }, 'BASELINE'),
              h('span', { style: { textAlign: 'right' } }, 'SCENARIO'),
              h('span', { style: { textAlign: 'right' } }, 'DELTA'),
            ),
            h(ComparisonRow, { label: 'Demand Coverage', base: baseline.coverage, scenario: ops.coverage, delta: ops.deltas.coverage, isPct: true }),
            h(ComparisonRow, { label: 'Satisfied Demand', base: baseline.satisfiedDemand, scenario: ops.satisfiedDemand, delta: ops.deltas.satisfiedDemand }),
            h(ComparisonRow, { label: 'Unserved Demand', base: baseline.unservedDemand, scenario: ops.unservedDemand, delta: ops.deltas.unservedDemand, invertDelta: true }),
            h(ComparisonRow, { label: 'Active Services', base: baseline.totalServices, scenario: ops.servicesDeployed, delta: ops.deltas.servicesDeployed }),
            h(ComparisonRow, { label: 'Degraded Services', base: 0, scenario: ops.countDegraded, delta: ops.countDegraded, invertDelta: true }),
            h(ComparisonRow, { label: 'Unavailable / Cut', base: 0, scenario: ops.countUnavailable, delta: ops.countUnavailable, invertDelta: true }),
            h(ComparisonRow, { label: 'Cumulative Delay', base: 0, scenario: ops.totalDelayHours, delta: ops.totalDelayHours, invertDelta: true }),
          )
        ),
      ),

      // ── ROW 4: Service Impact Table & Regional Impact Grid (Equal-Height) ──
      h('div', { className: 'cx-grid-12 sa-row-stretch', style: { marginBottom: 12 } },
        // Left: Service Impact Table
        h('div', { className: 'cx-span-7' },
          h(InstrumentPanel, {
            title: 'Service Impact Explorer',
            right: `${filteredServices.length} / ${scenarioResult.services.length} SVCS`,
          },
            // Filters Strip
            h('div', {
              style: {
                display: 'flex', gap: 6, marginBottom: 6, alignItems: 'center', flexWrap: 'wrap',
              },
            },
              h('input', {
                type: 'text',
                placeholder: 'Filter by ID, port, vessel...',
                value: serviceSearch,
                onChange: e => setServiceSearch(e.target.value),
                style: {
                  flex: 1, minWidth: 120, background: 'var(--cx-bg-3)', color: 'var(--cx-text)',
                  border: '1px solid var(--cx-edge-soft)', padding: '3px 6px',
                  fontFamily: 'var(--cx-mono)', fontSize: 12, borderRadius: 2,
                },
              }),
              h('select', {
                value: serviceRegionFilter,
                onChange: e => setServiceRegionFilter(e.target.value),
                style: { background: 'var(--cx-bg-3)', color: 'var(--cx-text)', border: '1px solid var(--cx-edge-soft)', padding: '3px 6px', fontFamily: 'var(--cx-mono)', fontSize: 12 },
              },
                h('option', { value: 'ALL' }, 'All Regions'),
                h('option', { value: 'Asia' }, 'Asia'),
                h('option', { value: 'Europe' }, 'Europe'),
                h('option', { value: 'Americas' }, 'Americas'),
                h('option', { value: 'Middle East' }, 'Middle East'),
                h('option', { value: 'Africa' }, 'Africa'),
              ),
              h('select', {
                value: serviceStatusFilter,
                onChange: e => setServiceStatusFilter(e.target.value),
                style: { background: 'var(--cx-bg-3)', color: 'var(--cx-text)', border: '1px solid var(--cx-edge-soft)', padding: '3px 6px', fontFamily: 'var(--cx-mono)', fontSize: 12 },
              },
                h('option', { value: 'ALL' }, 'All Statuses'),
                h('option', { value: 'UNAFFECTED' }, 'Nominal'),
                h('option', { value: 'AFFECTED' }, 'Affected'),
                h('option', { value: 'DEGRADED' }, 'Degraded'),
                h('option', { value: 'AT RISK' }, 'At Risk'),
                h('option', { value: 'UNAVAILABLE' }, 'Unavailable'),
              ),
            ),
            // Table with fixed scroll window
            h('div', { style: { height: 230, overflowY: 'auto' } },
              h('table', {
                style: { width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--cx-mono)', fontSize: 12 },
              },
                h('thead', null,
                  h('tr', { style: { borderBottom: '1px solid var(--cx-edge-soft)', color: 'var(--cx-text-faint)', textAlign: 'left' } },
                    h('th', { style: { padding: '4px 6px' } }, 'SERVICE'),
                    h('th', { style: { padding: '4px 6px' } }, 'REGION'),
                    h('th', { style: { padding: '4px 6px', textAlign: 'right' } }, 'BASE PROFIT'),
                    h('th', { style: { padding: '4px 6px', textAlign: 'right' } }, 'SCEN PROFIT'),
                    h('th', { style: { padding: '4px 6px', textAlign: 'right' } }, 'DELTA'),
                    h('th', { style: { padding: '4px 6px', textAlign: 'center' } }, 'STATUS'),
                  ),
                ),
                h('tbody', null,
                  filteredServices.slice(0, 50).map(s => {
                    const statusColor = s.status === 'UNAVAILABLE' ? '#ef4444'
                                      : s.status === 'DEGRADED' ? '#f59e0b'
                                      : s.status === 'AT RISK' ? '#ec4899'
                                      : s.status === 'AFFECTED' ? '#38bdf8'
                                      : 'var(--cx-text-faint)';
                    return h('tr', {
                      key: s.id,
                      onClick: () => setInspectedService(s),
                      style: {
                        borderBottom: '1px solid rgba(255,255,255,0.03)',
                        cursor: 'pointer',
                        background: inspectedService?.id === s.id ? 'rgba(0,245,255,0.08)' : 'transparent',
                      },
                    },
                      h('td', { style: { padding: '3px 6px', color: 'var(--cx-cyan-2)', fontWeight: 600 } }, s.id),
                      h('td', { style: { padding: '3px 6px', color: 'var(--cx-text-dim)' } }, s.region),
                      h('td', { style: { padding: '3px 6px', textAlign: 'right', color: 'var(--cx-text-faint)' } }, fmtUsd(s.baseline_profit)),
                      h('td', { style: { padding: '3px 6px', textAlign: 'right', color: 'var(--cx-text)', fontWeight: 600 } }, fmtUsd(s.scenario_profit)),
                      h('td', { style: { padding: '3px 6px', textAlign: 'right', color: deltaColor(s.delta_profit), fontWeight: 700 } }, fmtDeltaUsd(s.delta_profit)),
                      h('td', { style: { padding: '3px 6px', textAlign: 'center' } },
                        h('span', {
                          style: {
                            background: `${statusColor}22`, border: `1px solid ${statusColor}66`,
                            color: statusColor, padding: '1px 5px', borderRadius: 2, fontSize: 12, fontWeight: 700,
                          },
                        }, s.status)
                      ),
                    );
                  }),
                ),
              ),
            ),
          )
        ),

        // Right: Regional Impact Cards (Stretched with Bottom Summary)
        h('div', { className: 'cx-span-5' },
          h(InstrumentPanel, {
            title: 'Regional Trade Zone Sensitivity',
            right: '5 regions',
          },
            h('div', { style: { flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' } },
              h('div', { style: { flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: 5 } },
                scenarioResult.regionalImpacts.map(reg =>
                  h('div', {
                    key: reg.name,
                    style: {
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      background: 'rgba(255,255,255,0.02)', border: '1px solid var(--cx-edge-soft)',
                      padding: '5px 8px', borderRadius: 2, fontFamily: 'var(--cx-mono)', fontSize: 12,
                      flex: 1,
                    },
                  },
                    h('div', null,
                      h('div', { style: { color: 'var(--cx-text)', fontWeight: 600 } }, reg.name),
                      h('div', { style: { color: 'var(--cx-text-faint)', fontSize: 12 } },
                        `${reg.scenario_services} svcs · Cov: ${fmtPct(reg.scenario_coverage)} (${fmtDeltaPct(reg.delta_coverage)})`
                      ),
                    ),
                    h('div', { style: { textAlign: 'right' } },
                      h('div', { style: { color: reg.scenario_profit >= 0 ? 'var(--cx-green)' : 'var(--cx-red)', fontWeight: 700 } },
                        fmtUsd(reg.scenario_profit)
                      ),
                      h('div', { style: { color: deltaColor(reg.delta_profit), fontSize: 12 } },
                        isShockActive ? fmtDeltaUsd(reg.delta_profit) : 'Nominal'
                      ),
                    ),
                  )
                ),
              ),
              h('div', {
                style: {
                  display: 'flex', justifyContent: 'space-between',
                  fontFamily: 'var(--cx-mono)', fontSize: 12,
                  color: 'var(--cx-text-faint)', borderTop: '1px solid var(--cx-edge-soft)',
                  paddingTop: 6, marginTop: 6,
                },
              },
                h('span', null, 'Total: 5 Trade Zones'),
                h('span', { style: { color: 'var(--cx-cyan-2)' } }, `${ops.servicesDeployed} Active Services · ${fmtPct(ops.coverage)} Cov`),
              ),
            ),
          )
        ),
      ),

      // ── ROW 5: Sensitivity Curve + Deterministic AI Analysis (Equal-Height) ─
      h('div', { className: 'cx-grid-12 sa-row-stretch', style: { marginBottom: 12 } },
        // Left: Dynamic Sensitivity Curve
        h('div', { className: 'cx-span-6' },
          h(InstrumentPanel, {
            title: 'Economic Sensitivity Model',
            right: 'non-linear response',
          },
            h('div', { style: { flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' } },
              h(SensitivityChart, {
                points: scenarioResult.sensitivityCurves.fuel,
                currentMult: parameters.fuelPriceMultiplier,
                title: 'Bunker Fuel Price Sensitivity ($ Net Weekly Profit)',
              }),
              h('div', {
                style: {
                  display: 'flex', justifyContent: 'space-between',
                  fontFamily: 'var(--cx-mono)', fontSize: 12,
                  color: 'var(--cx-text-faint)', borderTop: '1px solid var(--cx-edge-soft)',
                  paddingTop: 6, marginTop: 6,
                },
              },
                h('span', null, 'Evaluated Multipliers: -30% to +50%'),
                h('span', { style: { color: '#fbbf24', fontWeight: 600 } }, `Current Setting: ${(parameters.fuelPriceMultiplier).toFixed(2)}x`),
              ),
            ),
          )
        ),
        // Right: Deterministic AI Scenario Interpretation
        h('div', { className: 'cx-span-6' },
          h(InstrumentPanel, {
            title: 'AI Decision-Support & Operator Recommendations',
            right: 'authoritative synthesis',
          },
            h('div', { style: { flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: 6 } },
              h('div', null,
                h('div', {
                  style: {
                    fontFamily: 'var(--cx-mono)', fontSize: 12, fontWeight: 700, color: 'var(--cx-cyan-2)', marginBottom: 4,
                  },
                }, scenarioResult.explanations.headline),
                h('div', {
                  style: {
                    fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text)', lineHeight: 1.4,
                    background: 'rgba(0,0,0,0.25)', padding: '6px 8px', borderLeft: '3px solid var(--cx-cyan-2)',
                    marginBottom: 6,
                  },
                }, scenarioResult.explanations.riskAnalysis),
                h('div', {
                  style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-dim)' },
                },
                  h('span', { style: { color: 'var(--cx-amber)', fontWeight: 600 } }, 'Exposed Regions: '),
                  scenarioResult.explanations.exposedRegions
                ),
              ),
              h('div', { style: { marginTop: 2 } },
                h('div', { style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-faint)', textTransform: 'uppercase', marginBottom: 2 } }, 'Recommended Mitigations:'),
                scenarioResult.explanations.recommendations.map((rec, i) =>
                  h('div', {
                    key: i,
                    style: { fontFamily: 'var(--cx-mono)', fontSize: 12, color: 'var(--cx-text-dim)', marginBottom: 2 },
                  }, `▸ ${rec}`)
                ),
              ),
            ),
          )
        ),
      ),

      // ── Provenance Footer ──────────────────────────────────────────────────
      h(Provenance, {
        source: 'pipeline_output.json (summary_metrics, selected_services, regional_results)',
        sourceStatus: 'available',
        attribution: `${baseline.runId ?? 'run id unavailable'} · Canonical baseline: ITER ${String(baseline.selectedIteration).padStart(2, '0')}`,
        license: 'Internal what-if simulation',
        recordCount: baseline.totalServices,
        snapshotId: baseline.evaluatedAt,
      }),
    ),
  );
}
