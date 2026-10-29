/**
 * basemaps.js — MapLibre styles for the map's basemap choice.
 *
 *   vector       bundled Natural Earth countries (world-atlas 110m), no network needed — the default
 *   bluemarble   NASA Blue Marble Next Generation (GIBS WMTS, keyless)
 *   nightlights  NASA VIIRS Black Marble 2016 night lights (GIBS) — where economic activity is
 *   citylights   NASA VIIRS City Lights 2012 (GIBS)
 *
 * GIBS asks clients to acknowledge it; the attribution string is shown in the map corner. Raster basemaps keep
 * the country outlines on top so coasts stay readable. The globe gets a sky / atmosphere in every style.
 */
import { feature, mesh } from 'topojson-client';
import countries110 from 'world-atlas/countries-110m.json';

const LAND = feature(countries110, countries110.objects.countries);
const BORDERS = mesh(countries110, countries110.objects.countries, (a, b) => a !== b);

const GIBS = 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best';
const GIBS_ATTR = 'Imagery: NASA GIBS (ESDIS)';

export const BASEMAPS = {
  vector: { label: 'Dark vector', group: 'Basemap', attribution: 'Natural Earth', asOf: 'Natural Earth 110m' },
  bluemarble: {
    label: 'Blue Marble', group: 'Basemap', attribution: GIBS_ATTR, asOf: 'NASA Blue Marble NG (2004 composite)',
    tiles: `${GIBS}/BlueMarble_NextGeneration/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg`,
  },
  nightlights: {
    label: 'Night lights 2016', group: 'Basemap', attribution: GIBS_ATTR, asOf: 'VIIRS Black Marble 2016',
    tiles: `${GIBS}/VIIRS_Black_Marble/default/2016-01-01/GoogleMapsCompatible_Level8/{z}/{y}/{x}.png`,
  },
  citylights: {
    label: 'City lights 2012', group: 'Basemap', attribution: GIBS_ATTR, asOf: 'VIIRS City Lights 2012',
    tiles: `${GIBS}/VIIRS_CityLights_2012/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg`,
  },
};

const SKY = {
  'sky-color': '#030a14',
  'horizon-color': '#0f2a47',
  'fog-color': '#071526',
  'sky-horizon-blend': 0.6,
  'horizon-fog-blend': 0.6,
  'fog-ground-blend': 0.4,
  'atmosphere-blend': ['interpolate', ['linear'], ['zoom'], 0, 1, 4, 0.8, 6, 0],
};

/**
 * One MapLibre style holding every basemap: the dark vector land plus one hidden raster layer per GIBS product.
 * Switching basemaps only flips layer visibility (applyBasemap), so the map, the camera and the deck.gl layers
 * interleaved into the style are never torn down; hidden raster layers fetch no tiles.
 */
export function buildStyle(key = 'vector', projection = 'mercator') {
  const sources = {
    land: { type: 'geojson', data: LAND, attribution: 'Natural Earth' },
    borders: { type: 'geojson', data: BORDERS },
  };
  const layers = [{ id: 'sea', type: 'background', paint: { 'background-color': '#030a14' } }];
  layers.push({ id: 'land', type: 'fill', source: 'land', paint: { 'fill-color': '#11253a' } });
  Object.entries(BASEMAPS).forEach(([k, bm]) => {
    if (!bm.tiles) return;
    sources[`img-${k}`] = { type: 'raster', tiles: [bm.tiles], tileSize: 256, maxzoom: 8, attribution: bm.attribution };
    layers.push({ id: `img-${k}`, type: 'raster', source: `img-${k}`, layout: { visibility: 'none' }, paint: { 'raster-opacity': 0.92, 'raster-fade-duration': 0 } });
  });
  layers.push({ id: 'coast', type: 'line', source: 'land', paint: { 'line-color': '#21405e', 'line-width': 0.6 } });
  layers.push({ id: 'borders', type: 'line', source: 'borders', paint: { 'line-color': '#1a3550', 'line-width': 0.4 } });
  const style = { version: 8, projection: { type: projection }, sky: SKY, sources, layers };
  style.layers.forEach((l) => { if (l.id.startsWith('img-')) l.layout.visibility = l.id === `img-${key}` ? 'visible' : 'none'; });
  if (BASEMAPS[key]?.tiles) style.layers.find((l) => l.id === 'land').layout = { visibility: 'none' };
  return style;
}

/** Show basemap `key` on a live map (vector land or one GIBS raster); outlines lighten over imagery. */
export function applyBasemap(map, key) {
  const bm = BASEMAPS[key] || BASEMAPS.vector;
  const raster = Boolean(bm.tiles);
  Object.keys(BASEMAPS).forEach((k) => {
    if (BASEMAPS[k].tiles && map.getLayer(`img-${k}`)) map.setLayoutProperty(`img-${k}`, 'visibility', k === key ? 'visible' : 'none');
  });
  if (map.getLayer('land')) map.setLayoutProperty('land', 'visibility', raster ? 'none' : 'visible');
  if (map.getLayer('coast')) map.setPaintProperty('coast', 'line-color', raster ? 'rgba(148,163,184,0.35)' : '#21405e');
  if (map.getLayer('borders')) map.setPaintProperty('borders', 'line-color', raster ? 'rgba(148,163,184,0.18)' : '#1a3550');
}
