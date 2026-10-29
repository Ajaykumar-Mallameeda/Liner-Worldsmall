/**
 * GlMap — the WebGL map: MapLibre GL (flat or globe with atmosphere) with the plan drawn by deck.gl layers
 * interleaved into the map. Same props as the classic SVG map (SvgWorldMap.jsx), so every page uses either.
 *
 * - Legs follow real sea lanes (services/seaRoutes.js → /api/searoutes: searoute's Eurostat maritime network).
 *   The tooltip compares the sea-lane length with the LINERLIB distance the optimizer used and lists the
 *   straits / canals passed. Without the backend the legs are great-circle paths and the screen says so.
 * - Width = TEU on the leg (square root, against the busiest leg on screen); colours as in the SVG map.
 * - Vessels: every vessel of every service on screen sits where its leg schedule (utils/legTimes.js) puts it
 *   at the shared timeline clock (TimelineBar), moved along the sea-lane geometry of its current leg.
 * - Cargo flow particles run along each leg in sailing direction (full motion only).
 * - Route draw-on once per run and surface, hover link dimming, glides of 300 ms — all gated by motion.
 *
 * Frame-by-frame updates (clock, particles, draw-on) go straight to the deck overlay; React re-renders only
 * when the data on screen changes.
 */
import React, { useState, useCallback, useMemo, useEffect, useLayoutEffect, useRef } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
// MapLibre finds its worker next to its own module, which Vite's dep bundle and build do not keep; bundle it here.
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import { MapLibreOverlay } from '@deck.gl/maplibre';
import { PathLayer, ScatterplotLayer, TextLayer, IconLayer, GeoJsonLayer } from '@deck.gl/layers';
import { TripsLayer } from '@deck.gl/geo-layers';
import { PathStyleExtension } from '@deck.gl/extensions';
import { getPortName, getPortCoordinates } from '../../utils/portLookup.js';
import { activeDatasetPorts, portRegistryVersion } from '../../utils/portRegistry.js';
import { fmtNum, fmtUsd } from '../../utils/formatters.js';
import { portGeoRegion } from '../../utils/geoRegion.js';
import { useAgentFocus, matchesAgent, useHoverTarget, matchesHover } from '../../services/focusStore.js';
import { useMotionLevel, motionLevel } from '../../services/prefsStore.js';
import { legScheduleOf, positionAt } from '../../utils/legTimes.js';
import { useSeaRoutes, greatCircle, pathMeasure, pointAlong, passageName, densify, boundsOf } from '../../services/seaRoutes.js';
import { getTimeline, subscribeTimeline, playTimeline } from '../../services/timelineStore.js';
import { getSelectedRun, subscribeRun } from '../../services/runSelection.js';
import { useTransshipment } from '../../services/transshipmentData.js';
import { useChokepointExposure, usePortWatch, CHOKEPOINT_AT, yoyPct } from '../../services/chokepoints.js';
import { useEcaZones } from '../../services/ecaZones.js';
import { useWarRiskAreas, usePiracy } from '../../services/warRisk.js';
import { useAisLive, aisTone, AIS_CATEGORIES } from '../../services/aisLive.js';
import { useMapSeaState, seaRiskTone, SEA_RISKS, CURRENT_TONE } from '../../services/seaState.js';
import { useMapPrefs, getMapPrefs, setMapPrefs, toggleMapLayer, LAYER_DEFS } from '../../services/mapPrefsStore.js';
import { BASEMAPS, buildStyle, applyBasemap } from './basemaps.js';
import { getRegionColor } from './SvgWorldMap.jsx';
import LayerPanel from './LayerPanel.jsx';
import TimelineBar from './TimelineBar.jsx';
import { joinSync } from '../../services/mapSync.js';
import { registerSnapshot } from '../../services/mapSnapshot.js';

maplibregl.setWorkerUrl(maplibreWorkerUrl);

const VIZ_1 = '#3987e5';
const VIZ_2 = '#d95926';
const HUB_TONE = '#a78bfa';   // transshipment hubs: apart from the leg blue, unserved orange and chokepoint amber
const VIZ_MUTED = '#5b6b7a';
const UNSERVED_LANES_SHOWN = 12;
const DIFF_TONE = { added: VIZ_1, removed: VIZ_2, kept: VIZ_MUTED };
const DISRUPT_TONE = { rerouted: VIZ_2, suspended: VIZ_MUTED };
const ECA_TONE = '#2dd4bf';
const WAR_TONE = '#f87171';
const PIRACY_TONE = '#fda4af';
const ITIN_TONES = [VIZ_1, VIZ_2, '#c9a227'];          // first, second, third service ridden
const ITIN_PORT_TONE = { origin: '#10b981', transfer: '#f5b301', destination: '#00d4ff', call: '#94a3b8' };
const WORLD_BOUNDS = [[-165, -50], [190, 68]];
const MAX_FIT_ZOOM = 6;
const PORT_ZOOM = 4;
const GLIDE_MS = 300;
const MAX_VESSELS_PER_SERVICE = 12;

// Draw-on: each leg draws in 200 ms; starts spread over 300 ms by rank (busiest first). Once per run + surface.
const drawnKeys = new Set();
const DRAW_SPREAD_MS = 300;
const DRAW_LEG_MS = 200;
const DRAW_TOTAL_MS = DRAW_SPREAD_MS + DRAW_LEG_MS + 100;
// Flow particles: every leg runs one particle pair per period, whatever its length.
const FLOW_PERIOD = 1250;
const FLOW_TRAIL = 140;
const FLOW_MS_PER_UNIT = 3.2;

const legWidth = (load, maxLoad) => (maxLoad > 0 ? 0.8 + 3.4 * Math.sqrt(Math.max(load, 0) / maxLoad) : 1.2);
const rgb = (hex, a = 1) => {
  const h = String(hex).replace('#', '');
  const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255, Math.round(a * 255)];
};
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const nm = (v) => (v == null ? '—' : `${fmtNum(Math.round(v))} nm`);
// Globe and text / icon layers: draw both faces (the globe's winding would cull them otherwise).
const LAYER_BASE = { parameters: { cullMode: 'none' } };
const DIAMOND_ICON = {
  url: `data:image/svg+xml;charset=utf-8,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><path d="M16 2 30 16 16 30 2 16z" fill="#fff" fill-opacity="0.35" stroke="#fff" stroke-width="3"/></svg>')}`,
  width: 32, height: 32, anchorX: 16, anchorY: 16, mask: true,
};
const VESSEL_ICON = {
  url: `data:image/svg+xml;charset=utf-8,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><path d="M30 16 6 5l5 11-5 11z" fill="#fff"/></svg>')}`,
  width: 32, height: 32, anchorX: 16, anchorY: 16, mask: true,
};

