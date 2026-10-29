/**
 * paletteActions.js — scenario commands typed into the command palette (design D10): "close Suez", "fuel +20%",
 * "demand -10%", "rates +30%", "war risk on", "bunker market", "compare with seed 7". Pure: turns text into
 * intents; the What-if and Run diff tabs apply them (services/scenarioIntent.js).
 *
 * Intents
 *   { kind: 'whatif', patch: { fuelM?, demandM?, closure?: preset key | null, market?: { rateM?, war?, bunker? } } }
 *   { kind: 'diff', seed }   plan A = the run on screen, plan B = the same dataset's benchmark seed
 */

export const PASSAGES = [
  { key: 'suez', label: 'Suez Canal', words: ['suez', 'suez canal'] },
  { key: 'red_sea', label: 'Red Sea (Bab al-Mandab)', words: ['red sea', 'bab al-mandab', 'bab el-mandeb', 'mandab'] },
  { key: 'panama', label: 'Panama Canal', words: ['panama', 'panama canal'] },
  { key: 'hormuz', label: 'Strait of Hormuz', words: ['hormuz', 'strait of hormuz'] },
  { key: 'malacca', label: 'Strait of Malacca', words: ['malacca', 'strait of malacca'] },
  { key: 'gibraltar', label: 'Strait of Gibraltar', words: ['gibraltar', 'strait of gibraltar'] },
  { key: 'bosporus', label: 'Bosporus', words: ['bosporus', 'bosphorus', 'turkish straits'] },
];

// Slider ranges of the What-if (views/console/WhatIf.jsx, MarketPanels.jsx): a typed value is clamped to them.
export const RANGES = { fuelM: [0.5, 3], demandM: [0.5, 2], rateM: [0.3, 3] };

const clamp = (v, [lo, hi]) => Math.min(hi, Math.max(lo, v));
const round2 = (v) => Math.round(v * 100) / 100;
const pctText = (m) => `${m >= 1 ? '+' : '−'}${Math.round(Math.abs(m - 1) * 100)}%`;

/** "+20%", "-10 %", "−30%", "20%", "x1.2", "×0.8" → multiplier, or null. */
export function parseChange(text) {
  const t = text.replace(/−/g, '-').trim();
  let m = t.match(/^(?:by\s+)?([+-]?)\s*(\d+(?:\.\d+)?)\s*%$/);
  if (m) return 1 + (m[1] === '-' ? -1 : 1) * Number(m[2]) / 100;
  m = t.match(/^(?:[x×*]|times\s+)\s*(\d+(?:\.\d+)?)$/i);
  if (m) return Number(m[1]);
  return null;
}

const LEVERS = [
  { key: 'fuelM', re: /^(?:fuel|bunker(?:\s+price)?|fuel\s+price)\s+(.+)$/, label: 'Bunker fuel price' },
  { key: 'demandM', re: /^(?:demand|volume|cargo)\s+(.+)$/, label: 'Demand on every lane' },
  { key: 'rateM', re: /^(?:freight(?:\s+rates?)?|rates?|revenue)\s+(.+)$/, label: 'Freight rate level' },
];

/** Intents for the typed text (several when it is ambiguous), each with a label for the palette. */
export function parseActions(query) {
  const q = String(query || '').toLowerCase().replace(/\s+/g, ' ').trim();
  if (!q) return [];
  const out = [];

  const close = q.match(/^(close|block|shut|reopen|open)\s+(?:the\s+)?(.+)$/);
  if (close) {
    const reopen = close[1] === 'reopen' || close[1] === 'open';
    const hits = PASSAGES.filter((p) => p.words.some((w) => w.startsWith(close[2]) || close[2].startsWith(w)));
    if (reopen && hits.length) out.push({ kind: 'whatif', patch: { closure: null }, label: 'Reopen every passage (What-if)', hint: 'clears the closure' });
    if (!reopen) hits.forEach((p) => out.push({ kind: 'whatif', patch: { closure: p.key }, label: `Close the ${p.label} (What-if)`, hint: 'ships take their detour' }));
  }

  LEVERS.forEach((lv) => {
    const m = q.match(lv.re);
    const mult = m ? parseChange(m[1]) : null;
    if (mult == null || !Number.isFinite(mult) || mult <= 0) return;
    const v = round2(clamp(mult, RANGES[lv.key]));
    const patch = lv.key === 'rateM' ? { market: { rateM: v, rateMode: 'uniform' } } : { [lv.key]: v };
    out.push({ kind: 'whatif', patch, label: `${lv.label} ${pctText(v)} (What-if)`, hint: v !== round2(mult) ? `limited to the slider range ×${v}` : `× ${v.toFixed(2)}` });
  });

  if (/^war[ -]?risk(?:\s+(on|off))?$/.test(q)) {
    const off = q.endsWith('off');
    out.push({ kind: 'whatif', patch: { market: { war: !off } }, label: `${off ? 'Remove' : 'Add'} war-risk premiums (What-if)`, hint: 'JWC listed areas' });
  }
  if (/^(?:bunker|fuel)\s+(?:by\s+port|market|prices?\s+by\s+port)$/.test(q)) {
    out.push({ kind: 'whatif', patch: { market: { bunker: 'market' } }, label: 'Bunker prices by port (What-if)', hint: 'Ship & Bunker' });
  }
  if (/^(?:wci|freight\s+index|wci\s+lanes)$/.test(q)) {
    out.push({ kind: 'whatif', patch: { market: { rateMode: 'wci_lanes' } }, label: 'Freight rates from the Drewry WCI lanes (What-if)', hint: 'spot ÷ dataset' });
  }

  const seed = q.match(/^(?:compare|diff)(?:\s+(?:with|to|against))?\s+seed\s*(\d{1,3})$/);
  if (seed) out.push({ kind: 'diff', seed: Number(seed[1]), label: `Compare the run on screen with seed ${Number(seed[1])} (Run diff)`, hint: 'A = on screen · B = seed' });

  return out;
}

/** Example commands shown when the palette opens, so the feature can be found. */
export const EXAMPLES = [
  { kind: 'whatif', patch: { closure: 'suez' }, label: 'Close the Suez Canal (What-if)', hint: 'type “close …”' },
  { kind: 'whatif', patch: { fuelM: 1.2 }, label: 'Bunker fuel price +20% (What-if)', hint: 'type “fuel +20%”' },
  { kind: 'diff', seed: 7, label: 'Compare the run on screen with seed 7 (Run diff)', hint: 'type “compare with seed N”' },
];
