/**
 * Benchmarks.jsx
 * --------------
 * The frozen 30-seed benchmark (Benchmark/seed-30, FREEZE_2026-10-24_seed30), read through the
 * read-only backend routes /api/benchmark/summary and /api/benchmark/<dataset>/seeds. Without a reachable
 * backend (or with one that predates the detail fields) the same rows come from the static bundle
 * /benchmark/seed30_bundle.json, written by scripts/build_benchmark_bundle.py from the same functions.
 *
 * Sections: dataset cards; per-seed strip plots of a chosen metric (each dataset on its own scale: they
 * differ by ~400x in profit) with mean and 95% CI and the summary table; profit vs coverage of one dataset;
 * cost structure; where the time goes; fleet deployment; transit; solver and reliability; seed explorer.
 * Clicking a seed anywhere opens that run in every tab.
 */

import { useEffect, useMemo, useState } from 'react';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import { Provenance } from '../../components/console/p12.jsx';
import { ProfitCoverage } from '../../components/charts/PlanCharts.jsx';
import {
  DatasetCards, CostStructure, StageTime, FleetDeployment, TransitQuality, SolverReliability, SeedExplorer,
} from '../../components/charts/BenchSections.jsx';
import { apiClient } from '../../services/apiClient.js';
import { setSelectedRun } from '../../services/runSelection.js';
import { fmtUsd } from '../../utils/formatters.js';
import { num, stats, niceTicks, flagged } from '../../utils/benchStats.js';

const EM = '—';
const DATASET_ORDER = ['baltic', 'WAF', 'worldsmall', 'world500', 'world1000'];
const BUNDLE_URL = '/benchmark/seed30_bundle.json';

const pct = (d = 1) => (v) => (v == null ? EM : `${Number(v).toFixed(d)}%`);
const secs = (v) => (v == null ? EM : v >= 120 ? `${(v / 60).toFixed(1)} min` : `${Number(v).toFixed(1)} s`);
const METRICS = [
  { id: 'weekly_profit_usd', label: 'Weekly profit', fmt: fmtUsd },
  { id: 'coverage_pct', label: 'Coverage', fmt: pct(1) },
  { id: 'margin_pct', label: 'Profit margin', fmt: pct(1), get: (r) => (num(r.profit_margin_on_revenue) == null ? null : r.profit_margin_on_revenue * 100) },
  { id: 'contribution_margin_pct', label: 'Contribution margin', fmt: pct(1) },
  { id: 'profit_per_assigned_vessel_usd', label: 'Profit per vessel', fmt: fmtUsd },
  { id: 'teu_util_pct', label: 'TEU utilisation', fmt: pct(1), get: (r) => (num(r.teu_utilisation_avg) == null ? null : r.teu_utilisation_avg * 100) },
  { id: 'transit_days_mean', label: 'Transit time', fmt: (v) => (v == null ? EM : `${Number(v).toFixed(1)} d`) },
  { id: 'transship_share_pct', label: 'Transshipped TEU', fmt: pct(1) },
  { id: 'gap_to_bound_pct', label: 'Gap to LP bound', fmt: pct(1) },
  { id: 't_milp_sec', label: 'MILP time', fmt: secs },
  { id: 'pipeline_sec', label: 'Pipeline time', fmt: secs },
];

/** Summary + seed rows: the live API when it answers with the detail fields, else the static bundle. */
async function loadBenchmark() {
  let apiErr = null;
  try {
    const sum = await apiClient.getBenchmarkSummary();
    const keys = Object.keys(sum?.datasets || {});
    const lists = await Promise.all(keys.map((k) => apiClient.getBenchmarkSeeds(k).then((r) => [k, r.seeds || []])));
    const seeds = Object.fromEntries(lists);
    const detailed = lists.every(([, l]) => !l.length || 'cost_fuel_usd' in l[0]);
    if (detailed) return { summary: sum, seeds, source: 'api' };
    apiErr = 'backend predates the detail fields';
  } catch (e) {
    apiErr = e?.message || 'unavailable';
  }
  const res = await fetch(BUNDLE_URL);
  if (!res.ok) throw new Error(`API: ${apiErr}; static snapshot: HTTP ${res.status}`);
  const b = await res.json();
  return { summary: b.summary, seeds: b.seeds, source: 'bundle', apiErr, bundleAt: b.bundle_generated_utc };
}
const valueOf = (m, r) => num(m.get ? m.get(r) : r[m.id]);