export default function GlMap({
  optimizationState,
  selectedServices: propSelectedServices = null,
  inspectedService = null,
  regionFilter = 'world',
  layerVisibility = null,
  onSelectService = null,
  onClearService = null,
  drawKey = null,
  focusPort = null,
  unserved = null,
  diff = null,
  onPortOpen = null,
  openPort = null,
  dataset = 'worldsmall',
  disruption = null,     // { closed: [passage], detourAvoid: [passage], rerouted: Set('A|B'), suspended: Set(serviceId) }
  itinerary = null,      // transit finder: { origin, destination, hubs: [port], segments: [{ service, calls: [port] }] }
  syncGroup = null,      // maps sharing a name keep one camera (Run diff split screen, services/mapSync.js)
  diffSide = null,       // 'A' | 'B': one side of a split Run diff, the legend lists only that side's statuses
  fitPorts = null,       // port codes to frame instead of the services' own (split maps frame A ∪ B alike)
  snapshotId = null,     // registers the map for the one-page PDF plan report (services/mapSnapshot.js)
}) {
  const [selectedCorridor, setSelectedCorridor] = useState(null);
  const [clickedPort, setClickedPort] = useState(null);
  const [legendOpen, setLegendOpen] = useState(() => typeof window === 'undefined' || window.innerWidth >= 768);
  const [fatal, setFatal] = useState(null);
  const [ready, setReady] = useState(false);
  const [zoomInfo, setZoomInfo] = useState({ zoom: 0, min: 0 });
  const [agentFocus] = useAgentFocus();
  const hover = useHoverTarget();
  const motion = useMotionLevel();
  const mapPrefs = useMapPrefs();
  const registryVersion = portRegistryVersion();
  if (fatal) throw fatal;   // caught by the WorldMap boundary → classic SVG map

  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const overlayRef = useRef(null);
  const dayRef = useRef(null);
  const userMovedRef = useRef(false);

  /* ── Data on screen (same rules as the SVG map) ── */
  const allServices = useMemo(() => {
    if (Array.isArray(propSelectedServices) && propSelectedServices.length > 0) return propSelectedServices;
    return (optimizationState?.global?.selected_services) || [];
  }, [propSelectedServices, optimizationState?.global?.selected_services]);

  const matchesRegion = useCallback((svcRegion, targetRegion) => {
    if (!targetRegion || targetRegion === 'world') return true;
    const r = String(svcRegion || '').toLowerCase();
    const t = String(targetRegion).toLowerCase();
    if (t === 'americas') return r.includes('americ');
    if (t === 'europe') return r.includes('europ');
    if (t === 'middle_east' || t === 'middle east') return r.includes('middl') || r.includes('east');
    if (t === 'asia' || t === 'asia pacific') return r.includes('asia') || r.includes('pacif');
    if (t === 'africa') return r.includes('afric');
    return r === t;
  }, []);

  const services = useMemo(() => {
    if (inspectedService) return [inspectedService];
    return allServices.filter((s) => matchesRegion(s.region, regionFilter) && matchesAgent(s, agentFocus));
  }, [allServices, inspectedService, regionFilter, matchesRegion, agentFocus]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const loc = useCallback((portId) => getPortCoordinates(portId), [registryVersion]);

  const callCount = useMemo(() => {
    const m = new Map();
    services.forEach((svc) => (svc.ports || []).forEach((p) => m.set(p, (m.get(p) || 0) + 1)));
    return m;
  }, [services]);
  const maxCalls = useMemo(() => Math.max(1, ...callCount.values()), [callCount]);

  // Each service's leg schedule (closed loop): drives the vessels and asks for the closing leg's sea lane.
  const schedules = useMemo(() => services.map((svc) => ({ svc, schedule: legScheduleOf(svc, loc) })).filter((x) => x.schedule), [services, loc]);

  // Legs of the services on screen, one per directed port pair (MODE B), with diff status and colour.
  const corridors = useMemo(() => {
    if (inspectedService) return [];
    const legMap = {};
    services.forEach((svc) => {
      if (!Array.isArray(svc.ports) || svc.ports.length < 2) return;
      for (let i = 0; i < svc.ports.length - 1; i++) {
        const from = svc.ports[i]; const to = svc.ports[i + 1];
        if (!from || !to || from === to) continue;
        const key = `${from}__${to}`;
        if (!legMap[key]) legMap[key] = { id: key, from, to, service_count: 0, total_load: 0, regions: new Set(), serviceObjs: [] };
        legMap[key].service_count += 1;
        legMap[key].total_load += (Number(svc.load) || 0);
        if (svc.region) legMap[key].regions.add(svc.region);
        legMap[key].serviceObjs.push(svc);
      }
    });
    return Object.values(legMap).map((leg) => {
      if (!loc(leg.from) || !loc(leg.to)) return null;
      const fromReg = portGeoRegion(leg.from); const toReg = portGeoRegion(leg.to);
      const isInterRegional = Boolean(fromReg && toReg && fromReg !== toReg);
      let diffStatus = null;
      if (diff) {
        const st = new Set(leg.serviceObjs.map((sv) => diff.get(String(sv.id)) || 'kept'));
        diffStatus = st.size === 1 ? [...st][0] : 'kept';
      }
      // What-if closure: legs sailing a detour, and legs only suspended services sailed.
      let disrupt = null;
      if (disruption) {
        if (leg.serviceObjs.every((sv) => disruption.suspended.has(String(sv.id)))) disrupt = 'suspended';
        else if (disruption.rerouted.has(`${leg.from}|${leg.to}`)) disrupt = 'rerouted';
      }
      return {
        ...leg, isInterRegional, diffStatus, disrupt,
        color: disrupt ? DISRUPT_TONE[disrupt] : diffStatus ? DIFF_TONE[diffStatus] : isInterRegional && regionFilter === 'world' ? '#fbbf24' : getRegionColor(fromReg),
        regions: Array.from(leg.regions),
        avg_load: Math.round(leg.total_load / (leg.service_count || 1)),
      };
    }).filter(Boolean);
  }, [services, inspectedService, regionFilter, loc, diff, disruption]);

  // Sea lanes for every leg on screen plus each loop's closing leg.
  const pairs = useMemo(() => {
    const out = corridors.map((l) => [l.from, l.to]);
    schedules.forEach(({ schedule }) => schedule.legs.forEach((l) => out.push([l.from, l.to])));
    return out;
  }, [corridors, schedules]);
  const { routes, status: routeStatus } = useSeaRoutes(dataset, pairs, loc);
  // Closure scenario: the re-routed legs' detours, from the same sea-lane network with the closed passages avoided.
  const detourAvoid = disruption ? [...disruption.closed, ...disruption.detourAvoid].sort().join(',') : '';
  const detourPairs = useMemo(() => (disruption ? pairs.filter(([a, b]) => disruption.rerouted.has(`${a}|${b}`)) : []), [pairs, disruption]);
  const { routes: detours } = useSeaRoutes(dataset, detourPairs, loc, detourAvoid);
  const dense = useMemo(() => new WeakMap(), []);
  const pathOf = useCallback((a, b) => {
    const k = `${a}|${b}`;
    const r = (disruption?.rerouted.has(k) && detours.get(k)?.source === 'searoute' && detours.get(k)) || routes.get(k);
    if (r) {
      if (!dense.has(r)) dense.set(r, { ...r, coords: densify(r.coords) });
      return dense.get(r);
    }
    const pa = loc(a); const pb = loc(b);
    return pa && pb ? { coords: greatCircle(pa, pb), source: 'great-circle', passages: [] } : null;
  }, [routes, detours, disruption, loc]);

  const maxLegLoad = useMemo(() => Math.max(0, ...corridors.map((l) => l.total_load)), [corridors]);
  const topCorridors = useMemo(() => [...corridors].sort((a, b) => b.total_load - a.total_load).slice(0, 4), [corridors]);
  const drawDelay = useMemo(() => {
    const ranked = [...corridors].sort((a, b) => b.total_load - a.total_load);
    const n = Math.max(1, ranked.length - 1);
    return new Map(ranked.map((l, i) => [l.id, Math.round((i / n) * DRAW_SPREAD_MS)]));
  }, [corridors]);

  // Leg geometry joined to the corridors (re-made when the sea lanes arrive).
  const corridorPaths = useMemo(() => corridors.map((l) => {
    const r = pathOf(l.from, l.to);
    if (!r) return null;
    const cum = pathMeasure(r.coords);
    const total = cum[cum.length - 1] || 1;
    return { ...l, route: r, path: r.coords, frac: cum.map((c) => c / total) };
  }).filter(Boolean), [corridors, pathOf]);

  // Single-service inspection: its legs in calling order, plus the closing leg back to the first port.
  const inspectedLegs = useMemo(() => {
    if (!inspectedService) return [];
    const sch = schedules[0]?.schedule;
    const ports = inspectedService.ports || [];
    const legs = sch ? sch.legs : ports.slice(0, -1).map((p, i) => ({ from: p, to: ports[i + 1] }));
    const color = getRegionColor(inspectedService.region);
    return legs.map((l, i) => {
      if (!l.from || !l.to || l.from === l.to) return null;
      const r = pathOf(l.from, l.to);
      if (!r) return null;
      const closing = sch ? i === legs.length - 1 : false;
      return { id: `${inspectedService.id}_${i}`, from: l.from, to: l.to, route: r, path: r.coords, color, closing };
    }).filter(Boolean);
  }, [inspectedService, schedules, pathOf]);

  // Transit finder: the legs the box rides, one colour per service ridden, and its origin / transfer / destination ports.
  const itinLegs = useMemo(() => (itinerary ? itinerary.segments.flatMap((sg, si) => sg.calls.slice(0, -1).map((a, i) => {
    const b = sg.calls[i + 1];
    const r = pathOf(a, b);
    return r ? { id: `itin_${si}_${i}`, from: a, to: b, path: r.coords, color: ITIN_TONES[si % ITIN_TONES.length], service: sg.service } : null;
  }).filter(Boolean)) : []), [itinerary, pathOf]);
  const itinPorts = useMemo(() => {
    if (!itinerary) return [];
    const role = (c) => (c === itinerary.origin ? 'origin' : c === itinerary.destination ? 'destination' : itinerary.hubs.includes(c) ? 'transfer' : 'call');
    const codes = [...new Set(itinerary.segments.flatMap((sg) => sg.calls))];
    return codes.map((c) => ({ code: c, coords: loc(c), role: role(c) })).filter((d) => d.coords);
  }, [itinerary, loc]);

  // Vessels: per service, each schedule leg's sea-lane path with its length measure.
  const fleets = useMemo(() => schedules.filter(({ svc }) => !disruption?.suspended.has(String(svc.id))).map(({ svc, schedule }) => ({
    svc,
    schedule,
    color: inspectedService ? '#f8fafc' : getRegionColor(svc.region),
    vessels: Math.max(1, Math.min(MAX_VESSELS_PER_SERVICE, Number(svc.vessels) || 1)),
    headway: 7 / (Number(svc.frequency_per_week) || 1),
    legs: schedule.legs.map((l) => {
      const r = pathOf(l.from, l.to);
      const coords = r ? r.coords : [loc(l.from) || [0, 0], loc(l.to) || [0, 0]];
      return { from: l.from, to: l.to, coords, cum: pathMeasure(coords) };
    }),
  })), [schedules, pathOf, loc, inspectedService, disruption]);
  const vesselCount = useMemo(() => fleets.reduce((a, f) => a + f.vessels, 0), [fleets]);

  // Unserved demand (rings + the largest lanes, great-circle dashed: demand not sailed has no sea lane).
  const unservedRings = useMemo(() => {
    if (!unserved?.hasDemand || inspectedService) return [];
    const out = [];
    unserved.ports.forEach((p) => {
      const teu = p.unservedOut + p.unservedIn;
      const c = teu > 0 ? loc(p.code) : null;
      if (!c) return;
      if (regionFilter && regionFilter !== 'world' && !matchesRegion(portGeoRegion(p.code), regionFilter)) return;
      out.push({ code: p.code, coords: c, teu, out: p.unservedOut, in: p.unservedIn, demand: p.demandOut + p.demandIn });
    });
    return out.sort((a, b) => b.teu - a.teu);
  }, [unserved, inspectedService, loc, regionFilter, matchesRegion]);
  const unservedLanes = useMemo(() => {
    if (!unserved?.hasDemand || inspectedService) return [];
    const inView = (code) => !regionFilter || regionFilter === 'world' || matchesRegion(portGeoRegion(code), regionFilter);
    return unserved.lanes.filter((l) => inView(l.o) || inView(l.d)).slice(0, UNSERVED_LANES_SHOWN).map((l) => {
      const a = loc(l.o); const b = loc(l.d);
      return a && b ? { ...l, path: greatCircle(a, b) } : null;
    }).filter(Boolean);
  }, [unserved, inspectedService, loc, regionFilter, matchesRegion]);
  const unservedMax = unservedRings.length ? unservedRings[0].teu : 0;

  const lay = mapPrefs.layers;

  // Risk layer: the chokepoints, sized by the TEU the plan carries through them, with real PortWatch traffic.
  const [run, setRun] = useState(getSelectedRun());
  useEffect(() => subscribeRun(setRun), []);
  const chokeOn = lay.chokepoints && !diff;
  // Regulation layer: SOx emission control areas (0.10 % sulphur), Marine Regions polygons served by the backend.
  const eca = useEcaZones(Boolean(lay.eca));
  const war = useWarRiskAreas(Boolean(lay.warrisk) && !diff);
  const piracy = usePiracy(Boolean(lay.piracy) && !diff);
  // Live layer: real vessels heard by AIS (Digitraffic, Baltic), refreshed every minute while on.
  const ais = useAisLive(Boolean(lay.ais) && !diff);
  // Weather layers: forecast sea state and mean currents at the lane sample points (Open-Meteo Marine, backend/weather.py).
  const sea = useMapSeaState(Boolean(lay.seastate || lay.currents) && !diff);
  const seaPts = useMemo(() => (sea.data?.points || []).filter((p) => p.hs_max_m != null || p.u != null).map((p) => {
    const kn = p.u == null ? null : Math.hypot(p.u, p.v);
    return { ...p, kn, dir: kn == null ? null : (Math.atan2(p.u, p.v) * 180 / Math.PI + 360) % 360 };
  }), [sea.data]);
  const exposure = useChokepointExposure(chokeOn ? run : null);
  const portwatch = usePortWatch(chokeOn);
  const chokeData = useMemo(() => {
    if (!chokeOn) return [];
    const byId = new Map((exposure.data?.passages || []).map((p) => [p.id, p]));
    const pw = portwatch.data?.chokepoints || {};
    return Object.entries(CHOKEPOINT_AT).map(([id, c]) => {
      const e = byId.get(id);
      return { id, name: c.name, at: c.at, teu: e?.teu_per_week || 0, share: e?.share_of_teu_legs_pct ?? null,
        services: e?.services?.length || 0, sailings: e?.sailings_per_week || 0, pw: pw[id] || null,
        closed: Boolean(disruption?.closed.includes(id)) };
    });
  }, [chokeOn, exposure.data, portwatch.data, disruption]);
  const chokeMax = Math.max(1, ...chokeData.map((c) => c.teu));
  // Names only where they matter at world zoom: closed passages and the four busiest (others: hover).
  const chokeLabels = useMemo(() => {
    const busiest = new Set(chokeData.filter((c) => c.teu > 0).sort((a, b) => b.teu - a.teu).slice(0, 4).map((c) => c.id));
    return chokeData.filter((c) => c.closed || busiest.has(c.id));
  }, [chokeData]);
  // Plan layer: transshipment hubs, ring area = TEU changing ship there (the plan's own ledger flows; services/transshipmentData.js).
  const hubsOn = Boolean(lay.hubs) && !diff && !inspectedService;
  const transship = useTransshipment(optimizationState);
  const hubData = useMemo(() => {
    if (!hubsOn || !transship.model) return [];
    const onScreen = new Set(services.flatMap((s) => s.ports || []));
    return transship.model.hubs.filter((h) => onScreen.has(h.code) && loc(h.code)).map((h) => ({ ...h, coords: loc(h.code) }));
  }, [hubsOn, transship.model, services, loc]);
  const hubMax = hubData.length ? Math.max(...hubData.map((h) => h.teu)) : 0;
  const showPorts = (!layerVisibility || layerVisibility.has('ports')) && lay.ports;
  const showSelected = (!layerVisibility || layerVisibility.has('selected')) && lay.routes;

  const portDots = useMemo(() => {
    const codes = new Set([...activeDatasetPorts(), ...callCount.keys()]);
    const out = [];
    codes.forEach((code) => {
      const c = loc(code);
      if (!c) return;
      const region = portGeoRegion(code);
      if (regionFilter && regionFilter !== 'world' && !matchesRegion(region, regionFilter)) return;
      const calls = callCount.get(code) || 0;
      out.push({ code, coords: c, region, calls, r: calls ? 1.8 + 3.2 * Math.sqrt(calls / maxCalls) : 1.4 });
    });
    return out.sort((a, b) => a.calls - b.calls);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [callCount, maxCalls, loc, regionFilter, matchesRegion, registryVersion]);

  const keyPortLabels = useMemo(() => [...callCount.entries()]
    .map(([id, n]) => ({ id, n, coords: loc(id) }))
    .filter((p) => p.coords).sort((a, b) => b.n - a.n).slice(0, 10), [callCount, loc]);

  const inspectedPorts = useMemo(() => {
    if (!inspectedService) return [];
    const ports = inspectedService.ports || [];
    return ports.map((id, idx) => {
      const c = loc(id);
      if (!c) return null;
      const tag = idx === 0 ? 'ORIGIN' : idx === ports.length - 1 ? 'LAST CALL' : `CALL ${idx + 1}`;
      return { id, idx, coords: c, origin: idx === 0, dest: idx === ports.length - 1, label: `${tag} · ${id}\n${getPortName(id)}` };
    }).filter(Boolean);
  }, [inspectedService, loc]);

  const hoverLit = useMemo(() => {
    if (!hover || inspectedService) return null;
    const legs = new Set(); const ports = new Set();
    corridors.forEach((l) => {
      if (l.serviceObjs.some((s) => matchesHover(s, hover))) { legs.add(l.id); ports.add(l.from); ports.add(l.to); }
    });
    return legs.size ? { legs, ports } : null;
  }, [hover, inspectedService, corridors]);

  const fitPoints = useMemo(() => {
    const codes = fitPorts?.length ? fitPorts : itinerary ? [...new Set(itinerary.segments.flatMap((sg) => sg.calls))]
      : inspectedService ? (inspectedService.ports || []) : [...callCount.keys()];
    const pts = codes.map(loc).filter(Boolean);
    return pts.length ? pts : portDots.map((p) => p.coords);
  }, [fitPorts, itinerary, inspectedService, callCount, loc, portDots]);
  const fitKey = useMemo(() => fitPoints.map((p) => p.join(',')).sort().join(';'), [fitPoints]);

  /* ── Map lifecycle ── */
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return undefined;
    let map; let overlay; let ro;
    try {
      map = new maplibregl.Map({
        container: el,
        style: buildStyle(mapPrefs.basemap, mapPrefs.projection),
        bounds: WORLD_BOUNDS,
        renderWorldCopies: true,
        attributionControl: { compact: true },
        cooperativeGestures: true,
        dragRotate: false,
        pitchWithRotate: false,
        maxPitch: 0,
        minZoom: 0,
        maxZoom: 10,
        fadeDuration: 0,
      });
      map.touchZoomRotate.disableRotation();
      map.keyboard.disableRotation();
      overlay = new MapLibreOverlay({ interleaved: true, layers: [], getTooltip: (info) => tooltipRef.current(info), onClick: (info) => clickRef.current(info) });
      map.addControl(overlay);
    } catch (e) {
      setFatal(e instanceof Error ? e : new Error(String(e)));
      return undefined;
    }
    mapRef.current = map;
    overlayRef.current = overlay;
    const onZoom = () => setZoomInfo({ zoom: map.getZoom(), min: map.getMinZoom() });
    map.on('zoomend', onZoom);
    map.on('load', () => { setReady(true); onZoom(); });
    map.on('error', (ev) => { if (ev?.error && /webgl/i.test(String(ev.error.message))) setFatal(ev.error); });
    // A drag / wheel / pinch by the viewer (originalEvent set) stops the automatic refit on resize.
    map.on('movestart', (e) => { if (e.originalEvent) userMovedRef.current = true; });
    let lastW = el.clientWidth; let lastH = el.clientHeight;
    ro = new ResizeObserver(() => {
      map.resize();
      if (Math.abs(el.clientWidth - lastW) > 40 || Math.abs(el.clientHeight - lastH) > 40) {
        lastW = el.clientWidth; lastH = el.clientHeight;
        if (!userMovedRef.current && fittedOnce.current) fitCameraRef.current(false);
      }
      el.parentElement?.style.setProperty('--map-h', `${el.clientHeight}px`);   // layer panel max height
    });
    ro.observe(el);
    return () => {
      ro.disconnect();
      try { map.removeControl(overlay); } catch (_) { /* already gone */ }
      map.remove();
      mapRef.current = null; overlayRef.current = null;
      setReady(false);   // a re-created map (hot reload) must load its style before projection / basemap calls
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!ready || !syncGroup || !mapRef.current) return undefined;
    return joinSync(syncGroup, mapRef.current, containerRef.current?.closest('.gl-root'));
  }, [ready, syncGroup]);

  // The canvas is read inside MapLibre's 'render' event, before the frame is handed to the screen, so the
  // drawing buffer does not have to be preserved for every frame.
  useEffect(() => {
    if (!ready || !snapshotId) return undefined;
    return registerSnapshot(snapshotId, () => new Promise((resolve) => {
      const map = mapRef.current;
      if (!map) { resolve(null); return; }
      const t = setTimeout(() => resolve(null), 3000);
      map.once('render', () => {
        clearTimeout(t);
        try {
          const c = map.getCanvas();
          resolve({ url: c.toDataURL('image/jpeg', 0.9), width: c.width, height: c.height });
        } catch (_) { resolve(null); }   // a basemap without CORS taints the canvas
      });
      map.triggerRepaint();
    }));
  }, [ready, snapshotId]);

  // Projection and basemap follow the viewer's choice without rebuilding the map.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    map.setProjection({ type: mapPrefs.projection });
    fitCameraRef.current(true);
  }, [mapPrefs.projection, ready]);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    applyBasemap(map, mapPrefs.basemap);
  }, [mapPrefs.basemap, ready]);

  /* ── Camera ── */
  const legendPad = legendOpen ? 230 : 40;
  const fitCamera = useCallback((animate) => {
    const map = mapRef.current;
    if (!map) return;
    userMovedRef.current = false;
    const fit = boundsOf(fitPoints);
    const w = containerRef.current?.clientWidth || 800;
    const h = containerRef.current?.clientHeight || 400;
    const left = w < 640 ? 24 : legendPad;
    const duration = animate && motionLevel() === 'full' ? GLIDE_MS : 0;
    // A whole-world view on the globe: centre the sphere and size it to the frame (≈ 512·2^z/π px across).
    if (!fit && getMapPrefs().projection === 'globe') {
      map.easeTo({ center: [30, 18], zoom: Math.log2((1.1 * (h - 60) * Math.PI) / 512), duration });
      return;
    }
    const b = fit || WORLD_BOUNDS;
    map.fitBounds(b, {
      padding: { top: 48, bottom: 72, left, right: 40 }, maxZoom: MAX_FIT_ZOOM, duration,
    });
  }, [fitPoints, legendPad]);
  const fitCameraRef = useRef(fitCamera);
  fitCameraRef.current = fitCamera;
  const fittedOnce = useRef(false);
  useEffect(() => {
    if (!ready) return;
    fitCamera(fittedOnce.current);
    fittedOnce.current = true;
  }, [fitKey, ready]); // eslint-disable-line react-hooks/exhaustive-deps

  const zoomBy = (dir) => {
    const map = mapRef.current;
    if (!map) return;
    const opts = { duration: motion === 'full' ? GLIDE_MS : 0 };
    if (dir > 0) map.zoomIn(opts); else map.zoomOut(opts);
  };
  const pickPort = useCallback((code) => {
    const c = loc(code);
    if (onPortOpen) onPortOpen(code); else setClickedPort(code);
    const map = mapRef.current;
    if (c && map) map.easeTo({ center: c, zoom: Math.max(PORT_ZOOM, map.getZoom()), duration: motionLevel() === 'full' ? GLIDE_MS : 0 });
  }, [loc, onPortOpen]);
  useEffect(() => { if (focusPort && ready) pickPort(focusPort); }, [focusPort, ready]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ── Draw-on, once per run and surface ── */
  const drawStart = useRef(0);
  const [drawing, setDrawing] = useState(null);   // null | 'full' | 'reduced'
  const hasLegs = corridors.length > 0;
  useLayoutEffect(() => {
    if (!drawKey || !hasLegs || drawnKeys.has(drawKey)) return;
    drawnKeys.add(drawKey);
    if (motion !== 'off') { drawStart.current = performance.now(); setDrawing(motion); }
  }, [drawKey, hasLegs]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!drawing) return undefined;
    const t = setTimeout(() => setDrawing(null), drawing === 'full' ? DRAW_TOTAL_MS : 150);
    return () => clearTimeout(t);
  }, [drawing]);

  // Inspection starts the clock at full motion, so the vessels sail as soon as a service is opened.
  useEffect(() => { if (inspectedService && motion === 'full') playTimeline(); }, [inspectedService?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ── Tooltip and click (read through refs so the overlay never needs re-binding) ── */
  const tooltipRef = useRef(null);
  const clickRef = useRef(null);
  tooltipRef.current = ({ object, layer }) => {
    if (!object || !layer) return null;
    const id = layer.id;
    let html = null;
    if (id === 'routes' || id === 'routes-hit') {
      const l = object;
      const r = l.route;
      const geo = r.source === 'searoute'
        ? `Sea lane ${nm(r.nm)} · optimizer (LINERLIB) ${nm(r.model_nm)}${r.passages?.length ? `<br>via ${r.passages.map(passageName).map(esc).join(', ')}` : '<br>no strait or canal passed'}`
        : 'Great-circle path (sea lanes unavailable)';
      html = `<b>${esc(l.from)} → ${esc(l.to)}</b> · ${fmtNum(l.total_load)} TEU on ${l.service_count} service${l.service_count === 1 ? '' : 's'}${l.diffStatus ? ` · ${l.diffStatus === 'kept' ? 'in both runs' : l.diffStatus === 'added' ? 'only in run B' : 'only in run A'}` : ''}<br>${geo}`;
    } else if (id === 'insp-legs') {
      const r = object.route;
      html = `<b>${esc(object.from)} → ${esc(object.to)}</b>${object.closing ? ' (return leg: the service is a loop)' : ''}<br>${r.source === 'searoute' ? `Sea lane ${nm(r.nm)} · optimizer ${nm(r.model_nm)}${r.passages?.length ? `<br>via ${r.passages.map(passageName).map(esc).join(', ')}` : ''}` : 'Great-circle path (sea lanes unavailable)'}`;
    } else if (id === 'ports') {
      const p = object;
      html = `<b>${esc(getPortName(p.code))}</b> (${esc(p.code)})${p.calls ? ` · ${p.calls} call${p.calls === 1 ? '' : 's'}` : ' · not called by the plan'}`;
    } else if (id === 'unserved-rings') {
      const p = object;
      html = `<b>${esc(getPortName(p.code))}</b> (${esc(p.code)})<br>${fmtNum(p.teu)} TEU/week unserved (${fmtNum(p.out)} out, ${fmtNum(p.in)} in) of ${fmtNum(p.demand)} demand`;
    } else if (id === 'hubs') {
      const h = object;
      const top = h.pairs[0];
      html = `<b>${esc(getPortName(h.code) || h.name || h.code)}</b> (${esc(h.code)}) · transshipment hub<br>${fmtNum(Math.round(h.teu))} TEU/week change ship here (${h.shareOfMoves.toFixed(1)}% of all transfers) on ${h.flows} OD flow${h.flows === 1 ? '' : 's'}${h.cost != null ? `<br>Transshipment ${fmtUsd(h.cost)}/week at ${fmtUsd(h.costPerTeu)}/TEU` : ''}${top ? `<br>Busiest connection ${esc(top.from)} → ${esc(top.to)}: ${fmtNum(Math.round(top.teu))} TEU` : ''}<br><span style="color:#94a3b8">${h.services.length} services connect here · Network → Transshipment</span>`;
    } else if (id === 'unserved-lanes') {
      html = `<b>${esc(object.o)} → ${esc(object.d)}</b><br>${fmtNum(object.teu)} of ${fmtNum(object.demand)} TEU/week not carried`;
    } else if (id === 'ais') {
      const v = object;
      html = `<b>${esc(v.name || `MMSI ${v.mmsi}`)}</b> · ${esc(v.category)} (AIS type ${v.ship_type ?? '—'})<br>${v.sog_kn != null ? `${v.sog_kn} kn` : '—'}, course ${v.cog ?? '—'}°${v.draught_m ? ` · draught ${v.draught_m} m` : ''}${v.destination ? ` · to ${esc(v.destination)}` : ''}<br><span style="color:#94a3b8">live AIS, ${v.age_min} min ago (Digitraffic)</span>`;
    } else if (id === 'seastate' || id === 'currents') {
      const p = object;
      const when = p.hs_max_at ? `${p.hs_max_at.slice(5, 10)} ${p.hs_max_at.slice(11, 16)} UTC` : '';
      const rows = [];
      if (p.hs_max_m != null) rows.push(`Worst forecast wave height <b>${p.hs_max_m.toFixed(1)} m</b> (${esc(p.name)}, WMO ${p.code})${when ? ` on ${when}` : ''}${p.hrs_ge4 ? ` · ${p.hrs_ge4} h at 4 m or more` : ''}`);
      if (p.kn != null) rows.push(`Mean current ${p.kn.toFixed(2)} kn flowing to ${Math.round(p.dir)}°`);
      html = `<b>${p.lat.toFixed(1)}°, ${p.lon.toFixed(1)}°</b> · lane sample<br>${rows.join('<br>')}<br><span style="color:#94a3b8">Open-Meteo Marine forecast, ${esc(sea.data?.forecast_days)} days from ${esc(sea.data?.fetched_on || '')}</span>`;
    } else if (id === 'warrisk') {
      const p = object.properties || {};
      const zones = (p.zones || []).map((z) => `${esc(z.label)}: <b>${z.default_pct}%</b> of hull value per visit`).join('<br>');
      html = `<b>${esc(p.label)}</b> · JWC listed area<br>${zones}<br><span style="color:#94a3b8">${esc(war.data?.circular?.id)} (${esc(war.data?.circular?.date)}) · ${esc(p.drawn)} · default rates, editable in What-if</span>`;
    } else if (id === 'piracy') {
      const p = object;
      html = `<b>${esc(p.date)}</b> · ${esc(p.hostility || 'incident')}${p.victim ? ` · ${esc(p.victim)}` : ''}<br>${esc(p.description || '')}<br><span style="color:#94a3b8">NGA ASAM · ${p.lat.toFixed(2)}°, ${p.lon.toFixed(2)}°</span>`;
    } else if (id === 'eca') {
      const p = object.properties || {};
      html = `<b>${esc(p.name)}</b> · SOx emission control area<br>Fuel sulphur ≤ ${p.sox_limit_pct}% (marine gas oil or a scrubber) · in force ${esc(p.in_force)}<br><span style="color:#94a3b8">${esc(p.source)}</span>`;
    } else if (id === 'chokepoints') {
      const c = object;
      const pw = c.pw;
      const ch = pw ? yoyPct(pw.last30.container, pw.year_before.container) : null;
      const plan = c.teu > 0
        ? `Plan: ${fmtNum(c.teu)} TEU/wk on ${c.services} service${c.services === 1 ? '' : 's'} (${c.sailings} sailings/wk)${c.share != null ? ` · ${c.share.toFixed(1)}% of carried TEU-legs` : ''}`
        : exposure.status === 'ok' ? 'Plan: no leg crosses it' : 'Plan exposure needs the backend';
      const real = pw
        ? `Real traffic (PortWatch, 30 days to ${esc(pw.data_through)}): ${pw.last30.container ?? '—'} container ships/day vs ${pw.year_before.container ?? '—'} a year earlier${ch != null ? ` (${ch >= 0 ? '+' : '−'}${Math.abs(ch).toFixed(0)}%)` : ''}; all ships ${pw.last30.total ?? '—'}/day`
        : portwatch.status === 'loading' ? 'Real traffic: loading PortWatch…' : 'Real traffic: PortWatch unavailable';
      html = `<b>${esc(c.name)}</b>${c.closed ? ' · <b style="color:#f87171">CLOSED in this scenario</b>' : ''}<br>${plan}<br>${real}`;
    } else if (id === 'vessels') {
      const v = object;
      html = `<b>${esc(v.svc)}</b> · vessel ${v.n} of ${v.of}<br>${v.where}<br>day ${v.cycleDay.toFixed(1)} of the ${v.cycle}-day cycle`;
    }
    return html ? { html, className: 'gl-tip' } : null;
  };
  clickRef.current = ({ object, layer }) => {
    if (!object || !layer) return;
    if (layer.id === 'ports' || layer.id === 'unserved-rings' || layer.id === 'hubs') pickPort(object.code);
    else if (layer.id === 'routes' || layer.id === 'routes-hit') {
      if (onSelectService && object.serviceObjs.length) onSelectService(object.serviceObjs[0]);
      else setSelectedCorridor(object);
    }
  };

  /* ── deck.gl layers ── */
  const flowsOn = lay.flows && motion === 'full' && !inspectedService && showSelected;
  // Run diff shows two plans at once; vessels of both on one clock would mean nothing, so the replay is off there.
  const vesselsOn = lay.vessels && !diff;
  const model = {
    corridorPaths, inspectedLegs, inspectedPorts, unservedRings, unservedLanes, portDots, keyPortLabels, fleets,
    maxLegLoad, maxCalls, hoverLit, drawDelay, drawing, showPorts, showSelected, labelsOn: lay.labels && !itinerary, flowsOn,
    vesselsOn, openPort, unservedMax, inspected: Boolean(inspectedService), hubData, hubMax, chokeData, chokeMax, chokeLabels, itinLegs, itinPorts, ecaData: lay.eca ? eca.data : null, warData: lay.warrisk && !diff ? war.data : null, piracyData: lay.piracy && !diff ? piracy.data?.incidents || null : null, aisData: lay.ais && !diff ? ais.data?.vessels || null : null,
    seaPts: lay.seastate && !diff ? seaPts.filter((p) => p.hs_max_m != null) : [], curPts: lay.currents && !diff ? seaPts.filter((p) => p.kn != null && p.kn >= 0.3) : [],
  };
  const modelRef = useRef(model);
  modelRef.current = model;

  const buildLayers = useCallback((now) => {
    const m = modelRef.current;
    const out = [];
    const dim = (lit) => (m.itinLegs.length ? 0.22 : m.hoverLit ? (lit ? 1 : 0.14) : 1);
    const day = getTimeline().day;

    // ECA polygons under every plan layer.
    if (m.ecaData) {
      out.push(new GeoJsonLayer({
        ...LAYER_BASE, id: 'eca', data: m.ecaData, pickable: true, stroked: true, filled: true,
        getFillColor: rgb(ECA_TONE, 0.1), getLineColor: rgb(ECA_TONE, 0.65), getLineWidth: 1, lineWidthUnits: 'pixels',
      }));
    }

    // JWC war-risk listed areas, under the plan; piracy incidents on top of them.
    if (m.warData) {
      out.push(new GeoJsonLayer({
        ...LAYER_BASE, id: 'warrisk', data: m.warData, pickable: true, stroked: true, filled: true,
        getFillColor: rgb(WAR_TONE, 0.1), getLineColor: rgb(WAR_TONE, 0.7), getLineWidth: 1.2, lineWidthUnits: 'pixels',
      }));
    }
    if (m.piracyData?.length) {
      out.push(new ScatterplotLayer({
        ...LAYER_BASE, id: 'piracy', data: m.piracyData, pickable: true, getPosition: (d) => [d.lon, d.lat],
        getRadius: 4, radiusUnits: 'pixels', stroked: true, getFillColor: rgb(PIRACY_TONE, 0.9),
        getLineColor: [15, 23, 42, 220], getLineWidth: 1, lineWidthUnits: 'pixels',
      }));
    }

    // Forecast sea state at the lane sample points (worst wave height in the window) and the mean current there.
    if (m.seaPts.length) {
      out.push(new ScatterplotLayer({
        ...LAYER_BASE, id: 'seastate', data: m.seaPts, pickable: true, getPosition: (d) => [d.lon, d.lat],
        getRadius: (d) => 2 + Math.min(12, d.hs_max_m) * 0.45, radiusUnits: 'pixels', radiusMaxPixels: 8,
        getFillColor: (d) => rgb(seaRiskTone(d.risk), { low: 0.3, moderate: 0.45, high: 0.7, severe: 0.9 }[d.risk] ?? 0.3), stroked: false,
      }));
    }
    if (m.curPts.length) {
      out.push(new IconLayer({
        ...LAYER_BASE, id: 'currents', data: m.curPts, pickable: true, getPosition: (d) => [d.lon, d.lat], getIcon: () => VESSEL_ICON,
        getSize: (d) => 8 + Math.min(3, d.kn) * 4, sizeUnits: 'pixels', billboard: false,
        getAngle: (d) => 90 - d.dir, getColor: (d) => rgb(CURRENT_TONE, Math.min(0.95, 0.35 + d.kn * 0.3)),
      }));
    }

    // Unserved lanes under everything else.
    if (m.unservedLanes.length) {
      const top = m.unservedLanes[0].teu || 1;
      out.push(new PathLayer({
        ...LAYER_BASE, id: 'unserved-lanes', data: m.unservedLanes, getPath: (d) => d.path, pickable: true,
        getColor: rgb(VIZ_2, m.hoverLit ? 0.15 : 0.75), getWidth: (d) => 0.8 + 2.2 * Math.sqrt(d.teu / top), widthUnits: 'pixels',
        getDashArray: [4, 3], dashJustified: true, extensions: [new PathStyleExtension({ dash: true })],
        updateTriggers: { getColor: [Boolean(m.hoverLit)] },
      }));
    }

    if (m.inspected) {
      const legs = m.inspectedLegs.filter((l) => !l.closing);
      out.push(new PathLayer({ ...LAYER_BASE, id: 'insp-glow', data: legs, getPath: (d) => d.path, getColor: (d) => rgb(d.color, 0.3), getWidth: 7.5, widthUnits: 'pixels', capRounded: true, jointRounded: true }));
      out.push(new PathLayer({ ...LAYER_BASE, id: 'insp-legs', data: m.inspectedLegs, getPath: (d) => d.path, pickable: true,
        getColor: (d) => (d.closing ? rgb('#94a3b8', 0.45) : rgb(d.color, 0.95)), getWidth: (d) => (d.closing ? 1.2 : 3.5), widthUnits: 'pixels',
        capRounded: true, jointRounded: true, getDashArray: (d) => (d.closing ? [3, 3] : [0, 0]), extensions: [new PathStyleExtension({ dash: true })] }));
    } else if (m.showSelected) {
      const width = (d) => legWidth(d.total_load, m.maxLegLoad) * (m.hoverLit?.legs.has(d.id) ? 1.6 : 1);
      const color = (d) => rgb(d.color, 0.85 * dim(m.hoverLit?.legs.has(d.id)));
      if (m.drawing === 'full') {
        const t = now - drawStart.current;
        out.push(new TripsLayer({
          ...LAYER_BASE, id: 'routes-draw', data: m.corridorPaths, getPath: (d) => d.path,
          getTimestamps: (d) => d.frac.map((f) => (m.drawDelay.get(d.id) || 0) + f * DRAW_LEG_MS),
          currentTime: t, trailLength: 1e9, fadeTrail: false, getColor: color, getWidth: width, widthUnits: 'pixels', capRounded: true, jointRounded: true,
        }));
      } else {
        const fade = m.drawing === 'reduced' ? Math.min(1, (now - drawStart.current) / 150) : 1;
        out.push(new PathLayer({
          ...LAYER_BASE, id: 'routes', data: m.corridorPaths, getPath: (d) => d.path, pickable: true, autoHighlight: true,
          highlightColor: [255, 255, 255, 60], opacity: fade,
          getColor: color, getWidth: width, widthUnits: 'pixels', widthMinPixels: 1, capRounded: true, jointRounded: true,
          getDashArray: (d) => (d.diffStatus === 'removed' || d.disrupt === 'suspended' ? [6, 4] : [0, 0]), extensions: [new PathStyleExtension({ dash: true })],
          updateTriggers: { getColor: [m.hoverLit, m.itinLegs.length], getWidth: [m.hoverLit, m.maxLegLoad] },
        }));
      }
      if (m.flowsOn && m.drawing !== 'full') {
        const period = (now / FLOW_MS_PER_UNIT) % FLOW_PERIOD;
        out.push(new TripsLayer({
          ...LAYER_BASE, id: 'flows', data: m.corridorPaths, getPath: (d) => d.path,
          getTimestamps: (d) => d.frac.map((f) => f * 1000), currentTime: period, trailLength: FLOW_TRAIL, fadeTrail: true,
          getColor: (d) => rgb('#e2f3ff', 0.75 * dim(m.hoverLit?.legs.has(d.id))), getWidth: (d) => legWidth(d.total_load, m.maxLegLoad),
          widthUnits: 'pixels', capRounded: true, jointRounded: true, updateTriggers: { getColor: [m.hoverLit, m.itinLegs.length] },
        }));
      }
    }

    // Unserved rings (area ∝ TEU).
    if (m.unservedRings.length) {
      out.push(new ScatterplotLayer({
        ...LAYER_BASE, id: 'unserved-rings', data: m.unservedRings, getPosition: (d) => d.coords, pickable: true,
        getRadius: (d) => 3 + 13 * Math.sqrt(d.teu / (m.unservedMax || 1)), radiusUnits: 'pixels', stroked: true, filled: true,
        getFillColor: rgb(VIZ_2, m.hoverLit ? 0.02 : 0.1), getLineColor: rgb(VIZ_2, m.hoverLit ? 0.2 : 0.9), lineWidthUnits: 'pixels', getLineWidth: 1.4,
        updateTriggers: { getFillColor: [Boolean(m.hoverLit)], getLineColor: [Boolean(m.hoverLit)] },
      }));
    }

    // Transshipment hubs (rings, area ∝ TEU changing ship there).
    if (m.hubData.length) {
      out.push(new ScatterplotLayer({
        ...LAYER_BASE, id: 'hubs', data: m.hubData, getPosition: (d) => d.coords, pickable: true,
        getRadius: (d) => 4 + 14 * Math.sqrt(d.teu / (m.hubMax || 1)), radiusUnits: 'pixels', stroked: true, filled: true,
        getFillColor: rgb(HUB_TONE, m.hoverLit ? 0.03 : 0.14), getLineColor: rgb(HUB_TONE, m.hoverLit ? 0.25 : 0.95), lineWidthUnits: 'pixels', getLineWidth: 1.6,
        updateTriggers: { getFillColor: [Boolean(m.hoverLit)], getLineColor: [Boolean(m.hoverLit)], getRadius: [m.hubMax] },
      }));
    }

    // Chokepoints (diamonds): area ∝ TEU / week the plan carries through; grey when no leg crosses; red when closed.
    if (m.chokeData.length) {
      out.push(new IconLayer({
        ...LAYER_BASE, id: 'chokepoints', data: m.chokeData, getPosition: (d) => d.at, getIcon: () => DIAMOND_ICON, pickable: true,
        getSize: (d) => (d.teu > 0 ? 12 + 18 * Math.sqrt(d.teu / m.chokeMax) : 10), sizeUnits: 'pixels', billboard: true,
        getColor: (d) => (d.closed ? rgb('#ef4444', 0.95) : d.teu > 0 ? rgb('#f5b301', m.hoverLit ? 0.3 : 0.9) : rgb('#94a3b8', 0.55)),
        updateTriggers: { getColor: [Boolean(m.hoverLit)], getSize: [m.chokeMax] },
      }));
      out.push(new TextLayer({
        ...LAYER_BASE, id: 'chokepoint-labels', data: m.chokeLabels,
        getPosition: (d) => d.at, getText: (d) => (d.closed ? `${d.name} · CLOSED` : d.name), getSize: 10, sizeUnits: 'pixels', characterSet: 'auto',
        getPixelOffset: [0, 16], fontFamily: 'ui-monospace, Menlo, Consolas, monospace', fontWeight: 700,
        getColor: (d) => (d.closed ? [248, 113, 113, 255] : [245, 179, 1, m.hoverLit ? 80 : 230]), fontSettings: { sdf: true }, outlineWidth: 3,
        outlineColor: [3, 10, 20, 255], updateTriggers: { getColor: [Boolean(m.hoverLit)] },

      }));
    }

    // Live AIS: real vessels as heading arrows, above the plan, below the itinerary.
    if (m.aisData?.length) {
      out.push(new IconLayer({
        ...LAYER_BASE, id: 'ais', data: m.aisData, pickable: true, getPosition: (d) => [d.lon, d.lat], getIcon: () => VESSEL_ICON,
        getSize: (d) => (d.category === 'cargo' ? 13 : 10), sizeUnits: 'pixels', billboard: false,
        getAngle: (d) => 90 - (d.heading ?? 0), getColor: (d) => rgb(aisTone(d.category), d.sog_kn > 0.5 ? 0.95 : 0.55),
      }));
    }

    // Transit finder itinerary above the network: glow + ridden legs, then its ports with their role.
    if (m.itinLegs.length) {
      out.push(new PathLayer({ ...LAYER_BASE, id: 'itin-glow', data: m.itinLegs, getPath: (d) => d.path, getColor: (d) => rgb(d.color, 0.3), getWidth: 9, widthUnits: 'pixels', capRounded: true, jointRounded: true }));
      out.push(new PathLayer({ ...LAYER_BASE, id: 'itin-legs', data: m.itinLegs, getPath: (d) => d.path, pickable: true, getColor: (d) => rgb(d.color, 1), getWidth: 4, widthUnits: 'pixels', capRounded: true, jointRounded: true }));
      const key = m.itinPorts.filter((d) => d.role !== 'call');
      out.push(new ScatterplotLayer({
        ...LAYER_BASE, id: 'itin-ports', data: m.itinPorts, getPosition: (d) => d.coords, radiusUnits: 'pixels',
        getRadius: (d) => (d.role === 'call' ? 3 : 6), getFillColor: (d) => rgb(ITIN_PORT_TONE[d.role]),
        stroked: true, getLineColor: [255, 255, 255, 255], lineWidthUnits: 'pixels', getLineWidth: (d) => (d.role === 'call' ? 0.5 : 1.5),
      }));
      out.push(new TextLayer({
        ...LAYER_BASE, id: 'itin-labels', data: key, getPosition: (d) => d.coords,
        getText: (d) => `${d.code} · ${d.role}`, characterSet: 'auto', fontFamily: 'ui-monospace, Menlo, Consolas, monospace', fontWeight: 700,
        getSize: 11, sizeUnits: 'pixels', getColor: [226, 232, 240, 255], getPixelOffset: (d) => [0, d.role === 'destination' ? 22 : -22],
        background: true, getBackgroundColor: [5, 13, 24, 230], backgroundPadding: [5, 3], getBorderColor: (d) => rgb(ITIN_PORT_TONE[d.role], 0.8), getBorderWidth: 1,
      }));
    }

    if (m.inspected) {
      out.push(new ScatterplotLayer({
        ...LAYER_BASE, id: 'insp-ports', data: m.inspectedPorts, getPosition: (d) => d.coords, radiusUnits: 'pixels',
        getRadius: (d) => (d.origin || d.dest ? 5 : 4), getFillColor: (d) => rgb(d.origin ? '#10b981' : d.dest ? '#00d4ff' : '#94a3b8'),
        stroked: true, getLineColor: [255, 255, 255, 255], lineWidthUnits: 'pixels', getLineWidth: 1.5,
      }));
      out.push(new TextLayer({
        ...LAYER_BASE, id: 'insp-labels', data: m.inspectedPorts, getPosition: (d) => d.coords, getText: (d) => d.label,
        characterSet: 'auto', fontFamily: 'ui-monospace, Menlo, Consolas, monospace', fontWeight: 700, getSize: 11, sizeUnits: 'pixels',
        getColor: [226, 232, 240, 255], getPixelOffset: (d) => [0, d.origin ? -22 : 22], background: true, getBackgroundColor: [5, 13, 24, 230],
        backgroundPadding: [5, 3], getBorderColor: [0, 212, 255, 160], getBorderWidth: 1,
      }));
    } else if (m.showPorts) {
      const lit = (d) => m.hoverLit?.ports.has(d.code);
      out.push(new ScatterplotLayer({
        ...LAYER_BASE, id: 'port-halo', data: m.portDots.filter((d) => d.calls), getPosition: (d) => d.coords, radiusUnits: 'pixels',
        getRadius: (d) => d.r + 2.5, getFillColor: (d) => rgb(getRegionColor(d.region), 0.18 * dim(lit(d))), updateTriggers: { getFillColor: [m.hoverLit, m.itinLegs.length] },
      }));
      out.push(new ScatterplotLayer({
        ...LAYER_BASE, id: 'ports', data: m.portDots, getPosition: (d) => d.coords, radiusUnits: 'pixels', pickable: true,
        radiusMinPixels: 1.4, getRadius: (d) => d.r,
        getFillColor: (d) => (d.calls ? rgb(getRegionColor(d.region), 0.95 * dim(lit(d))) : rgb('#4b6478', 0.7 * dim(lit(d)))),
        updateTriggers: { getFillColor: [m.hoverLit, m.itinLegs.length] },
      }));
      if (m.openPort) {
        const p = m.portDots.find((d) => d.code === m.openPort);
        if (p) out.push(new ScatterplotLayer({ ...LAYER_BASE, id: 'open-port', data: [p], getPosition: (d) => d.coords, radiusUnits: 'pixels', getRadius: (d) => d.r + 5, stroked: true, filled: false, getLineColor: [248, 250, 252, 255], lineWidthUnits: 'pixels', getLineWidth: 1.6 }));
      }
      if (m.labelsOn) {
        out.push(new TextLayer({
          ...LAYER_BASE, id: 'labels', data: m.keyPortLabels, getPosition: (d) => d.coords, getText: (d) => `${d.id} ${d.n}`,
          fontFamily: 'ui-monospace, Menlo, Consolas, monospace', fontWeight: 700, getSize: 11, sizeUnits: 'pixels', getPixelOffset: [0, -12],
          getColor: (d) => [226, 232, 240, Math.round(255 * dim(m.hoverLit?.ports.has(d.id)))], fontSettings: { sdf: true }, outlineWidth: 3, outlineColor: [3, 10, 20, 255],
          updateTriggers: { getColor: [m.hoverLit, m.itinLegs.length] },
        }));
      }
    }

    // Vessels at the timeline clock.
    if (m.vesselsOn && m.fleets.length) {
      const boats = [];
      m.fleets.forEach((f) => {
        const { schedule } = f;
        for (let v = 0; v < f.vessels; v++) {
          const pos = positionAt(schedule, day + v * f.headway);
          const leg = f.legs[pos.leg];
          if (!leg) continue;
          const { p, heading } = pointAlong(leg.coords, leg.cum, pos.frac);
          const where = pos.atPort ? `${pos.waiting ? 'waiting at' : 'in port at'} ${pos.atPort}` : `sailing ${leg.from} → ${leg.to}`;
          boats.push({ p, heading, color: f.color, svc: String(f.svc.id), n: v + 1, of: f.vessels, where, cycle: schedule.cycleDays, cycleDay: ((day + v * f.headway) % schedule.cycleDays + schedule.cycleDays) % schedule.cycleDays, lit: !m.hoverLit || matchesHover(f.svc, hoverRef.current) });
        }
      });
      out.push(new ScatterplotLayer({ ...LAYER_BASE, id: 'vessel-halo', data: boats, getPosition: (d) => d.p, radiusUnits: 'pixels', getRadius: m.inspected ? 7 : 5, getFillColor: (d) => rgb('#f8fafc', d.lit ? 0.16 : 0.03) }));
      out.push(new IconLayer({
        ...LAYER_BASE, id: 'vessels', data: boats, getPosition: (d) => d.p, getIcon: () => VESSEL_ICON, getAngle: (d) => d.heading,
        getSize: m.inspected ? 14 : 11, sizeUnits: 'pixels', getColor: (d) => rgb(d.color, d.lit ? 1 : 0.15), pickable: true, billboard: true,
      }));
      if (m.inspected && dayRef.current && m.fleets[0]) {
        const f = m.fleets[0];
        const lead = positionAt(f.schedule, day);
        const legNow = f.legs[lead.leg];
        const where = lead.atPort ? `${lead.waiting ? 'waiting at' : 'in port'} ${lead.atPort}` : `${legNow.from} → ${legNow.to}`;
        dayRef.current.textContent = `day ${(((day % f.schedule.cycleDays) + f.schedule.cycleDays) % f.schedule.cycleDays).toFixed(1)} of ${f.schedule.cycleDays} · ${where}`;
      }
    }
    return out;
  }, []);
  const hoverRef = useRef(hover);
  hoverRef.current = hover;

  const paint = useCallback(() => {
    const ov = overlayRef.current;
    if (ov) ov.setProps({ layers: buildLayers(performance.now()) });
  }, [buildLayers]);

  // Repaint when the data changes, when the clock moves, and every frame while something animates.
  useEffect(() => { if (ready) paint(); });
  useEffect(() => subscribeTimeline(() => { if (modelRef.current.vesselsOn) paint(); }), [paint]);
  useEffect(() => {
    if (!ready || !(flowsOn || drawing)) return undefined;
    let raf = 0;
    const step = () => { paint(); raf = requestAnimationFrame(step); };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [ready, flowsOn, drawing, paint]);

  /* ── Layer panel ── */
  const routeStatusText = {
    loading: 'Sea lanes: loading…',
    searoute: 'Legs follow sea lanes (searoute · Eurostat maritime network; display only, not navigation)',
    mixed: 'Some legs follow sea lanes; the rest are great-circle paths',
    'great-circle': 'Sea lanes unavailable (backend offline): legs are great-circle paths',
  }[routeStatus] || null;
  const runAsOf = optimizationState?.source?.modifiedIso ? `run ${String(optimizationState.source.modifiedIso).slice(0, 16).replace('T', ' ')}` : 'run on screen';
  const layerGroups = [
    {
      id: 'plan', label: 'Plan',
      items: LAYER_DEFS.filter((d) => d.group === 'Plan').map((d) => ({
        id: d.id, label: d.label, hint: d.hint, on: lay[d.id], onToggle: () => toggleMapLayer(d.id),
        asOf: d.id === 'routes' ? (routeStatus === 'searoute' ? 'searoute 1.6' : routeStatus === 'loading' ? '…' : 'great-circle') : d.id === 'vessels' ? 'leg schedule' : runAsOf,
        note: d.id === 'flows' && motion !== 'full' ? ' · needs full motion' : d.id === 'vessels' ? ` · ${vesselCount}` : d.id === 'hubs' ? (transship.model ? ` · ${transship.model.totals.hubs}` : ' · no routed flows for this plan') : null,
        disabled: d.id === 'flows' && motion !== 'full',
      })),
    },
    {
      id: 'risk', label: 'Risk',
      items: diff ? [] : LAYER_DEFS.filter((d) => d.group === 'Risk').map((d) => ({
        id: d.id, label: d.label, hint: d.hint, on: lay[d.id], onToggle: () => toggleMapLayer(d.id),
        ...(d.id === 'warrisk' ? {
          asOf: war.data ? `JWC ${war.data.circular.id} · ${war.data.circular.date}` : war.status === 'loading' ? '…' : 'JWC',
          note: war.status === 'unavailable' ? ' · needs the backend' : null,
        } : d.id === 'piracy' ? {
          asOf: piracy.data?.status && piracy.data.status !== 'unavailable' ? `ASAM ${String(piracy.data.fetched_on || '').slice(0, 10)} · ${piracy.data.incidents.length}` : piracy.status === 'loading' ? '…' : 'NGA ASAM',
          note: piracy.data?.status === 'unavailable' ? ' · NGA service down, retried daily' : piracy.status === 'unavailable' ? ' · needs the backend' : null,
        } : {
          asOf: portwatch.data?.chokepoints ? `PortWatch ${Object.values(portwatch.data.chokepoints)[0]?.data_through || ''}` : portwatch.status === 'loading' && chokeOn ? '…' : 'PortWatch',
          note: exposure.status === 'unavailable' && chokeOn ? ' · exposure needs the backend' : null,
        }),
      })),
    },
    {
      id: 'live', label: 'Live',
      items: diff ? [] : LAYER_DEFS.filter((d) => d.group === 'Live').map((d) => ({
        id: d.id, label: d.label, hint: d.hint, on: lay[d.id], onToggle: () => toggleMapLayer(d.id),
        asOf: ais.data ? `AIS ${String(ais.data.data_updated || '').slice(11, 16)} UTC · ${ais.data.vessels.length}` : ais.status === 'loading' ? '…' : 'Digitraffic',
        note: ais.status === 'unavailable' ? ' · AIS feed unavailable' : null,
      })),
    },
    {
      id: 'weather', label: 'Weather',
      items: diff ? [] : LAYER_DEFS.filter((d) => d.group === 'Weather').map((d) => ({
        id: d.id, label: d.label, hint: d.hint, on: lay[d.id], onToggle: () => toggleMapLayer(d.id),
        asOf: sea.data ? `Open-Meteo ${String(sea.data.fetched_on || '').slice(5, 16)} · ${sea.data.forecast_days} d` : sea.status === 'loading' ? 'fetching…' : 'Open-Meteo',
        note: sea.status === 'unavailable' ? ' · needs the backend' : sea.status === 'error' ? ' · forecast unavailable' : null,
      })),
    },
    {
      id: 'regulation', label: 'Regulation',
      items: LAYER_DEFS.filter((d) => d.group === 'Regulation').map((d) => ({
        id: d.id, label: d.label, hint: d.hint, on: lay[d.id], onToggle: () => toggleMapLayer(d.id),
        asOf: eca.data ? `Marine Regions ${eca.data.retrieved || ''}` : eca.status === 'loading' ? '…' : 'Marine Regions',
        note: eca.status === 'unavailable' ? ' · needs the backend' : null,
      })),
    },
    {
      id: 'demand', label: 'Demand',
      items: unserved?.hasDemand ? [{ id: 'unserved', label: `Unserved demand · ${fmtNum(unserved.totals.unserved)} TEU/wk`, hint: 'Toggled from the panel header above the map', on: true, disabled: true, asOf: 'dataset demand' }] : [],
    },
  ];
  const basemapControl = {
    name: drawKey || 'map', value: mapPrefs.basemap, onChange: (k) => setMapPrefs({ basemap: k }),
    options: Object.entries(BASEMAPS).map(([key, b]) => ({ key, label: b.label, asOf: b.asOf })),
  };

  const isGlobe = mapPrefs.projection === 'globe';
  const voyageTiming = schedules[0]?.schedule?.source || null;
  const showTimeline = vesselsOn && fleets.length > 0;

  return (
    <div className={`wm-root gl-root relative w-full h-full min-h-[360px] bg-[#030a14] overflow-hidden select-none font-mono ${showTimeline ? 'has-timeline' : ''}`}>
      {/* Inline position: maplibre-gl.css sets .maplibregl-map { position: relative } on this element. */}
      <div ref={containerRef} className="z-0 gl-canvas" style={{ position: 'absolute', inset: 0 }} aria-label="World map of the plan" role="region" />

      {inspectedService && (
        <div className="gl-insp absolute left-3 z-20 flex items-center gap-2 flex-wrap p-1.5 px-3 rounded bg-black/85 backdrop-blur-md border border-cyan-500/50 shadow-xl">
          <span className="w-2 h-2 rounded-full bg-cyan-400" />
          <span className="text-[12px] font-bold text-white uppercase tracking-wider">
            SERVICE INSPECTION: <span className="text-cyan-400">{inspectedService.id}</span>
          </span>
          <span className="text-[12px] px-1.5 py-0.5 rounded uppercase font-bold" style={{ background: `${getRegionColor(inspectedService.region)}25`, color: getRegionColor(inspectedService.region) }}>
            {inspectedService.region}
          </span>
          {Number(inspectedService.cycle_time_days) > 0 && vesselsOn && (
            <span className="wm-voyage" title={`Vessel markers sail the loop on the timeline clock at its real ${inspectedService.cycle_time_days}-day cycle time. ${voyageTiming === 'run'
              ? "Sail days per leg and port stays are the run's own (ledger) figures; slack between them and the whole-day cycle is spent waiting at the first port."
              : 'Estimated timing: this run has no per-leg times, so sea time (cycle minus a 24 h stay per call) is split by leg distance.'} ${inspectedService.vessels || 1} vessel(s), one departure every ${(7 / (Number(inspectedService.frequency_per_week) || 1)).toFixed(0)} days.`}>
              <span ref={dayRef}>day 0.0 of {inspectedService.cycle_time_days}</span>
              <span className="wm-voyage-scale">· {voyageTiming === 'run' ? 'run leg times' : 'estimated leg times'}</span>
            </span>
          )}
          {onClearService && (
            <button type="button" onClick={onClearService} className="ml-2 text-[12px] px-2 py-0.5 rounded bg-white/10 hover:bg-white/20 text-slate-200 uppercase font-semibold transition-colors">
              ✕ BACK TO REGION
            </button>
          )}
        </div>
      )}

      <div className="wm-zoom" role="group" aria-label="Map view">
        <LayerPanel groups={layerGroups} basemap={basemapControl} status={routeStatusText} />
        <button type="button" onClick={() => zoomBy(1)} aria-label="Zoom in" title="Zoom in">+</button>
        <button type="button" onClick={() => zoomBy(-1)} aria-label="Zoom out" title="Zoom out" disabled={zoomInfo.zoom <= zoomInfo.min + 0.01}>−</button>
        <button type="button" onClick={() => fitCamera(true)} aria-label="Fit the map to the ports shown" title="Drag to pan · Ctrl + scroll to zoom">Fit</button>
        <button type="button" onClick={() => setMapPrefs({ projection: isGlobe ? 'mercator' : 'globe' })} aria-pressed={isGlobe}
          className={isGlobe ? 'is-on' : ''} title={isGlobe ? 'Switch to the flat map' : 'Switch to the globe'}>{isGlobe ? '2D' : 'Globe'}</button>
        <button type="button" onClick={() => setMapPrefs({ engine: 'svg' })} title="Use the classic SVG map (no WebGL)" aria-label="Use the classic SVG map">SVG</button>
      </div>

      {routeStatus !== 'searoute' && routeStatus !== 'loading' && hasLegs && (
        <div className="gl-chip" role="status">{routeStatus === 'mixed' ? 'Some legs: great-circle (no sea lane)' : 'Great-circle paths · sea lanes need the backend'}</div>
      )}

      {selectedCorridor && !inspectedService && (
        <div className="absolute top-12 left-6 z-20 p-3 rounded-lg bg-black/90 border border-cyan-500/50 backdrop-blur-md min-w-[230px] text-left font-mono shadow-2xl">
          <div className="flex justify-between items-center pb-1.5 border-b border-white/10 mb-2">
            <span className="text-[12px] text-cyan-400 font-bold uppercase tracking-widest">SERVICE CORRIDOR</span>
            <button type="button" onClick={() => setSelectedCorridor(null)} className="text-slate-400 hover:text-white text-xs px-1" aria-label="Close">✕</button>
          </div>
          <div className="text-sm font-bold text-white mb-2 tracking-wide">{selectedCorridor.from} → {selectedCorridor.to}</div>
          <div className="space-y-1 text-[12px]">
            <div className="flex justify-between"><span className="text-slate-400">SERVICES:</span><span className="text-slate-100 font-bold">{selectedCorridor.service_count}</span></div>
            <div className="flex justify-between"><span className="text-slate-400">TOTAL LOAD:</span><span className="text-emerald-400 font-bold">{fmtNum(selectedCorridor.total_load)} TEU</span></div>
            <div className="flex justify-between"><span className="text-slate-400">AVG LOAD:</span><span className="text-slate-200">{fmtNum(selectedCorridor.avg_load)} TEU</span></div>
            <div className="flex justify-between"><span className="text-slate-400">REGIONS:</span><span className="text-cyan-400">{selectedCorridor.regions.join(', ') || '—'}</span></div>
            {selectedCorridor.route?.source === 'searoute' && (
              <>
                <div className="flex justify-between"><span className="text-slate-400">SEA LANE:</span><span className="text-slate-200">{nm(selectedCorridor.route.nm)}</span></div>
                <div className="flex justify-between"><span className="text-slate-400">MODEL (LINERLIB):</span><span className="text-slate-200">{nm(selectedCorridor.route.model_nm)}</span></div>
                <div className="flex justify-between gap-2"><span className="text-slate-400">VIA:</span><span className="text-slate-200 text-right">{selectedCorridor.route.passages.map(passageName).join(', ') || 'open sea'}</span></div>
              </>
            )}
          </div>
        </div>
      )}

      {clickedPort && (() => {
        const c = loc(clickedPort);
        return (
          <div className="absolute top-12 right-3 z-20 p-2.5 rounded-lg bg-black/90 border border-emerald-500/50 backdrop-blur-md min-w-[180px] text-left font-mono">
            <div className="flex justify-between items-center pb-1 border-b border-white/10 mb-1.5">
              <span className="text-[12px] text-emerald-400 font-bold uppercase tracking-wider">PORT {clickedPort}</span>
              <button type="button" onClick={() => setClickedPort(null)} className="text-slate-400 hover:text-white text-xs" aria-label="Close">✕</button>
            </div>
            <div className="text-[12px] text-slate-200 font-semibold">{getPortName(clickedPort)}</div>
            <div className="text-[12px] text-slate-300 mt-0.5">Region: <span className="text-cyan-400 font-semibold">{portGeoRegion(clickedPort) || 'unknown'}</span></div>
            <div className="text-[12px] text-slate-300 mt-0.5">Calls in plan: <span className="text-slate-100 font-semibold">{callCount.get(clickedPort) || 0}</span></div>
            <div className="text-[12px] text-slate-300 mt-0.5">Lon, lat: <span className="text-slate-400">{c ? `${c[0].toFixed(2)}, ${c[1].toFixed(2)}` : 'not in ports.csv'}</span></div>
          </div>
        );
      })()}

      <div className="gl-legend absolute left-3 z-10 p-2.5 rounded bg-black/80 backdrop-blur-md border border-white/10 min-w-[210px] max-w-[260px] pointer-events-auto">
        <button type="button" className={`w-full flex justify-between items-center gap-3 text-left ${legendOpen ? 'mb-1.5 pb-1 border-b border-white/10' : ''}`}
          onClick={() => setLegendOpen((v) => !v)} aria-expanded={legendOpen} title={legendOpen ? 'Fold the legend' : 'Show the legend'}>
          <span className="text-[12px] text-slate-400 font-mono tracking-widest uppercase font-bold"><span aria-hidden="true">{legendOpen ? '▾' : '▸'}</span> LEGEND</span>
          <span className="text-[12px] font-mono text-emerald-400 font-bold">{inspectedService ? 'ONE SERVICE' : `${services.length} SERVICES`}</span>
        </button>
        {!legendOpen ? null : inspectedService ? (
          <div className="space-y-1 text-[12px]">
            <div className="flex justify-between gap-3"><span className="text-slate-400">SERVICE</span><span className="text-cyan-400 font-bold">{inspectedService.id}</span></div>
            <div className="flex justify-between gap-3"><span className="text-slate-400">CALLS</span><span className="text-slate-100 font-semibold">{(inspectedService.ports || []).length}</span></div>
            <div className="flex justify-between gap-3"><span className="text-slate-400">VESSEL</span><span className="text-slate-200">{inspectedService.vessel_class || '—'}</span></div>
            <div className="flex justify-between gap-3"><span className="text-slate-400">LOAD</span><span className="text-emerald-400 font-bold">{fmtNum(inspectedService.load)} TEU</span></div>
            <div className="flex justify-between gap-3"><span className="text-slate-400">P&amp;L / WK</span><span className={`font-bold ${Number(inspectedService.weekly_profit) < 0 ? 'text-red-400' : 'text-emerald-300'}`}>{fmtUsd(inspectedService.weekly_profit)}</span></div>
            <div className="flex items-center gap-2 pt-1"><svg width="28" height="8" aria-hidden="true"><line x1="1" y1="4" x2="27" y2="4" stroke="#94a3b8" strokeOpacity="0.6" strokeWidth="1.2" strokeDasharray="3 3" /></svg><span className="text-slate-300">Return leg (loop)</span></div>
          </div>
        ) : (
          <>
            {disruption && (
              <div className="mb-1.5 pb-1.5 border-b border-white/10 space-y-1">
                <div className="flex items-center gap-2"><svg width="28" height="8" aria-hidden="true"><line x1="1" y1="4" x2="27" y2="4" stroke={VIZ_2} strokeWidth="2.4" strokeLinecap="round" /></svg><span className="text-[12px] text-slate-300">Leg on a detour ({disruption.rerouted.size})</span></div>
                <div className="flex items-center gap-2"><svg width="28" height="8" aria-hidden="true"><line x1="1" y1="4" x2="27" y2="4" stroke={VIZ_MUTED} strokeWidth="2.4" strokeDasharray="5 3" /></svg><span className="text-[12px] text-slate-300">Suspended service ({disruption.suspended.size})</span></div>
              </div>
            )}
            {lay.ais && ais.data && !diff && (
              <div className="mb-1.5 space-y-0.5">
                <div className="text-[11px] text-slate-400">Live AIS · {ais.data.coverage}</div>
                {AIS_CATEGORIES.map(([k, label, tone]) => (
                  <div key={k} className="flex items-center gap-2"><svg width="28" height="10" aria-hidden="true"><path d="M20 5 8 1l3 4-3 4z" fill={tone} /></svg><span className="text-[12px] text-slate-300">{label} ({k === 'other' ? Object.entries(ais.data.counts).filter(([c]) => !['cargo', 'tanker', 'passenger'].includes(c)).reduce((a, [, c]) => a + c, 0) : ais.data.counts[k] ?? 0})</span></div>
                ))}
              </div>
            )}
            {lay.seastate && sea.data && !diff && (
              <div className="mb-1.5 space-y-0.5">
                <div className="text-[11px] text-slate-400">Worst forecast sea, next {sea.data.forecast_days} days</div>
                {SEA_RISKS.map(([k, label, tone]) => (
                  <div key={k} className="flex items-center gap-2"><svg width="28" height="12" aria-hidden="true"><circle cx="14" cy="6" r={k === 'low' ? 3 : k === 'moderate' ? 4 : k === 'high' ? 5 : 6} fill={tone} /></svg><span className="text-[12px] text-slate-300">{label}</span></div>
                ))}
              </div>
            )}
            {lay.currents && sea.data && !diff && (
              <div className="flex items-center gap-2 mb-1.5"><svg width="28" height="10" aria-hidden="true"><path d="M20 5 8 1l3 4-3 4z" fill={CURRENT_TONE} /></svg><span className="text-[12px] text-slate-300">Mean current ≥ 0.3 kn · size = speed</span></div>
            )}
            {lay.eca && eca.data && (
              <div className="flex items-center gap-2 mb-1.5"><svg width="28" height="14" aria-hidden="true"><rect x="2" y="2" width="24" height="10" fill={ECA_TONE} fillOpacity="0.15" stroke={ECA_TONE} strokeWidth="1.2" /></svg><span className="text-[12px] text-slate-300">SOx emission control area (0.10% S)</span></div>
            )}
            {lay.warrisk && war.data && !diff && (
              <div className="flex items-center gap-2 mb-1.5"><svg width="28" height="14" aria-hidden="true"><rect x="2" y="2" width="24" height="10" fill={WAR_TONE} fillOpacity="0.15" stroke={WAR_TONE} strokeWidth="1.2" /></svg><span className="text-[12px] text-slate-300">JWC war-risk listed area</span></div>
            )}
            {lay.piracy && piracy.data?.incidents?.length > 0 && !diff && (
              <div className="flex items-center gap-2 mb-1.5"><svg width="28" height="10" aria-hidden="true"><circle cx="14" cy="5" r="4" fill={PIRACY_TONE} stroke="#0f172a" /></svg><span className="text-[12px] text-slate-300">Piracy / hostile act, last 12 months ({piracy.data.incidents.length})</span></div>
            )}
            {chokeData.length > 0 && (
              <div className="flex items-center gap-2 mb-1.5"><svg width="28" height="14" aria-hidden="true"><path d="M14 1 21 7 14 13 7 7z" fill="#f5b301" fillOpacity="0.35" stroke="#f5b301" strokeWidth="1.4" /></svg><span className="text-[12px] text-slate-300">Chokepoint · size = plan TEU through it</span></div>
            )}
            {diff && (
              <div className="mb-1.5 pb-1.5 border-b border-white/10 space-y-1">
                {[['added', 'Only in run B'], ['removed', 'Only in run A (dashed)'], ['kept', 'In both runs']]
                  .filter(([k2]) => !diffSide || k2 === 'kept' || (diffSide === 'A' ? k2 === 'removed' : k2 === 'added')).map(([k2, label]) => (
                  <div key={k2} className="flex items-center gap-2">
                    <svg width="28" height="8" aria-hidden="true"><line x1="1" y1="4" x2="27" y2="4" stroke={DIFF_TONE[k2]} strokeWidth="2.4" strokeLinecap="round" strokeDasharray={k2 === 'removed' ? '5 3' : undefined} /></svg>
                    <span className="text-[12px] text-slate-300">{label}</span>
                  </div>
                ))}
              </div>
            )}
            {hubData.length > 0 && (
              <div className="mb-1.5 pb-1.5 border-b border-white/10">
                <div className="flex items-center gap-2">
                  <svg width="28" height="14" aria-hidden="true"><circle cx="14" cy="7" r="6" fill={HUB_TONE} fillOpacity="0.14" stroke={HUB_TONE} strokeWidth="1.6" /></svg>
                  <span className="text-[12px] text-slate-300">Transshipment hub (area = TEU changing ship) · max {fmtNum(Math.round(hubMax))}</span>
                </div>
                {transship.model?.totals.cost != null && <div className="text-[12px] text-slate-400 mt-1">{fmtNum(Math.round(transship.model.totals.transferTeu))} TEU/week transshipped · {fmtUsd(transship.model.totals.cost)}/week</div>}
              </div>
            )}
            {unservedRings.length > 0 && (
              <div className="mb-1.5 pb-1.5 border-b border-white/10">
                <div className="flex items-center gap-2 mb-1">
                  <svg width="28" height="14" aria-hidden="true"><circle cx="14" cy="7" r="6" fill={VIZ_2} fillOpacity="0.1" stroke={VIZ_2} strokeWidth="1.4" /></svg>
                  <span className="text-[12px] text-slate-300">Unserved TEU at port (area) · max {fmtNum(unservedMax)}</span>
                </div>
                <div className="flex items-center gap-2">
                  <svg width="28" height="8" aria-hidden="true"><line x1="1" y1="4" x2="27" y2="4" stroke={VIZ_2} strokeWidth="2" strokeDasharray="4 3" /></svg>
                  <span className="text-[12px] text-slate-300">Top {unservedLanes.length} unserved lanes (great circle)</span>
                </div>
                <div className="text-[12px] text-slate-400 mt-1">{fmtNum(unserved.totals.unserved)} of {fmtNum(unserved.totals.demand)} TEU/week not carried</div>
              </div>
            )}
            <div className="text-[12px] text-slate-400 mb-1">Line width = TEU on the leg</div>
            {[1, 0.25, 0.04].map((f) => (
              <div key={f} className="flex items-center gap-2 mb-1">
                <svg width="28" height="8" aria-hidden="true"><line x1="1" y1="4" x2="27" y2="4" stroke="#cbd5e1" strokeWidth={legWidth(f * maxLegLoad, maxLegLoad)} strokeLinecap="round" /></svg>
                <span className="text-[12px] text-slate-300">{maxLegLoad > 0 ? `${fmtNum(Math.round(f * maxLegLoad))} TEU` : '—'}</span>
              </div>
            ))}
            {!diff && (
              <>
                <div className="flex items-center gap-2 mt-1.5 mb-1"><span className="w-4 h-[3px] bg-amber-400 rounded" aria-hidden="true" /><span className="text-[12px] text-amber-300">Leg between two regions</span></div>
                <div className="flex items-center gap-2 mb-1.5"><span className="w-4 h-[3px] rounded" style={{ background: 'linear-gradient(90deg,#10b981,#7c3aed,#00d4ff)' }} aria-hidden="true" /><span className="text-[12px] text-slate-300">Leg within a region (region colour)</span></div>
              </>
            )}
            <div className="text-[12px] text-slate-400 mb-1">Dot size = port calls · grey = not called</div>
            {vesselsOn && fleets.length > 0 && (
              <div className="flex items-center gap-2 mb-1.5">
                <svg width="28" height="10" aria-hidden="true"><path d="M20 5 10 1l2 4-2 4z" fill="#e2e8f0" /></svg>
                <span className="text-[12px] text-slate-300">Vessel at the clock (region colour)</span>
              </div>
            )}
            {topCorridors.length > 0 && (
              <>
                <div className="text-[12px] text-slate-400 font-mono uppercase tracking-wider mb-1">BUSIEST LEGS</div>
                {topCorridors.map((c, i) => (
                  <div key={i} className="flex items-center gap-1.5 text-[12px] text-slate-300 py-0.5">
                    <span className="font-semibold">{c.from}→{c.to}</span>
                    <span className="text-cyan-300 ml-auto">{fmtNum(c.total_load)} TEU</span>
                  </div>
                ))}
              </>
            )}
          </>
        )}
      </div>

      {showTimeline && (
        <TimelineBar summary={inspectedService ? `${fleets[0]?.vessels || 0} vessel${fleets[0]?.vessels === 1 ? '' : 's'} · ${inspectedService.id}` : `${vesselCount} vessels on ${fleets.length} services`} />
      )}
    </div>
  );
}
