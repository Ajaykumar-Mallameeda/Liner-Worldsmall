/**
 * portRegistry.js
 * ---------------
 * Port facts read from the shown dataset's own ports.csv: name, coordinates and country.
 * The static tables in portLookup.js / port_coordinates.json only cover the WorldSmall ports;
 * Baltic and WAF add ports, and World-500 / World-1000 use synthetic codes (ZZ000 ...) that no
 * static table knows. Every dataset's ports.csv carries Longitude / Latitude / Country.
 *
 * No JSON imports here, so node tests can load modules that depend on this one.
 */

const NAMES = {};
const COORDS = {};     // code -> [lon, lat]
const COUNTRY = {};    // code -> country name as written in ports.csv
const DATASET_PORTS = {};   // rawDir -> [code, ...]
const pending = new Map();  // rawDir -> Promise
let activeDir = null;
let version = 0;

const norm = (code) => String(code).toUpperCase().trim();

/** Parse a tab-separated ports.csv and register every port in it. Returns the codes in file order. */
export function registerPortsCsv(rawDir, text) {
  const lines = String(text || '').trim().split(/\r?\n/);
  if (lines.length < 2) return [];
  const head = lines[0].split('\t').map((x) => x.trim());
  const col = (n) => head.indexOf(n);
  const ci = col('UNLocode'), ni = col('name'), lo = col('Longitude'), la = col('Latitude'), co = col('Country');
  if (ci < 0) return [];
  const codes = [];
  lines.slice(1).forEach((line) => {
    const p = line.split('\t');
    if (!p[ci]) return;
    const code = norm(p[ci]);
    codes.push(code);
    if (ni >= 0 && p[ni]) NAMES[code] = p[ni].trim();
    if (co >= 0 && p[co]) COUNTRY[code] = p[co].trim();
    const lon = lo >= 0 ? Number(p[lo]) : NaN;
    const lat = la >= 0 ? Number(p[la]) : NaN;
    if (Number.isFinite(lon) && Number.isFinite(lat)) COORDS[code] = [lon, lat];
  });
  DATASET_PORTS[rawDir] = codes;
  version += 1;
  return codes;
}

/** Fetch /data/raw/<dir>/ports.csv once per dataset; resolves when its ports are registered. */
export function ensurePortData(rawDir) {
  if (!rawDir) return Promise.resolve();
  activeDir = rawDir;
  if (DATASET_PORTS[rawDir]) return Promise.resolve();
  if (pending.has(rawDir)) return pending.get(rawDir);
  const p = fetch(`/data/raw/${rawDir}/ports.csv`)
    .then((res) => (res.ok ? res.text() : ''))
    .then((text) => { registerPortsCsv(rawDir, text); })
    .catch(() => { /* names and coordinates fall back to the static tables */ })
    .finally(() => pending.delete(rawDir));
  pending.set(rawDir, p);
  return p;
}

export const datasetPortName = (code) => (code ? NAMES[norm(code)] || null : null);
export const datasetPortCoords = (code) => (code ? COORDS[norm(code)] || null : null);
export const datasetPortCountry = (code) => (code ? COUNTRY[norm(code)] || null : null);

/** Port codes of the dataset most recently requested with ensurePortData (the one on screen). */
export function activeDatasetPorts() {
  return (activeDir && DATASET_PORTS[activeDir]) || [];
}

/** Changes whenever new ports are registered; use as a memo dependency. */
export function portRegistryVersion() {
  return version;
}