function StripPlot({ dsKey, label, rows, metric, onOpen }) {
  const [hover, setHover] = useState(null);
  const pts = rows.map((r) => ({ r, v: valueOf(metric, r) })).filter((p) => p.v != null);
  const s = stats(pts.filter((p) => !flagged(p.r)).map((p) => p.v));
  if (!pts.length || !s) return <div className="cx-compact-empty">No values for {metric.label.toLowerCase()} in {label}.</div>;

  const lo = Math.min(s.min, ...pts.map((p) => p.v));
  const hi = Math.max(s.max, ...pts.map((p) => p.v));
  const pad = (hi - lo) * 0.06 || Math.abs(hi) * 0.05 || 1;
  const x0 = lo - pad;
  const x1 = hi + pad;
  const X = (v) => ((v - x0) / (x1 - x0)) * 100;
  // Deterministic vertical spread: seeds are stacked into 5 lanes so near-equal values stay visible.
  const lane = (seed) => 18 + (seed % 5) * 14;
  const ticks = niceTicks(x0, x1, 4);
  const bad = pts.filter((p) => flagged(p.r));

  return (
    <div className="bm-strip" role="group" aria-label={`${label}: ${metric.label} by seed`}>
      <div className="bm-strip-plot">
        <div className="bm-ci" style={{ left: `${X(s.lo)}%`, width: `${Math.max(0.4, X(s.hi) - X(s.lo))}%` }} title={`95% CI of the mean: ${metric.fmt(s.lo)} – ${metric.fmt(s.hi)}`} />
        <div className="bm-mean" style={{ left: `${X(s.mean)}%` }} />
        <span className="bm-mean-label" style={{ left: `${X(s.mean)}%` }}>mean {metric.fmt(s.mean)}</span>
        {pts.map(({ r, v }) => (
          <button
            key={r.seed}
            type="button"
            className={`bm-dot ${flagged(r) ? 'is-flagged' : ''} ${hover && hover.r.seed === r.seed ? 'is-hover' : ''}`}
            style={{ left: `${X(v)}%`, top: lane(r.seed) }}
            aria-label={`Seed ${String(r.seed).padStart(2, '0')}: ${metric.fmt(v)}${flagged(r) ? ', flagged run' : ''}. Open this run.`}
            onMouseEnter={() => setHover({ r, v })}
            onMouseLeave={() => setHover(null)}
            onFocus={() => setHover({ r, v })}
            onBlur={() => setHover(null)}
            onClick={() => onOpen(dsKey, r.seed)}
          />
        ))}
        {hover && (
          <div className="bm-tip" style={{ left: `${Math.min(80, Math.max(20, X(hover.v)))}%` }} role="tooltip">
            <b>{label} · seed {String(hover.r.seed).padStart(2, '0')}</b>
            <span>{metric.label}: {metric.fmt(hover.v)}</span>
            <span>Profit {fmtUsd(hover.r.weekly_profit_usd)} · coverage {pct(1)(hover.r.coverage_pct)}</span>
            <span>LLM: {hover.r.llm_regime ? hover.r.llm_regime.replace(/_/g, ' ') : EM}</span>
            {flagged(hover.r) && <span className="bm-tip-flag">⚠ exit code {hover.r.exit_code}{hover.r.ledger_verified === false ? ', ledger not verified' : ''}; excluded from mean/CI</span>}
            <span className="bm-tip-hint">Click to open this run</span>
          </div>
        )}
      </div>
      <div className="bm-axis" aria-hidden="true">
        {ticks.map((t) => <span key={t} style={{ left: `${X(t)}%` }}>{metric.fmt(t)}</span>)}
      </div>
      {bad.length > 0 && (
        <div className="bm-flags">⚠ Flagged, excluded from mean and CI: {bad.map((p) => `seed ${String(p.r.seed).padStart(2, '0')} (exit ${p.r.exit_code})`).join(', ')}</div>
      )}
    </div>
  );
}

