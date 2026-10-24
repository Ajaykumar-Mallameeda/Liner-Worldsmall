/**
 * Which optimizer run the dashboard shows.
 *
 *   { kind: 'current' }                                  -> pipeline_output.json of the latest local run
 *   { kind: 'benchmark', dataset: 'worldsmall', seed: 7 } -> a frozen Benchmark/seed-30 run (via /api/runs)
 *
 * The choice is remembered per browser; every view reads the same selection.
 */

const STORAGE_KEY = 'vr.selectedRun';
const CURRENT = Object.freeze({ kind: 'current' });

function readStored() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const run = raw ? JSON.parse(raw) : null;
    if (run && run.kind === 'benchmark' && typeof run.dataset === 'string' && Number.isInteger(run.seed)) return run;
  } catch (_) { /* storage unavailable: fall back to the current run */ }
  return CURRENT;
}

let selected = typeof window !== 'undefined' ? readStored() : CURRENT;
const listeners = new Set();

export function getSelectedRun() {
  return selected;
}

export function setSelectedRun(run) {
  const next = run && run.kind === 'benchmark'
    ? { kind: 'benchmark', dataset: String(run.dataset), seed: Number(run.seed) }
    : CURRENT;
  if (runKey(next) === runKey(selected)) return;
  selected = next;
  try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); } catch (_) { /* not persisted */ }
  listeners.forEach((fn) => { try { fn(next); } catch (_) { /* listener error */ } });
}

export function subscribeRun(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function runKey(run) {
  return run && run.kind === 'benchmark' ? `${run.dataset}/${run.seed}` : 'current';
}

export function runOutputUrl(run) {
  if (run && run.kind === 'benchmark') {
    return `/api/runs/${encodeURIComponent(run.dataset)}/${run.seed}/pipeline_output`;
  }
  return '/pipeline_output.json';
}

/** Human label: "WorldSmall · seed 07" or "WorldSmall · latest run". */
export function runLabel(run, datasetName) {
  const name = datasetName || (run && run.dataset) || 'Run';
  if (run && run.kind === 'benchmark') return `${name} · seed ${String(run.seed).padStart(2, '0')}`;
  return `${name} · latest run`;
}
