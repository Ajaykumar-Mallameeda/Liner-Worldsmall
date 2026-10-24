/**
 * geoRegion.js
 * ------------
 * Geographic trade region of a port and of a service: from the UN/LOCODE country prefix, else the
 * country in the dataset's ports.csv (synthetic ZZ codes), else the port's coordinates.
 *
 * Why: the engine's regional agents are clusters, and their labels do not match geography
 * (the "americas" agent's hubs are Bremerhaven, Rotterdam, Jebel Ali ...). Services carry the
 * agent label in `region`. The dashboard shows geography as the region and keeps the agent
 * label as `agent_region`, so a filter called EUROPE shows services calling European ports.
 */

import { datasetPortCountry, datasetPortCoords } from './portRegistry.js';

// Russian Pacific ports; every other RU port (St Petersburg, Ust-Luga, Novorossiysk ...) is Europe.
const RU_PACIFIC = new Set(['RUVVO', 'RUVYP', 'RUNJK', 'RUKOR', 'RUPKC', 'RUMAG', 'RUVNN']);

export const GEO_REGIONS = ['Americas', 'Europe', 'Middle East', 'Africa', 'Asia Pacific'];

const BY_COUNTRY = {};
const assign = (region, list) => list.split(' ').forEach((c) => { BY_COUNTRY[c] = region; });
assign('Americas', 'AG AI AN AR AW BB BM BO BR BS BZ CA CL CO CR CU CW DM DO EC GD GF GP GT GY HN HT JM KN KY LC MQ MX NI PA PE PR PY SR SV TC TT US UY VC VE VG VI');
assign('Europe', 'AL BA BE BG CY DE DK EE ES FI FO FR GB GE GI GR HR IE IS IT LT LV ME MT NL NO PL PT RO SE SI TR UA');
assign('Middle East', 'AE BH IL IQ IR JO KW LB OM QA SA SY YE');
assign('Africa', 'AO BJ CD CG CI CM CV DJ DZ EG ER GA GH GM GN GQ GW KE KM LR LY MA MG MR MU MZ NA NG RE SC SD SL SN SO ST TG TN TZ ZA');
assign('Asia Pacific', 'AS AU BD BN CK CN FJ FM GU HK ID IN JP KH KI KR LK MH MM MO MP MV MY NC NZ PF PG PH PK PW SB SG TH TL TO TV TW UM VN VU WS');

// Country names as written in the datasets' ports.csv (World-500 / World-1000 use synthetic ZZ codes).
const BY_COUNTRY_NAME = {};
const assignNames = (region, list) => list.split('|').forEach((n) => { BY_COUNTRY_NAME[n.toLowerCase()] = region; });
assignNames('Americas', 'Argentina|Bahamas|Belize|Brazil|Canada|Chile|Colombia|Costa Rica|Ecuador|El Salvador|Honduras|Martinique|Mexico|Nicaragua|Panama|Peru|Puerto Rico|United States|Uruguay|Venezuela');
assignNames('Europe', 'Belgium|Bulgaria|Cyprus|Denmark|Finland|France|Georgia|Germany|Greece|Ireland|Italy|Netherlands|Norway|Poland|Portugal|Slovenia|Spain|Sweden|Turkey|Ukraine|United Kingdom');
assignNames('Middle East', 'Iran|Israel|Jordan|Kuwait|Lebanon|Oman|Saudi Arabia|Syria|U. A. E.|Yemen');
assignNames('Africa', 'Algeria|Angola|Benin|Cameroon|Congo|Congo. Dem. Rep. of|Djibouti|Egypt|Gabon|Ghana|Guinea|Guinea-Bissau|Ivory Coast|Kenya|Liberia|Mauritius|Morocco|Nigeria|Senegal|Sierra Leone|South Africa|Tanzania|Togo|Tunisia');
assignNames('Asia Pacific', 'Australia|Bangladesh|China|Fiji Islands|French Polynesia|Guam|Hong Kong|India|Indonesia|Japan|Korea. South|Malaysia|New Zealand|Pakistan|Philippines|Singapore|Sri Lanka|Taiwan|Thailand|Vietnam');

/** Coarse region from coordinates; the last resort for a port with no known country. */
function regionFromLonLat([lon, lat]) {
  if (lon < -25) return 'Americas';
  if (lon > 60) return 'Asia Pacific';
  if (lat >= 36) return 'Europe';
  if (lon >= 34 && lat >= 12) return 'Middle East';
  return 'Africa';
}

/** Geographic region of one port code, or null when unknown. */
export function portGeoRegion(code) {
  if (!code) return null;
  const c = String(code).toUpperCase().trim();
  const cc = c.slice(0, 2);
  const country = datasetPortCountry(c);
  const coords = datasetPortCoords(c);
  if (cc === 'RU' || (country && country.toLowerCase() === 'russia')) {
    if (RU_PACIFIC.has(c)) return 'Asia Pacific';
    return coords && coords[0] > 100 ? 'Asia Pacific' : 'Europe';
  }
  return BY_COUNTRY[cc]
    || (country && BY_COUNTRY_NAME[country.toLowerCase()])
    || (coords ? regionFromLonLat(coords) : null);
}

/**
 * Geographic region of a service: the region of most of its port calls. A service whose calls
 * are split evenly between regions takes the region of its first port (its origin rotation).
 */
export function serviceGeoRegion(ports) {
  const counts = new Map();
  (ports || []).forEach((p) => {
    const r = portGeoRegion(p);
    if (r) counts.set(r, (counts.get(r) || 0) + 1);
  });
  if (!counts.size) return null;
  const max = Math.max(...counts.values());
  const top = [...counts.entries()].filter(([, n]) => n === max).map(([r]) => r);
  if (top.length === 1) return top[0];
  const first = (ports || []).map(portGeoRegion).find((r) => r && top.includes(r));
  return first || top[0];
}

/** Every geographic region a service calls in. */
export function serviceRegionsTouched(ports) {
  return [...new Set((ports || []).map(portGeoRegion).filter(Boolean))];
}

/**
 * Adds geography to each service in place: `agent_region` keeps the engine's label,
 * `region` becomes the geographic region, `regions_touched` lists every region called.
 * Idempotent (a service that already has agent_region is left alone).
 */
export function withGeoRegions(services) {
  if (!Array.isArray(services)) return services;
  services.forEach((s) => {
    if (!s || typeof s !== 'object' || 'agent_region' in s) return;
    s.agent_region = s.region ?? null;
    const geo = serviceGeoRegion(s.ports);
    if (geo) s.region = geo;
    s.regions_touched = serviceRegionsTouched(s.ports);
  });
  return services;
}

/** Geographic split of a regional agent's hub ports, e.g. "Americas 4/5". */
export function hubGeography(hubPorts) {
  const counts = new Map();
  (hubPorts || []).forEach((p) => {
    const r = portGeoRegion(p);
    if (r) counts.set(r, (counts.get(r) || 0) + 1);
  });
  const total = (hubPorts || []).length;
  return [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([r, n]) => `${r} ${n}/${total}`).join(', ');
}