export default function Benchmarks() {
  const [summary, setSummary] = useState(null);
  const [seedsBy, setSeedsBy] = useState({});
  const [source, setSource] = useState(null);
  const [error, setError] = useState(null);
  const [metricId, setMetricId] = useState('weekly_profit_usd');
  const [focusDs, setFocusDs] = useState('worldsmall');
  const metric = METRICS.find((m) => m.id === metricId) || METRICS[0];

  useEffect(() => {
    let cancelled = false;
    loadBenchmark().then((r) => {
      if (cancelled) return;
      const keys = DATASET_ORDER.filter((k) => r.seeds[k]).concat(Object.keys(r.seeds).filter((k) => !DATASET_ORDER.includes(k)));
      setSummary(r.summary);
      setSeedsBy(Object.fromEntries(keys.map((k) => [k, r.seeds[k] || []])));
      setSource(r);
    }).catch((e) => { if (!cancelled) setError(e?.message || 'unavailable'); });
    return () => { cancelled = true; };
  }, []);

  const datasets = useMemo(() => Object.keys(seedsBy), [seedsBy]);

  const openRun = (dataset, seed) => {
    setSelectedRun({ kind: 'benchmark', dataset, seed });
    window.location.hash = '#/overview/command_center';
  };

  const rows = datasets.map((k) => {
    const ds = summary?.datasets?.[k] || {};
    const list = seedsBy[k] || [];
    const st = stats(list.filter((r) => !flagged(r)).map((r) => valueOf(metric, r)));
    const regimes = ds.llm_regimes || {};
    const repro = ds.reproducibility_vs_reference || {};
    return { k, label: ds.dataset || k, list, st, runs: ds.runs || {}, regimes, repro };
  });
  const focus = rows.find((r) => r.k === focusDs) || rows[0];
  const loading = !summary && !error;

  const dsPicker = (
    <div className="bm-ds-pick" role="radiogroup" aria-label="Dataset">
      {rows.map((r) => (
        <button key={r.k} type="button" role="radio" aria-checked={focus?.k === r.k} className={`bm-metric ${focus?.k === r.k ? 'is-active' : ''}`} onClick={() => setFocusDs(r.k)}>{r.label}</button>
      ))}
    </div>
  );

  return (
    <div className="cx-page-body space-y-3">
      <PageHead
        section="Benchmarks"
        eyebrow="Frozen 30-seed benchmark"
        title="Benchmarks"
        subtitle="Five datasets × 30 seeds, frozen on 24 Oct 2026. Each seed is a full pipeline run; failed runs are shown but left out of the mean and its 95% confidence interval. Click any seed to open that run in every tab."
        pills={[
          { tone: summary ? 'available' : error ? 'no_data' : 'unknown', label: summary ? `${datasets.length} datasets` : error ? 'unavailable' : 'loading' },
          { tone: 'converged', label: `${rows.reduce((a, r) => a + (r.runs.n_runs || r.list.length || 0), 0)} runs` },
          { tone: source?.source === 'bundle' ? 'unknown' : 'available', label: source ? (source.source === 'api' ? 'live API' : 'static snapshot') : 'source —' },
          { tone: 'unknown', label: summary?.generated_utc ? `summary ${summary.generated_utc.slice(0, 10)}` : 'summary —' },
        ]}
      />

      {error && <div className="cx-compact-empty" role="alert">Benchmark data unavailable ({error}). Start the backend (it serves Benchmark/seed-30 read-only) or rebuild the snapshot with <code>python scripts/build_benchmark_bundle.py</code>.</div>}
      {source?.source === 'bundle' && (
        <div className="bm-source-note" role="status">
          Showing the static snapshot of the frozen benchmark ({source.apiErr === 'backend predates the detail fields' ? 'the running backend predates the detail fields' : 'the backend API is not reachable from this dev server'}). The numbers are the same frozen seeds; opening a seed as a run needs the backend.
        </div>
      )}
      {loading && <div className="bm-loading" aria-busy="true">{Array.from({ length: 5 }, (_, i) => <div key={i} className="skel-block bm-skel-card" />)}</div>}

      {rows.length > 0 && <DatasetCards datasets={rows} />}

      <div className="bm-metrics" role="radiogroup" aria-label="Metric">
        {METRICS.map((m) => (
          <button key={m.id} type="button" role="radio" aria-checked={m.id === metricId} className={`bm-metric ${m.id === metricId ? 'is-active' : ''}`} onClick={() => setMetricId(m.id)}>
            {m.label}
          </button>
        ))}
      </div>

      <InstrumentPanel title={`${metric.label} by dataset`} right="mean · 95% CI · median · range over successful seeds" bodyPadding="flush">
        <div style={{ overflowX: 'auto' }}>
          <table className="bm-table">
            <thead>
              <tr>
                <th scope="col">Dataset</th>
                <th scope="col">Runs OK</th>
                <th scope="col" className="r">Mean</th>
                <th scope="col" className="r">95% CI</th>
                <th scope="col" className="r">Median</th>
                <th scope="col" className="r">Min – max</th>
                <th scope="col" className="r">CV</th>
                <th scope="col">LLM regime (runs)</th>
                <th scope="col">Reproducible</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ k, label, list, st, runs, regimes, repro }) => {
                const ok = runs.n_exit_code_0 ?? list.filter((r) => r.exit_code === 0).length;
                const n = runs.n_runs ?? list.length;
                return (
                  <tr key={k}>
                    <th scope="row">{label}</th>
                    <td className={ok < n ? 'warn' : ''}>{ok}/{n}{ok < n ? ' ⚠' : ''}</td>
                    <td className="r">{st ? metric.fmt(st.mean) : EM}</td>
                    <td className="r">{st ? `${metric.fmt(st.lo)} – ${metric.fmt(st.hi)}` : EM}</td>
                    <td className="r">{st ? metric.fmt(st.median) : EM}</td>
                    <td className="r">{st ? `${metric.fmt(st.min)} – ${metric.fmt(st.max)}` : EM}</td>
                    <td className="r">{st && st.cv != null ? `${st.cv.toFixed(1)}%` : EM}</td>
                    <td>{Object.entries(regimes).map(([rk, rv]) => `${rk.replace(/_/g, ' ')} ${rv.runs}`).join(' · ') || EM}</td>
                    <td>{repro.seeds_compared ? `${repro.identical_profit_to_1_cent}/${repro.seeds_compared} identical` : EM}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </InstrumentPanel>

      <div className="bm-grid">
        {rows.map(({ k, label, list }) => (
          <InstrumentPanel key={k} title={label} right={`${list.length} seeds · own scale`}>
            <StripPlot dsKey={k} label={label} rows={list} metric={metric} onOpen={openRun} />
          </InstrumentPanel>
        ))}
      </div>

      <div className="bm-key" aria-hidden="true">
        <span><i className="bm-key-dot" /> one seed</span>
        <span><i className="bm-key-mean" /> mean</span>
        <span><i className="bm-key-ci" /> 95% CI of the mean</span>
        <span><i className="bm-key-flag" /> failed run (⚠)</span>
      </div>

      {rows.length > 0 && (
        <>
          <div className="bm-two">
            <InstrumentPanel title={`Profit vs coverage · ${focus?.label || ''}`} right="each seed · Pareto front">
              {dsPicker}
              <ProfitCoverage seeds={focus?.list || []} dataset={focus?.label} exportBase={`benchmark_${focus?.k}`} />
            </InstrumentPanel>
            <InstrumentPanel title="Cost structure" right="share of weekly cost · mean of seeds">
              <CostStructure datasets={rows} />
            </InstrumentPanel>
          </div>

          <div className="bm-two">
            <InstrumentPanel title="Where the time goes" right="median seconds per stage">
              <StageTime datasets={rows} />
            </InstrumentPanel>
            <InstrumentPanel title="Fleet deployment" right="vessels sailing of vessels owned, by class">
              <FleetDeployment datasets={rows} />
            </InstrumentPanel>
          </div>

          <div className="bm-two">
            <InstrumentPanel title="Transit time and transshipment" right="TEU-weighted days">
              <TransitQuality datasets={rows} />
            </InstrumentPanel>
            <InstrumentPanel title="Solver and reliability" right="all 30 seeds per dataset">
              <SolverReliability datasets={rows} />
            </InstrumentPanel>
          </div>

          <InstrumentPanel title={`Seed explorer · ${focus?.label || ''}`} right={`${focus?.list.length || 0} seeds · sortable`}>
            {dsPicker}
            {focus && <SeedExplorer label={focus.label} list={focus.list} dsKey={focus.k} onOpen={openRun} />}
          </InstrumentPanel>
        </>
      )}

      <Provenance
        source={source?.source === 'bundle'
          ? `frontend/public${BUNDLE_URL} (snapshot ${source.bundleAt?.slice(0, 10) || EM} of Benchmark/seed-30, scripts/build_benchmark_bundle.py)`
          : 'Benchmark/seed-30/<dataset>/seed_NN.json + FULL_SUMMARY_30_SEEDS.json (via /api/benchmark/*)'}
        sourceStatus={summary ? 'available' : 'no_data'}
        attribution="Frozen benchmark, freeze/FREEZE_2026-10-24_seed30"
        license="Internal"
        recordCount={rows.reduce((a, r) => a + r.list.length, 0)}
      />
    </div>
  );
}
