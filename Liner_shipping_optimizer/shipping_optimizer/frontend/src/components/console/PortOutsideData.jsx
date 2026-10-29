/**
 * PortOutsideData — the plan's ports against outside data (2026-10-28): #3 IMF PortWatch activity, #6 NGA World Port
 * Index depths and facilities, #8 UNCTAD port LSCI. POST /api/ports/activity (backend/port_activity.py) for the run
 * selected in the header. Every tab names its source, its date and how each port was matched.
 */
import React, { useEffect, useMemo, useState } from 'react';
import InstrumentPanel from './InstrumentPanel.jsx';
import { getSelectedRun, subscribeRun } from '../../services/runSelection.js';
import { fmtNum } from '../../utils/formatters.js';

const TABS = [
  ['activity', 'Real activity (PortWatch)'],
  ['depth', 'Depth & facilities (WPI)'],
  ['lsci', 'Connectivity (LSCI)'],
];
const n1 = (v) => (v == null ? '—' : fmtNum(Math.round(v * 10) / 10));
const m1 = (v) => (v == null ? '—' : `${v.toFixed(1)} m`);
const YN = { Y: 'yes', N: 'no', U: 'unknown' };
const HARBOR = { L: 'large', M: 'medium', S: 'small', V: 'very small' };

function SourceChip({ src, label }) {
  if (!src) return null;
  const tone = src.status === 'unavailable' ? 'po-chip po-bad' : src.status === 'stale' ? 'po-chip po-warn' : 'po-chip';
  const when = src.fetched_on || (src.quarters ? `${src.quarters[0]}–${src.quarters[src.quarters.length - 1]}, retrieved ${src.retrieved}` : '');
  return (
    <a className={tone} href={src.url} target="_blank" rel="noreferrer" title={src.error || src.name}>
      {label} · {src.status === 'unavailable' ? 'unavailable' : `${src.matched} ports matched`}{when ? ` · ${when}` : ''}{src.status === 'stale' ? ' · stale copy' : ''}
    </a>
  );
}

function Spark({ values }) {
  const v = values.map((x) => (x == null ? null : Number(x)));
  const ok = v.filter((x) => x != null);
  if (ok.length < 2) return <span className="dz-pct">—</span>;
  const lo = Math.min(...ok); const hi = Math.max(...ok); const W = 88; const H = 22;
  const pts = v.map((x, i) => (x == null ? null : [2 + (i / (v.length - 1)) * (W - 4), H - 3 - ((x - lo) / ((hi - lo) || 1)) * (H - 6)])).filter(Boolean);
  const last = pts[pts.length - 1];
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} aria-hidden="true" className="po-spark">
      <polyline points={pts.map((p) => p.join(',')).join(' ')} fill="none" stroke="var(--viz-1)" strokeWidth="1.5" />
      <circle cx={last[0]} cy={last[1]} r="2.5" fill="var(--viz-1)" />
    </svg>
  );
}

