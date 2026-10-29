// Map platform of the 2026-10-28 campaign (node --test): sea-lane geometry helpers, camera bounds, the
// shared timeline clock and the map preferences store.
import test from 'node:test';
import assert from 'node:assert/strict';
import { unwrapPath, greatCircle, greatCircleRoute, densify, pathMeasure, pointAlong, boundsOf, passageName } from '../src/services/seaRoutes.js';
import { clockLabel, getTimeline, seekTimeline, setTimelineSpeed, resetTimeline } from '../src/services/timelineStore.js';
import { getMapPrefs, setMapPrefs, toggleMapLayer, LAYER_DEFS } from '../src/services/mapPrefsStore.js';
import { legScheduleOf, positionAt } from '../src/utils/legTimes.js';

test('unwrapPath: no longitude jump across the antimeridian', () => {
  const p = unwrapPath([[170, 10], [179, 12], [-179, 13], [-170, 15]]);
  assert.deepEqual(p.map((c) => c[0]), [170, 179, 181, 190]);
  for (let i = 1; i < p.length; i++) assert.ok(Math.abs(p[i][0] - p[i - 1][0]) < 180);
});

test('greatCircle: endpoints kept, trans-Pacific path unwrapped; fallback route is labelled great-circle', () => {
  const tokyo = [139.7, 35.6]; const la = [-118.3, 33.7];
  const g = greatCircle(tokyo, la, 20);
  assert.equal(g.length, 21);
  assert.deepEqual(g[0].map((v) => +v.toFixed(3)), tokyo);
  assert.ok(Math.abs(g[20][0] - (la[0] + 360)) < 1e-6, 'east end shifted by +360');
  const r = greatCircleRoute(tokyo, la);
  assert.equal(r.source, 'great-circle');
  assert.equal(r.model_nm, null);
  assert.ok(r.nm > 4500 && r.nm < 4900, `Tokyo-LA great circle ≈ 4,700 nm, got ${r.nm}`);
});

test('densify: no segment longer than the limit, original vertices kept in order', () => {
  const src = [[0, 0], [10, 0], [10, 7]];
  const d = densify(src, 2);
  for (let i = 1; i < d.length; i++) {
    assert.ok(Math.max(Math.abs(d[i][0] - d[i - 1][0]), Math.abs(d[i][1] - d[i - 1][1])) <= 2 + 1e-9);
  }
  src.forEach((v) => assert.ok(d.some((c) => c[0] === v[0] && c[1] === v[1])));
  assert.deepEqual(d[0], src[0]);
  assert.deepEqual(d[d.length - 1], src[2]);
  assert.deepEqual(densify([[1, 1]]), [[1, 1]]);
});

test('pointAlong: ends, midpoint and heading along a measured path', () => {
  const path = [[0, 0], [10, 0], [10, 10]];
  const cum = pathMeasure(path);
  assert.equal(cum.length, 3);
  assert.deepEqual(pointAlong(path, cum, 0).p, [0, 0]);
  assert.deepEqual(pointAlong(path, cum, 1).p, [10, 10]);
  const east = pointAlong(path, cum, 0.25);
  assert.ok(Math.abs(east.heading) < 1e-9, 'first half heads east (0°)');
  const north = pointAlong(path, cum, 0.9);
  assert.ok(Math.abs(north.heading - 90) < 1e-9, 'second half heads north (90°)');
  assert.deepEqual(pointAlong(path, cum, 2).p, [10, 10], 'clamped past the end');
});

test('vessel position: leg schedule + sea-lane path puts the vessel at the right fraction of its leg', () => {
  const svc = { ports: ['A', 'B'], cycle_time_days: 10, legs: [
    { from: 'A', to: 'B', sail_days: 4, distance_nm: 1000, load_teu: 1 },
    { from: 'B', to: 'A', sail_days: 4, distance_nm: 1000, load_teu: 1 },
  ], port_stay_days: 1 };
  const sch = legScheduleOf(svc);
  const pos = positionAt(sch, 2);   // no slack: halfway along leg A→B
  assert.equal(pos.leg, 0);
  assert.equal(pos.frac, 0.5);
  const lane = [[0, 0], [4, 0], [4, 4]];   // a dog-leg sea lane, not a straight line
  const { p } = pointAlong(lane, pathMeasure(lane), pos.frac);
  assert.deepEqual(p, [4, 0], 'half of the lane length is the corner');
});

test('boundsOf: tight box, antimeridian-aware, world (null) when the points circle the globe', () => {
  assert.equal(boundsOf([]), null);
  assert.deepEqual(boundsOf([[0, 50], [10, 40]]), [[0, 40], [10, 50]]);
  const pac = boundsOf([[140, 35], [-120, 34]]);   // Tokyo, LA: across the Pacific (100°), not across Europe (260°)
  assert.deepEqual(pac, [[140, 34], [240, 35]]);
  assert.equal(boundsOf([[0, 0], [90, 0], [180, 0], [-90, 0]]), null, 'a 270° spread is the world view');
  assert.deepEqual(boundsOf([[0, 0], [120, 0], [-120, 0]]), [[-120, 0], [120, 0]], '240° still fits');
  const one = boundsOf([[5, 5]]);
  assert.deepEqual(one, [[1, 1], [9, 9]], 'single port padded');
});

test('passageName: searoute ids map to names; unknown ids pass through', () => {
  assert.equal(passageName('suez'), 'Suez Canal');
  assert.equal(passageName('babalmandab'), 'Bab-el-Mandeb');
  assert.equal(passageName('south_africa'), 'Cape of Good Hope');
  assert.equal(passageName('xyz'), 'xyz');
});

test('timeline clock: label, seek clamp and speed', () => {
  resetTimeline();
  assert.equal(clockLabel(0), 'Week 1 · Mon 00:00');
  assert.equal(clockLabel(2.5), 'Week 1 · Wed 12:00');
  assert.equal(clockLabel(9.25), 'Week 2 · Wed 06:00');
  seekTimeline(-3);
  assert.equal(getTimeline().day, 0);
  seekTimeline(4.5);
  assert.equal(getTimeline().day, 4.5);
  setTimelineSpeed(7);
  assert.equal(getTimeline().speed, 7);
  resetTimeline();
  assert.deepEqual(getTimeline(), { day: 0, playing: false, speed: 1 });
});

test('map prefs: defaults, toggles, and no storage needed', () => {
  const p = getMapPrefs();
  assert.equal(p.engine, 'gl');
  assert.equal(p.projection, 'mercator');
  assert.equal(p.basemap, 'vector');
  // every layer on by default, except opt-in ones (the ECA zones)
  LAYER_DEFS.forEach((d) => assert.equal(p.layers[d.id], d.default !== false, d.id));
  assert.equal(p.layers.eca, false);
  toggleMapLayer('flows');
  assert.equal(getMapPrefs().layers.flows, false);
  assert.equal(getMapPrefs().layers.routes, true, 'other layers untouched');
  setMapPrefs({ projection: 'globe' });
  assert.equal(getMapPrefs().projection, 'globe');
  assert.equal(getMapPrefs().layers.flows, false, 'layer state kept across other changes');
});
