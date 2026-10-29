// Weekly pro-forma schedules (#23): call times from the ledger's leg schedule, weekday labels, CSV rows.
import test from 'node:test';
import assert from 'node:assert/strict';
import { proformaSchedule, scheduleRows, weekdayTime } from '../src/utils/proformaSchedule.js';

const svc = {
  id: 's1', vessel_class: 'Panamax_2400', frequency_per_week: 1, vessels: 3, cycle_time_days: 20, port_stay_days: 1,
  ports: ['A', 'B', 'C'],
  legs: [{ from: 'A', to: 'B', sail_days: 2.5, distance_nm: 1000, load_teu: 900 },
    { from: 'B', to: 'C', sail_days: 4, distance_nm: 1600, load_teu: 700 },
    { from: 'C', to: 'A', sail_days: 6, distance_nm: 2400, load_teu: 500 }],
};

test('weekdayTime: day offsets to weekday and hour, wrapping weeks', () => {
  assert.equal(weekdayTime(0), 'Mon 00:00');
  assert.equal(weekdayTime(2.5), 'Wed 12:00');
  assert.equal(weekdayTime(7 + 1.25), 'Tue 06:00');
});

test('proformaSchedule: arrivals and departures follow sail days + one stay per call', () => {
  const pf = proformaSchedule(svc);
  assert.equal(pf.source, 'run');
  assert.deepEqual(pf.calls.map((c) => [c.port, c.arrive, c.depart]), [['A', null, 0], ['B', 2.5, 3.5], ['C', 7.5, 8.5]]);
  assert.equal(pf.returnArrival, 14.5);
  assert.equal(pf.roundVoyageDays, 21);                 // 3 vessels x 7 / 1
  assert.equal(pf.activeDays, 15.5);
  assert.equal(pf.bufferDays, 5.5);
  assert.ok(pf.returnArrival + pf.stayDays <= pf.roundVoyageDays);
});

test('two sailings a week: the second departure 3.5 days later, same calls', () => {
  const pf = proformaSchedule({ ...svc, frequency_per_week: 2, vessels: 5 });
  assert.deepEqual(pf.departures, [0, 3.5]);
  assert.equal(pf.roundVoyageDays, 17.5);
  const rows = scheduleRows(pf);
  assert.equal(rows.length, 2 * (3 + 1));
  const b2 = rows.find((r) => r.weekly_departure === 2 && r.port === 'B');
  assert.equal(b2.arrive, 'Sun 00:00');               // 3.5 + 2.5 = day 6 = Sunday
  assert.equal(b2.depart_day, 7);
});

test('older run without legs: timings estimated from the cycle', () => {
  const pf = proformaSchedule({ id: 'old', ports: ['A', 'B'], cycle_time_days: 6, frequency_per_week: 1, vessels: 1 });
  assert.equal(pf.source, 'estimated');
  assert.equal(pf.calls.length, 2);
  assert.ok(Math.abs(pf.activeDays - 6) < 1e-9);
});