export default function PortOutsideData() {
  const [run, setRun] = useState(getSelectedRun());
  useEffect(() => subscribeRun(setRun), []);
  const [tab, setTab] = useState('activity');
  const [state, setState] = useState({ status: 'loading', data: null, error: null });

  useEffect(() => {
    let live = true;
    setState({ status: 'loading', data: null, error: null });
    (async () => {
      try {
        const r = await fetch('/api/ports/activity', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ run }) });
        const b = await r.json().catch(() => null);
        if (!live) return;
        if (!r.ok || !b?.ports) setState({ status: !b ? 'unavailable' : 'error', data: null, error: b?.detail || `HTTP ${r.status}` });
        else setState({ status: 'ok', data: b, error: null });
      } catch (e) {
        if (live) setState({ status: 'unavailable', data: null, error: String(e?.message || e) });
      }
    })();
    return () => { live = false; };
  }, [run]);

  const rows = useMemo(() => [...(state.data?.ports || [])].sort((a, b) => b.plan.calls_per_week - a.plan.calls_per_week || a.code.localeCompare(b.code)), [state.data]);
  const src = state.data?.sources;
  const over = rows.filter((r) => (r.portwatch?.plan_share_of_container_calls_pct ?? 0) > 100);
  const checks = rows.filter((r) => r.wpi?.check?.length);
  const q = src?.lsci?.quarters || [];

  return (
    <InstrumentPanel title="The plan's ports in the real world" right={<span className="text-[12px] text-slate-400">IMF PortWatch · NGA World Port Index · UNCTAD LSCI</span>}>
      <div className="rl-tabs" role="tablist" aria-label="Outside data">
        {TABS.map(([k, label]) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k} aria-pressed={tab === k} className="cmp-btn" onClick={() => setTab(k)}>{label}</button>
        ))}
      </div>

      {state.status === 'loading' && <p className="text-[12px] text-slate-400 mt-3">Fetching PortWatch port calls and the World Port Index: up to a minute the first time, cached after.</p>}
      {state.status === 'unavailable' && <p className="dz-warn mt-3">Needs the backend (POST /api/ports/activity). {state.error}</p>}
      {state.status === 'error' && <p className="dz-warn mt-3">Failed: {state.error}</p>}

      {state.status === 'ok' && tab === 'activity' && (
        <>
          <div className="po-head">
            <SourceChip src={src.portwatch} label="PortWatch" />
            <p className="viz-note">
              Plan calls per week against the container-ship calls PortWatch observed by AIS (mean of the last 30 days of data, and the same
              30 days a year earlier). Above 100 %, the plan calls more often than all container ships together did{over.length ? ` — ${over.map((r) => r.code).join(', ')}` : ''}.
            </p>
          </div>
          <div className="tf-scroll">
            <table className="viz-table wi-table tf-table po-table">
              <thead><tr><th>Port</th><th className="r">Plan calls / wk</th><th className="r">Plan TEU / wk</th><th className="r">Real container calls / wk</th><th className="r">vs a year earlier</th><th>Plan share of real calls</th><th>PortWatch port</th></tr></thead>
              <tbody>
                {rows.map((r) => {
                  const pw = r.portwatch;
                  const share = pw?.plan_share_of_container_calls_pct;
                  return (
                    <tr key={r.code}>
                      <td>{r.code}<div className="dz-pct">{r.name}</div></td>
                      <td className="r">{r.plan.calls_per_week}</td>
                      <td className="r">{fmtNum(Math.round(r.plan.teu_loaded + r.plan.teu_discharged + r.plan.teu_transhipped))}<div className="dz-pct">{fmtNum(Math.round(r.plan.teu_transhipped))} tranship</div></td>
                      <td className="r">{n1(pw?.container_calls_per_week)}</td>
                      <td className="r">{pw?.yoy_pct == null ? '—' : `${pw.yoy_pct > 0 ? '+' : pw.yoy_pct < 0 ? '−' : '±'}${Math.abs(pw.yoy_pct).toFixed(0)}%`}</td>
                      <td>
                        {share == null ? <span className="dz-pct">—</span> : (
                          <><span className="rl-bar po-bar"><span style={{ width: `${Math.min(100, share)}%` }} className={share > 100 ? 'po-over' : ''} /></span>
                            <span className="rl-val">{share.toFixed(0)}%</span>{share > 100 && <span className="dz-pct tf-over"> · above all real calls</span>}</>
                        )}
                      </td>
                      <td>{pw ? <>{pw.name}<div className="dz-pct">{pw.match} · {pw.km} km · data to {pw.data_through || '—'}</div></> : <span className="dz-pct">not in PortWatch</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {state.status === 'ok' && tab === 'depth' && (
        <>
          <div className="po-head">
            <SourceChip src={src.wpi} label="World Port Index" />
            <p className="viz-note">
              The deepest vessel class the plan sends to each port against the depths the World Port Index lists. WPI depths can be decades old
              and are often shallower than today's dredged berths, so a shallower WPI figure is a <b>check</b>, not an infeasibility: the optimizer
              enforces the LINERLIB port draft{checks.length ? `. To check: ${checks.map((r) => r.code).join(', ')}` : ''}.
            </p>
          </div>
          <div className="tf-scroll">
            <table className="viz-table wi-table tf-table po-table">
              <thead><tr><th>Port</th><th>Deepest class (draft)</th><th className="r">LINERLIB draft</th><th className="r">WPI channel</th><th className="r">WPI cargo pier</th><th className="r">WPI anchorage</th><th>Harbour size</th><th>WPI port</th></tr></thead>
              <tbody>
                {rows.map((r) => {
                  const w = r.wpi;
                  const flag = (k) => (w?.check?.includes(k) ? ' po-check' : '');
                  return (
                    <tr key={r.code}>
                      <td>{r.code}<div className="dz-pct">{r.name}</div></td>
                      <td>{r.plan.deepest_class}<div className="dz-pct">{m1(r.plan.deepest_class_draft_m)}</div></td>
                      <td className="r">{m1(r.plan.linerlib_draft_m)}</td>
                      <td className={`r${flag('channel')}`}>{m1(w?.channel_depth_m)}</td>
                      <td className={`r${flag('cargo pier')}`}>{m1(w?.cargo_pier_depth_m)}</td>
                      <td className="r">{m1(w?.anchorage_depth_m)}</td>
                      <td>{w ? `${HARBOR[w.harbor_size] || w.harbor_size || '—'}${w.container_cranes && w.container_cranes !== 'U' ? ` · container cranes ${YN[w.container_cranes] || w.container_cranes}` : ''}` : '—'}{w?.check?.length ? <div className="dz-pct tf-over">check: WPI {w.check.join(' and ')} shallower than the class draft</div> : null}</td>
                      <td>{w ? <>{w.name}<div className="dz-pct">{w.match} · {w.km} km</div></> : <span className="dz-pct">not in the WPI</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {state.status === 'ok' && tab === 'lsci' && (
        <>
          <div className="po-head">
            <SourceChip src={src.lsci} label="UNCTAD port LSCI" />
            <p className="viz-note">
              How well connected each port is to the global liner network (UNCTAD, quarterly; average Q1 2023 = 100), with its last {q.length} quarters (each line scaled to its own range).
              A plan hub with low connectivity relies on its own services for every connection.
            </p>
          </div>
          <div className="tf-scroll">
            <table className="viz-table wi-table tf-table po-table">
              <thead><tr><th>Port</th><th className="r">Plan calls / wk</th><th className="r">LSCI {q[q.length - 1] || ''}</th><th className="r">vs 4 quarters earlier</th><th>{q[0] || ''} – {q[q.length - 1] || ''}</th></tr></thead>
              <tbody>
                {[...rows].sort((a, b) => (b.lsci?.latest ?? -1) - (a.lsci?.latest ?? -1)).map((r) => {
                  const v = r.lsci?.values || [];
                  const a = v[v.length - 1]; const b = v[v.length - 5];
                  const ch = a != null && b ? ((a - b) / b) * 100 : null;
                  return (
                    <tr key={r.code}>
                      <td>{r.code}<div className="dz-pct">{r.lsci?.label || r.name}</div></td>
                      <td className="r">{r.plan.calls_per_week}</td>
                      <td className="r">{r.lsci?.latest != null ? fmtNum(Math.round(r.lsci.latest)) : '—'}</td>
                      <td className="r">{ch == null ? '—' : `${ch > 0 ? '+' : ch < 0 ? '−' : '±'}${Math.abs(ch).toFixed(1)}%`}</td>
                      <td>{r.lsci ? <Spark values={v} /> : <span className="dz-pct">not in UNCTAD's list</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </InstrumentPanel>
  );
}
