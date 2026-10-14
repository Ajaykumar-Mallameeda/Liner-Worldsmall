/**
 * Metric helpers for dashboard consumers.
 *
 * Rules (output-contract hardening):
 *  - a missing / null / non-numeric backend value is UNAVAILABLE (null), never 0 and never a demo number;
 *  - a genuine 0 stays 0;
 *  - load factor is carried TEU-legs / offered TEU-legs.  `load` (weekly cargo) divided by the
 *    per-departure `capacity` is not a load factor and is never computed here.
 */

export const UNAVAILABLE = '—';

/** Finite number or null.  null, undefined, '', booleans, NaN and Infinity are unavailable; 0 is valid. */
export function numOrNull(v) {
  if (v === null || v === undefined || v === '' || typeof v === 'boolean') return null;
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

/** Format a possibly-missing number: formatter(value) or the unavailable marker. */
export function fmtOr(v, formatter, unavailable = UNAVAILABLE) {
  const n = numOrNull(v);
  return n === null ? unavailable : formatter(n);
}

/** Leg load factor of one service as a fraction (0..), or null when the backend gave no basis for it. */
export function serviceLegLoadFactor(s) {
  if (!s) return null;
  const lf = numOrNull(s.leg_load_factor);
  if (lf !== null) return lf;
  const carried = numOrNull(s.carried_teu_legs);
  const offered = numOrNull(s.offered_teu_legs);
  if (carried !== null && offered !== null && offered > 0) return carried / offered;
  return null;
}

/** Volume-weighted network leg load factor (fraction) over services that carry the TEU-leg fields; null if none. */
export function networkLegLoadFactor(services = []) {
  let carried = 0;
  let offered = 0;
  let any = false;
  for (const s of services || []) {
    const c = numOrNull(s && s.carried_teu_legs);
    const o = numOrNull(s && s.offered_teu_legs);
    if (c !== null && o !== null) {
      carried += c;
      offered += o;
      any = true;
    }
  }
  return any && offered > 0 ? carried / offered : null;
}

/** "54.8%" or the unavailable marker. */
export function fmtPct(fraction, digits = 1) {
  const n = numOrNull(fraction);
  return n === null ? UNAVAILABLE : `${(n * 100).toFixed(digits)}%`;
}

/** Sum of a field over services; null when no service carries a numeric value (zero services -> null). */
export function sumOrNull(items, pick) {
  let total = 0;
  let any = false;
  for (const it of items || []) {
    const n = numOrNull(pick(it));
    if (n !== null) {
      total += n;
      any = true;
    }
  }
  return any ? total : null;
}

/** CSV cell: empty for a missing value so that it cannot be mistaken for a computed zero. */
export function csvNumber(v, digits = 2) {
  const n = numOrNull(v);
  return n === null ? '' : n.toFixed(digits);
}
