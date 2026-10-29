/**
 * s2tiles.js
 * ----------
 * Tile maths for the Sentinel-2 port view (components/console/PortSatellite.jsx): EOX "Sentinel-2 cloudless"
 * WMTS URLs, Web-Mercator tile positions, ground resolution and the tiles covering a viewport.
 */

export const S2_YEARS = [2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018];
export const TILE = 256;
export const MIN_Z = 10;
export const MAX_Z = 16;
export const NATIVE_Z = 14;

export function s2TileUrl(year, z, x, y) {
  return `https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-${year}_3857/default/GoogleMapsCompatible/${z}/${y}/${x}.jpg`;
}

/** Web-Mercator position of lon/lat in tile units at zoom z. */
export function tileXY(lon, lat, z) {
  const n = 2 ** z;
  const clamped = Math.max(-85.0511, Math.min(85.0511, lat));
  const rad = (clamped * Math.PI) / 180;
  const x = ((lon + 180) / 360) * n;
  const y = ((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * n;
  return { x, y };
}

/** Ground metres per CSS pixel at zoom z and this latitude (256-px tiles). */
export function metresPerPixel(lat, z) {
  return (156543.03392 * Math.cos((lat * Math.PI) / 180)) / 2 ** z;
}

/** A round scale-bar length (1, 2 or 5 x 10^k metres) that fits in maxPx pixels. */
export function scaleBar(lat, z, maxPx = 90) {
  const mpp = metresPerPixel(lat, z);
  const raw = mpp * maxPx;
  const p = 10 ** Math.floor(Math.log10(raw));
  const metres = [5, 2, 1].map((m) => m * p).find((m) => m <= raw) || p;
  return { metres, px: metres / mpp, label: metres >= 1000 ? `${metres / 1000} km` : `${metres} m` };
}

/** Tiles covering a width x height viewport centred on lon/lat, with their pixel offsets. */
export function tilesFor(lon, lat, z, width, height) {
  const n = 2 ** z;
  const c = tileXY(lon, lat, z);
  const left = c.x * TILE - width / 2;
  const top = c.y * TILE - height / 2;
  const out = [];
  for (let ty = Math.floor(top / TILE); ty <= Math.floor((top + height - 1) / TILE); ty += 1) {
    if (ty < 0 || ty >= n) continue;
    for (let tx = Math.floor(left / TILE); tx <= Math.floor((left + width - 1) / TILE); tx += 1) {
      const wrapped = ((tx % n) + n) % n;
      out.push({ key: `${z}/${tx}/${ty}`, x: wrapped, y: ty, left: tx * TILE - left, top: ty * TILE - top });
    }
  }
  return out;
}

/** Whole zoom at which `size` pixels cover about `metres` of ground (port thumbnails, design D8), within MIN_Z..NATIVE_Z. */
export function thumbZoom(lat, size, metres = 4000) {
  const z = Math.round(Math.log2((156543.03392 * Math.cos((lat * Math.PI) / 180) * size) / metres));
  return Math.max(MIN_Z, Math.min(NATIVE_Z, z));
}
