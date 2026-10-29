/**
 * proformaSchedule.js — a service's weekly pro-forma schedule (2026-10-28, feature #23), the way carriers publish it:
 * every port call with its arrival and departure as a day of the week and a time, for each weekly departure.
 *
 * Timings are the leg schedule the map's vessel replay uses (utils/legTimes.legScheduleOf: the ledger's sail days per
 * leg and one port stay per call; `source` says when they are estimated for an older run). Day 0 = the first
 * departure from the first port of the rotation, Monday 00:00; departure k of the week leaves k × 7 / frequency days
 * later. The round voyage takes vessels × 7 / frequency days: the time beyond the sailing and the port stays
 * (`buffer_days`) is spent at the first port before the next departure, so each port keeps the same weekday.
 */
import { legScheduleOf } from './legTimes.js';

export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

/** Day offset → 'Wed 14:00' (whole hours, rounded). */
export function weekdayTime(day) {
  const h = Math.round(day * 24);
  const w = ((Math.floor(h / 24) % 7) + 7) % 7;
  const hh = ((h % 24) + 24) % 24;
  return `${WEEKDAYS[w]} ${String(hh).padStart(2, '0')}:00`;
}

export function proformaSchedule(service, coordsOf) {
  const sch = legScheduleOf(service, coordsOf);
  if (!sch) return null;
  const f = Math.max(1, Number(service.frequency_per_week) || 1);
  const vessels = Number(service.vessels) || Math.ceil((sch.cycleDays * f) / 7);
  const roundVoyage = (vessels * 7) / f;
  const calls = [];
  let t = 0;
  sch.legs.forEach((l, i) => {
    calls.push({ seq: i + 1, port: l.from, arrive: i === 0 ? null : t - sch.stayDays, depart: t,
      next: { to: l.to, nm: l.distanceNm, sailDays: l.sailDays, loadTeu: l.loadTeu } });
    t += l.sailDays + sch.stayDays;
  });
  // back at the first port: arrival closes the round voyage (the next departure is roundVoyage after day 0)
  const back = t - sch.stayDays;
  const departures = Array.from({ length: f }, (_, k) => (k * 7) / f);
  return {
    id: service.id, vesselClass: service.vessel_class || service.vesselClass || null, frequency: f, vessels,
    stayDays: sch.stayDays, cycleDays: sch.cycleDays, activeDays: sch.activeDays,
    roundVoyageDays: roundVoyage, bufferDays: Math.max(0, roundVoyage - sch.activeDays),
    returnArrival: back, calls, departures, source: sch.source,
  };
}

/** Flat rows (one per call per weekly departure) for CSV: the published-schedule layout. */
export function scheduleRows(pf) {
  const rows = [];
  pf.departures.forEach((d0, k) => {
    pf.calls.forEach((c) => {
      rows.push({
        service: pf.id, vessel_class: pf.vesselClass, weekly_departure: k + 1, call: c.seq, port: c.port,
        arrive_day: c.arrive == null ? null : d0 + c.arrive, arrive: c.arrive == null ? '' : weekdayTime(d0 + c.arrive),
        depart_day: d0 + c.depart, depart: weekdayTime(d0 + c.depart),
        next_port: c.next.to, leg_nm: c.next.nm, leg_sail_days: c.next.sailDays, leg_teu: c.next.loadTeu,
        frequency_per_week: pf.frequency, vessels: pf.vessels, round_voyage_days: pf.roundVoyageDays, timings: pf.source,
      });
    });
    rows.push({
      service: pf.id, vessel_class: pf.vesselClass, weekly_departure: k + 1, call: pf.calls.length + 1, port: pf.calls[0].port,
      arrive_day: d0 + pf.returnArrival, arrive: weekdayTime(d0 + pf.returnArrival), depart_day: d0 + pf.roundVoyageDays,
      depart: `${weekdayTime(d0 + pf.roundVoyageDays)} (next voyage)`, next_port: '', leg_nm: null, leg_sail_days: null, leg_teu: null,
      frequency_per_week: pf.frequency, vessels: pf.vessels, round_voyage_days: pf.roundVoyageDays, timings: pf.source,
    });
  });
  return rows;
}
