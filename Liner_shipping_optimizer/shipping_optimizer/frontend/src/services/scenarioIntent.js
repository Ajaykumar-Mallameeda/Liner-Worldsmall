/**
 * scenarioIntent — hands a command-palette scenario (utils/paletteActions.js, design D10) to the tab that applies
 * it. The palette stores the intent and navigates; the What-if or Run diff tab takes it when it mounts, or at once
 * when it is already open. One pending intent per kind; taking it clears it.
 */

import { useEffect, useState } from 'react';

const pending = { whatif: null, diff: null };
const listeners = new Set();

export function requestScenario(intent) {
  if (!intent || !(intent.kind in pending)) return;
  pending[intent.kind] = { ...intent, at: Date.now() };
  listeners.forEach((fn) => fn(intent.kind));
}

export function takeScenario(kind) {
  const it = pending[kind];
  pending[kind] = null;
  return it;
}

/** Calls apply(intent) for each intent of this kind: the one waiting at mount, then every new one. */
export function useScenarioIntent(kind, apply) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const on = (k) => { if (k === kind) setTick((t) => t + 1); };
    listeners.add(on);
    return () => listeners.delete(on);
  }, [kind]);
  useEffect(() => {
    const it = takeScenario(kind);
    if (it) apply(it);
  }, [tick]); // eslint-disable-line react-hooks/exhaustive-deps
}
