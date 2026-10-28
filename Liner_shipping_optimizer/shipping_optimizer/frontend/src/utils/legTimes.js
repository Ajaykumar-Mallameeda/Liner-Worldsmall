/**
 * legTimes.js — the leg-by-leg schedule of a service's closed rotation.
 *
 * Runs made from 2026-10-24 carry the ledger's own figures on every service (`legs[i]` = {from, to,
 * distance_nm, sail_days, load_teu}, `port_stay_days`): the declared cycle is ceil(Σ sail days + one port
 * stay per call). Older runs do not; for them the sea time is ESTIMATED as the declared cycle minus one
 * 24 h stay per call (the LINERLIB minimum the engine uses), split over the legs in proportion to
 * great-circle distance. `source` says which, and the screen labels it.
 *
 * `coordsOf(port)` → [lon, lat] (portLookup.getPortCoordinates) is only needed for the estimate.
 */
import { geoDistance } from 'd3-geo';

const DEFAULT_STAY_DAYS = 1;   // assumptions.port_stay_hours = 24 in every recorded run

export function legScheduleOf(service, coordsOf = () => null) {
  const ports = (service?.ports || []).filter(Boolean);
  const cycle = Number(service?.cycle_time_days) || null;
  if (Array.isArray(service?.legs) && service.legs.length && service.legs.every((l) => Number.isFinite(Number(l.sail_days)))) {
    const stay = Number(service.port_stay_days ?? DEFAULT_STAY_DAYS);
    const legs = service.legs.map((l) => ({
      from: l.from, to: l.to, sailDays: Number(l.sail_days), distanceNm: Number(l.distance_nm), loadTeu: Number(l.load_teu),
    }));
    const active = legs.reduce((a, l) => a + l.sailDays, 0) + stay * legs.length;
    return { legs, stayDays: stay, cycleDays: cycle || Math.ceil(active), activeDays: active, slackDays: Math.max(0, (cycle || active) - active), source: 'run' };
  }
  if (ports.length < 2 || !cycle) return null;
  const legs = ports.map((from, i) => {
    const to = ports[(i + 1) % ports.length];
    const a = coordsOf(from); const b = coordsOf(to);
    return { from, to, w: a && b ? geoDistance(a, b) : 0, distanceNm: null, loadTeu: null };
  });
  const totalW = legs.reduce((a, l) => a + l.w, 0);
  const sea = Math.max(0.1, cycle - DEFAULT_STAY_DAYS * legs.length);
  // No coordinates at all: an even split (still labelled estimated).
  legs.forEach((l) => { l.sailDays = totalW > 0 ? (l.w / totalW) * sea : sea / legs.length; delete l.w; });
  return { legs, stayDays: DEFAULT_STAY_DAYS, cycleDays: cycle, activeDays: cycle, slackDays: 0, source: 'estimated' };
}

/**
 * Where a vessel is `day` days into the cycle: { leg, frac } while sailing leg `leg` (frac 0..1 along it),
 * or { leg, frac: 1, atPort } while it stays at the port that ends leg `leg`. Timeline per leg: sail, then
 * the port stay at its arrival port; schedule slack (cycle − active days) is spent waiting at the first port.
 */
export function positionAt(schedule, day) {
  const { legs, stayDays, cycleDays, slackDays } = schedule;
  let t = ((day % cycleDays) + cycleDays) % cycleDays;
  if (t < slackDays) return { leg: legs.length - 1, frac: 1, atPort: legs[0].from, waiting: true };
  t -= slackDays;
  for (let i = 0; i < legs.length; i++) {
    const l = legs[i];
    if (t < l.sailDays) return { leg: i, frac: l.sailDays > 0 ? t / l.sailDays : 1 };
    t -= l.sailDays;
    if (t < stayDays) return { leg: i, frac: 1, atPort: l.to };
    t -= stayDays;
  }
  return { leg: legs.length - 1, frac: 1, atPort: legs[legs.length - 1].to };
}
