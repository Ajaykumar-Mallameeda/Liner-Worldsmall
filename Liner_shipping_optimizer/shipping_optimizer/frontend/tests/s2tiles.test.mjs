import { test } from 'node:test';
import assert from 'node:assert/strict';
import { tileXY, metresPerPixel, scaleBar, tilesFor, s2TileUrl, TILE } from '../src/utils/s2tiles.js';

test('tileXY matches the slippy-map convention', () => {
  // lon 0 / lat 0 is the centre of the world at any zoom.
  assert.deepEqual(tileXY(0, 0, 1), { x: 1, y: 1 });
  // Rotterdam (4.0 E, 51.95 N) at z13 lies in tile x 4187, y 2707 (asinh form of the OSM formula, checked in Python).
  const t = tileXY(4.0, 51.95, 13);
  assert.equal(Math.floor(t.x), 4187);
  assert.equal(Math.floor(t.y), 2707);
});

test('ground resolution and scale bar', () => {
  assert.ok(Math.abs(metresPerPixel(0, 14) - 9.554) < 0.01); // ~10 m: Sentinel-2 native
  const b = scaleBar(0, 13, 90);
  assert.ok([1, 2, 5].includes(b.metres / 10 ** Math.floor(Math.log10(b.metres))));
  assert.ok(b.px <= 90 && b.px > 30);
  assert.equal(b.label, '1 km');
});

test('tilesFor covers the viewport and centres the point', () => {
  const tiles = tilesFor(4.0, 51.95, 13, 320, 200);
  const c = tileXY(4.0, 51.95, 13);
  // the tile holding the point is drawn so that the point lands at the viewport centre
  const home = tiles.find((t) => t.x === Math.floor(c.x) && t.y === Math.floor(c.y));
  assert.ok(home);
  assert.ok(Math.abs(home.left + (c.x % 1) * TILE - 160) < 1e-6);
  assert.ok(Math.abs(home.top + (c.y % 1) * TILE - 100) < 1e-6);
  // every pixel is covered
  const minL = Math.min(...tiles.map((t) => t.left)); const maxR = Math.max(...tiles.map((t) => t.left + TILE));
  const minT = Math.min(...tiles.map((t) => t.top)); const maxB = Math.max(...tiles.map((t) => t.top + TILE));
  assert.ok(minL <= 0 && maxR >= 320 && minT <= 0 && maxB >= 200);
});

test('tiles wrap across the antimeridian', () => {
  const tiles = tilesFor(179.99, 0, 3, 600, 100);
  assert.ok(tiles.every((t) => t.x >= 0 && t.x < 8));
  assert.ok(tiles.some((t) => t.x === 0));
});

test('EOX URL template is row before column', () => {
  assert.equal(s2TileUrl(2025, 13, 6863, 3355),
    'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2025_3857/default/GoogleMapsCompatible/13/3355/6863.jpg');
});
