/**
 * RunPicker
 * ---------
 * Header control that chooses which optimizer run every view shows:
 * the latest local run, a run kept in runs_extra/, or any frozen benchmark seed (/api/runs).
 * Without the backend only the latest run is offered.
 */

import { useEffect, useState } from 'react';
import { apiClient } from '../../services/apiClient.js';
import { getSelectedRun, setSelectedRun, subscribeRun, runKey } from '../../services/runSelection.js';
import { fmtUsd } from '../../utils/formatters.js';

export default function RunPicker() {
  const [catalog, setCatalog] = useState(null);
  const [selected, setSelected] = useState(getSelectedRun());

  useEffect(() => subscribeRun(setSelected), []);

  useEffect(() => {
    let cancelled = false;
    apiClient.getRuns()
      .then((c) => { if (!cancelled) setCatalog(c); })
      .catch(() => { if (!cancelled) setCatalog({ current: null, benchmark: [] }); });
    return () => { cancelled = true; };
  }, []);

  const onChange = (e) => {
    const v = e.target.value;
    if (v === 'current') { setSelectedRun({ kind: 'current' }); return; }
    if (v.startsWith('extra:')) { setSelectedRun({ kind: 'extra', id: v.slice(6) }); return; }
    const [dataset, seed] = v.split('/');
    setSelectedRun({ kind: 'benchmark', dataset, seed: Number(seed) });
  };

  const groups = (catalog?.benchmark || []).filter((g) => g.seeds.some((s) => s.has_pipeline_output));
  const extra = catalog?.extra || [];
  const value = runKey(selected);
  const known = value === 'current' || extra.some((r) => `extra:${r.id}` === value)
    || groups.some((g) => g.seeds.some((s) => `${g.key}/${s.seed}` === value));

  return (
    <label className="cx-run-picker">
      <span className="k">Run</span>
      <select id="run-picker" value={known ? value : 'current'} onChange={onChange} aria-label="Optimizer run shown in the dashboard">
        <option value="current">Latest local run</option>
        {extra.length > 0 && (
          <optgroup label="Other runs">
            {extra.map((r) => <option key={r.id} value={`extra:${r.id}`} title={r.note || ''}>{r.label}</option>)}
          </optgroup>
        )}
        {groups.map((g) => (
          <optgroup key={g.key} label={`${g.dataset} · 30-seed benchmark`}>
            {g.seeds.filter((s) => s.has_pipeline_output).map((s) => (
              <option key={s.seed} value={`${g.key}/${s.seed}`}>
                {`${g.dataset} · seed ${String(s.seed).padStart(2, '0')}`}
                {s.weekly_profit_usd != null ? ` · ${fmtUsd(s.weekly_profit_usd)}/wk` : ''}
                {s.exit_code ? ' · exit ' + s.exit_code : ''}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </label>
  );
}
