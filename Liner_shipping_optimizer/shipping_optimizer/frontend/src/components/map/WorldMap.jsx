/**
 * WorldMap — basemap, ports and the plan's routes (react-simple-maps on one equirectangular projection).
 *
 * Motion (2026-10-24 round, all gated by the viewer's motion setting):
 * - Routes draw on, busiest leg first, the first time a run's plan is shown on a map surface (≈0.5 s, `drawKey`).
 * - Region picks, Fit, zoom buttons and port picks glide (300 ms) instead of jumping.
 * - In single-service inspection, vessel markers sail the service loop at its real cycle time, scaled
 *   1 s = 1 day. Runs that record per-leg times (utils/legTimes.js) use the ledger's sail days and port stays;
 *   older runs split the sea time by leg distance, and the chip says the timing is estimated.
 * - Hovering a service or agent anywhere (focusStore hover link) lights up its routes and dims the rest.
 *
 * Layers added 2026-10-24: `unserved` (portFlows.portActivity result) rings each port by the TEU it could
 * not ship or receive and draws the largest unserved lanes dashed; `diff` (service id → added / removed /
 * kept) tones the legs for the run diff; `onPortOpen` hands a port click to the page (port drawer).
 */
import React, { useState, useCallback, useMemo, useEffect, useLayoutEffect, useRef } from "react";
import { ComposableMap, Geographies, Geography, Marker, Line, ZoomableGroup } from "react-simple-maps";
import { geoEquirectangular, geoPath } from "d3-geo";
import { getPortName, getPortCoordinates } from '../../utils/portLookup.js';
import { activeDatasetPorts, portRegistryVersion } from '../../utils/portRegistry.js';
import { fmtNum, fmtUsd } from '../../utils/formatters.js';
import { portGeoRegion } from '../../utils/geoRegion.js';
import { useAgentFocus, matchesAgent, useHoverTarget, matchesHover } from '../../services/focusStore.js';
import { useMotionLevel } from '../../services/prefsStore.js';
import { tween, MS } from '../../utils/motion.js';
import { legScheduleOf, positionAt } from '../../utils/legTimes.js';

// Validated chart pair (index.css --viz-1 / --viz-2) and the muted tone, for the layers drawn in SVG attributes.
const VIZ_1 = '#3987e5';
const VIZ_2 = '#d95926';
const VIZ_MUTED = '#5b6b7a';
const UNSERVED_LANES_SHOWN = 12;
const DIFF_TONE = { added: VIZ_1, removed: VIZ_2, kept: VIZ_MUTED };

const geoUrl = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

// One projection for the basemap, markers and the hand-drawn arcs (ComposableMap uses this instance).
const W = 900;
const H = 400;
const projection = geoEquirectangular()
  .scale(145)
  .center([15, 12])
  .translate([W / 2, H / 2]);
const WORLD_VIEW = { center: [15, 12], zoom: 1 };
const MAX_ZOOM = 14;

export function getRegionColor(regionId) {
  const r = String(regionId || '').toLowerCase().trim();
  if (r.includes('americ')) return '#10b981'; // Emerald
  if (r.includes('europ')) return '#7c3aed';  // Purple
  if (r.includes('middl') || r.includes('east')) return '#f59e0b'; // Amber
  if (r.includes('asia') || r.includes('pacif')) return '#00d4ff'; // Cyan
  if (r.includes('afric')) return '#ef4444';  // Red
  return '#94a3b8';
}

/**
 * Curved-arc interpolation in projected SVG screen coordinates:
 * returns an SVG path that arcs north between two projected points [x1, y1] and [x2, y2].
 */
function arcPath(p1, p2, curvature = 0.15) {
  const [x1, y1] = p1;
  const [x2, y2] = p2;
  const dx = x2 - x1;
  const dy = y2 - y1;
  const dist = Math.sqrt(dx * dx + dy * dy);
  if (!Number.isFinite(dist) || dist < 0.05) return `M ${x1} ${y1} L ${x2} ${y2}`;

  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  const nx = -dy / dist;
  const ny = dx / dist;

  // Arc towards upper half of map (north bow)
  const bow = curvature * dist * (y1 > y2 ? -1 : 1);
  const cx = mx + nx * bow;
  const cy = my + ny * bow;

  return `M ${x1.toFixed(2)} ${y1.toFixed(2)} Q ${cx.toFixed(2)} ${cy.toFixed(2)} ${x2.toFixed(2)} ${y2.toFixed(2)}`;
}

/** Center and zoom that fit a set of [lon, lat] points into the map frame (padLeft keeps them clear of the legend). */
function fitView(points, padLeft = 36) {
  const xy = points.map((p) => projection(p)).filter((p) => p && Number.isFinite(p[0]) && Number.isFinite(p[1]));
  if (!xy.length) return WORLD_VIEW;
  const xs = xy.map((p) => p[0]);
  const ys = xy.map((p) => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const pad = 36;
  const zoom = Math.min(MAX_ZOOM, (W - pad - padLeft) / Math.max(x1 - x0, 1), (H - 2 * pad) / Math.max(y1 - y0, 1));
  if (zoom <= 1.15) return WORLD_VIEW;
  // Shift the center left by half the extra left padding (in map units at this zoom), so points clear the legend.
  const shift = (padLeft - pad) / 2 / zoom;
  return {
    center: projection.invert([(x0 + x1) / 2 - shift, (y0 + y1) / 2]),
    zoom: Math.round(zoom * 100) / 100,
  };
}

// Route width: square-root scale of the leg's TEU against the busiest leg on screen.
const legWidth = (load, maxLoad) => (maxLoad > 0 ? 0.8 + 3.4 * Math.sqrt(Math.max(load, 0) / maxLoad) : 1.2);

// Route draw-on: once per (run, map surface). Each leg draws in 200 ms; starts spread over 300 ms by rank.
const drawnKeys = new Set();
const DRAW_SPREAD_MS = 300;
const DRAW_TOTAL_MS = DRAW_SPREAD_MS + MS[200] + 100;
const PORT_ZOOM = 4;          // zoom a picked port glides to (at least)
const DAYS_PER_SECOND = 1;    // vessel animation scale: one second of screen time = one day at sea
const geoPathOf = geoPath(projection);

// Basemap drawn once: the stroke stays one pixel at any zoom (non-scaling), so it never re-renders on zoom.
const BASEMAP = (
  <Geographies geography={geoUrl}>
    {({ geographies }) =>
      geographies.map((geo) => (
        <Geography
          key={geo.rsmKey}
          geography={geo}
          fill="#11253a"
          stroke="#21405e"
          strokeWidth={0.5}
          vectorEffect="non-scaling-stroke"
          style={{
            default: { outline: "none" },
            hover: { fill: "#152c44", outline: "none" },
            pressed: { outline: "none" },
          }}
        />
      ))
    }
  </Geographies>
);

/**
 * Vessels of one inspected service sailing its loop. Leg paths are the same curves the map draws, plus the
 * closing leg back to the first port. Positions are written straight to the DOM each frame (no re-render).
 */
function ServiceVessels({ service, k, motion, paused, dayRef }) {
  const schedule = useMemo(() => legScheduleOf(service, getPortCoordinates), [service]);
  // One drawable path per schedule leg (same index); a leg without coordinates keeps a null path.
  const legs = useMemo(() => (schedule?.legs || []).map((l, i, all) => {
    const a = getPortCoordinates(l.from); const b = getPortCoordinates(l.to);
    if (!a || !b || l.from === l.to) return { ...l, d: null };
    const transPacific = Math.abs(a[0] - b[0]) > 160;
    const d = transPacific ? geoPathOf({ type: 'LineString', coordinates: [a, b] }) : arcPath(projection(a), projection(b), 0.16);
    return { ...l, d, closing: i === all.length - 1 };
  }), [schedule]);
  const cycleDays = schedule?.cycleDays || null;
  const vessels = Math.max(1, Math.min(12, Number(service.vessels) || 1));
  const headwayDays = 7 / (Number(service.frequency_per_week) || 1);
  const pathRefs = useRef([]);
  const boatRefs = useRef([]);
  const kRef = useRef(k);
  kRef.current = k;
  const elapsed = useRef(0);   // screen seconds sailed so far (kept across pause and zoom)

  useEffect(() => {
    if (!legs.some((l) => l.d) || !cycleDays) return undefined;
    const lens = legs.map((_, i) => pathRefs.current[i]?.getTotalLength?.() || 0);
    const place = (secs) => {
      for (let v = 0; v < vessels; v++) {
        const { leg: li, frac } = positionAt(schedule, (secs * DAYS_PER_SECOND) + v * headwayDays);
        const path = pathRefs.current[li]; const boat = boatRefs.current[v];
        if (!path || !boat || !lens[li]) continue;
        const at = Math.min(lens[li], frac * lens[li]);
        const back = at >= lens[li] - 0.6;   // at a port: take the heading from the end of the leg
        const p = path.getPointAtLength(at);
        const q = path.getPointAtLength(back ? Math.max(0, at - 0.6) : at + 0.6);
        const ang = ((back ? Math.atan2(p.y - q.y, p.x - q.x) : Math.atan2(q.y - p.y, q.x - p.x)) * 180) / Math.PI;
        boat.setAttribute('transform', `translate(${p.x} ${p.y}) rotate(${Number.isFinite(ang) ? ang : 0}) scale(${1 / (kRef.current || 1)})`);
      }
      if (dayRef.current) {
        const day = (secs * DAYS_PER_SECOND) % cycleDays;
        const lead = positionAt(schedule, secs * DAYS_PER_SECOND);
        const where = lead.atPort ? `${lead.waiting ? 'waiting at' : 'in port'} ${lead.atPort}` : `${legs[lead.leg].from} → ${legs[lead.leg].to}`;
        dayRef.current.textContent = `day ${day.toFixed(1)} of ${cycleDays} · ${where}`;
      }
    };
    if (motion !== 'full' || paused) { place(elapsed.current); return undefined; }
    let raf = 0; let last = performance.now();
    const step = (now) => {
      elapsed.current += (now - last) / 1000; last = now;
      place(elapsed.current);
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [legs, schedule, cycleDays, vessels, headwayDays, motion, paused, k, dayRef]);

  if (!legs.some((l) => l.d) || !cycleDays) return null;
  return (
    <>
      {legs.filter((l) => l.closing && l.d).map((l) => (
        <path key="closing" d={l.d} fill="none" stroke="#94a3b8" strokeOpacity={0.45} strokeWidth={1.2 / (k || 1)} strokeDasharray={`${3 / (k || 1)} ${3 / (k || 1)}`}>
          <title>Return leg {l.from} → {l.to}: the service is a loop</title>
        </path>
      ))}
      {legs.map((l, i) => (l.d ? <path key={`vp${i}`} ref={(el) => { pathRefs.current[i] = el; }} d={l.d} fill="none" stroke="none" /> : null))}
      {Array.from({ length: vessels }, (_, v) => (
        <g key={`boat${v}`} ref={(el) => { boatRefs.current[v] = el; }} className="wm-vessel" style={{ pointerEvents: 'none' }}>
          <circle r={7} fill="#f8fafc" fillOpacity={0.16} />
          <path d="M 6 0 L -4 -3.6 L -2 0 L -4 3.6 Z" fill="#f8fafc" stroke="#030a14" strokeWidth={0.8} />
        </g>
      ))}
    </>
  );
}

export default function WorldMap({
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
}) {
  const [selectedCorridor, setSelectedCorridor] = useState(null);
  const [clickedPort, setClickedPort] = useState(null);
  // Legend starts folded on narrow screens, where it would cover most of the map.
  const [legendOpen, setLegendOpen] = useState(() => typeof window === 'undefined' || window.innerWidth >= 768);
  const [view, setView] = useState(WORLD_VIEW);
  const [liveZoom, setLiveZoom] = useState(1);
  const [agentFocus] = useAgentFocus();
  const hover = useHoverTarget();
  const motion = useMotionLevel();
  const registryVersion = portRegistryVersion();

  // All available selected services
  const allServices = useMemo(() => {
    if (Array.isArray(propSelectedServices) && propSelectedServices.length > 0) {
      return propSelectedServices;
    }
    return (optimizationState?.global?.selected_services) || [];
  }, [propSelectedServices, optimizationState?.global?.selected_services]);

  // Normalized region matching helper
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

  // Services on screen: the inspected one, else the region- and agent-filtered selection.
  const services = useMemo(() => {
    if (inspectedService) return [inspectedService];
    return allServices.filter((s) => matchesRegion(s.region, regionFilter) && matchesAgent(s, agentFocus));
  }, [allServices, inspectedService, regionFilter, matchesRegion, agentFocus]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const loc = useCallback((portId) => getPortCoordinates(portId), [registryVersion]);

  // Port calls by the services on screen.
  const callCount = useMemo(() => {
    const m = new Map();
    services.forEach((svc) => (svc.ports || []).forEach((p) => m.set(p, (m.get(p) || 0) + 1)));
    return m;
  }, [services]);
  const maxCalls = useMemo(() => Math.max(1, ...callCount.values()), [callCount]);

  /* ── SINGLE SERVICE MODE DATA ── */
  const singleServiceLegs = useMemo(() => {
    if (!inspectedService || !inspectedService.ports || inspectedService.ports.length < 2) return [];
    const regColor = getRegionColor(inspectedService.region);
    const legs = [];
    for (let i = 0; i < inspectedService.ports.length - 1; i++) {
      const from = inspectedService.ports[i];
      const to = inspectedService.ports[i + 1];
      if (!from || !to || from === to) continue;
      const fromLoc = loc(from);
      const toLoc = loc(to);
      if (!fromLoc || !toLoc) continue;
      legs.push({
        id: `${inspectedService.id}_leg_${i}`,
        from, to, fromLoc, toLoc,
        p1: projection(fromLoc),
        p2: projection(toLoc),
        isTransPacific: Math.abs(fromLoc[0] - toLoc[0]) > 160,
        color: regColor,
        index: i,
      });
    }
    return legs;
  }, [inspectedService, loc]);

  /* ── REGION MODE: AGGREGATE REAL SERVICE FLOWS PER LEG ── */
  const aggregatedCorridors = useMemo(() => {
    if (inspectedService) return [];
    const legMap = {};
    services.forEach((svc) => {
      if (!Array.isArray(svc.ports) || svc.ports.length < 2) return;
      for (let i = 0; i < svc.ports.length - 1; i++) {
        const from = svc.ports[i];
        const to = svc.ports[i + 1];
        if (!from || !to || from === to) continue;
        const key = `${from}__${to}`;
        if (!legMap[key]) {
          legMap[key] = { id: key, from, to, service_count: 0, total_load: 0, regions: new Set(), serviceObjs: [] };
        }
        legMap[key].service_count += 1;
        legMap[key].total_load += (Number(svc.load) || 0);
        if (svc.region) legMap[key].regions.add(svc.region);
        legMap[key].serviceObjs.push(svc);
      }
    });

    return Object.values(legMap).map((leg) => {
      const fromLoc = loc(leg.from);
      const toLoc = loc(leg.to);
      if (!fromLoc || !toLoc) return null;
      const fromReg = portGeoRegion(leg.from);
      const toReg = portGeoRegion(leg.to);
      const isInterRegional = Boolean(fromReg && toReg && fromReg !== toReg);
      // Run diff: a leg is "added" / "removed" when every service on it is, else it is shared ("kept").
      let diffStatus = null;
      if (diff) {
        const st = new Set(leg.serviceObjs.map((sv) => diff.get(String(sv.id)) || 'kept'));
        diffStatus = st.size === 1 ? [...st][0] : 'kept';
      }
      return {
        ...leg,
        fromLoc,
        toLoc,
        p1: projection(fromLoc),
        p2: projection(toLoc),
        isTransPacific: Math.abs(fromLoc[0] - toLoc[0]) > 160,
        isInterRegional,
        diffStatus,
        color: diffStatus ? DIFF_TONE[diffStatus] : isInterRegional && regionFilter === 'world' ? '#fbbf24' : getRegionColor(fromReg),
        regions: Array.from(leg.regions),
        avg_load: Math.round(leg.total_load / (leg.service_count || 1)),
      };
    }).filter(Boolean);
  }, [services, inspectedService, regionFilter, loc, diff]);

  // Unserved layer: one ring per port (area ∝ TEU it could not ship or receive) and the largest unserved lanes.
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
    return out.sort((a, b) => b.teu - a.teu);   // largest drawn first, underneath
  }, [unserved, inspectedService, loc, regionFilter, matchesRegion]);
  const unservedLanes = useMemo(() => {
    if (!unserved?.hasDemand || inspectedService) return [];
    const inView = (code) => !regionFilter || regionFilter === 'world' || matchesRegion(portGeoRegion(code), regionFilter);
    return unserved.lanes.filter((l) => inView(l.o) || inView(l.d)).slice(0, UNSERVED_LANES_SHOWN).map((l) => {
      const a = loc(l.o); const b = loc(l.d);
      if (!a || !b) return null;
      return { ...l, a, b, transPacific: Math.abs(a[0] - b[0]) > 160, d: arcPath(projection(a), projection(b), 0.22) };
    }).filter(Boolean);
  }, [unserved, inspectedService, loc, regionFilter, matchesRegion]);
  const unservedMax = unservedRings.length ? unservedRings[0].teu : 0;
  const ringR = (teu) => (unservedMax > 0 ? 3 + 13 * Math.sqrt(teu / unservedMax) : 0);

  const maxLegLoad = useMemo(() => Math.max(0, ...aggregatedCorridors.map((l) => l.total_load)), [aggregatedCorridors]);

  // Top corridors for the legend
  const topCorridors = useMemo(() => {
    return [...aggregatedCorridors].sort((a, b) => b.total_load - a.total_load).slice(0, 4);
  }, [aggregatedCorridors]);

  // Layer toggles
  const showPorts = !layerVisibility || layerVisibility.has('ports');
  const showSelected = !layerVisibility || layerVisibility.has('selected');

  // Ports layer: the dataset's own ports, plus any port the services call; size by port calls.
  const portDots = useMemo(() => {
    const codes = new Set([...activeDatasetPorts(), ...callCount.keys()]);
    const out = [];
    codes.forEach((code) => {
      const c = loc(code);
      if (!c) return;
      const region = portGeoRegion(code);
      if (regionFilter && regionFilter !== 'world' && !matchesRegion(region, regionFilter)) return;
      out.push({ code, coords: c, region, calls: callCount.get(code) || 0 });
    });
    return out.sort((a, b) => a.calls - b.calls);   // busiest drawn last, on top
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [callCount, loc, regionFilter, matchesRegion, registryVersion]);

  // Port labels: the busiest ports of the services on screen, with their call counts.
  const keyPortLabels = useMemo(() => {
    return [...callCount.entries()]
      .map(([id, n]) => ({ id, n, coords: loc(id), region: portGeoRegion(id) }))
      .filter((p) => p.coords)
      .sort((a, b) => b.n - a.n)
      .slice(0, 10);
  }, [callCount, loc]);

  // Fit the view to what is on screen whenever that set changes (dataset, region, agent, inspected service).
  const fitPoints = useMemo(() => {
    const codes = inspectedService ? (inspectedService.ports || []) : [...callCount.keys()];
    const pts = codes.map(loc).filter(Boolean);
    if (pts.length) return pts;
    return portDots.map((p) => p.coords);
  }, [inspectedService, callCount, loc, portDots]);
  const fitKey = useMemo(() => fitPoints.map((p) => p.join(',')).sort().join(';'), [fitPoints]);
  const fitted = useMemo(() => fitView(fitPoints, legendOpen ? 190 : 36), [fitKey, legendOpen]);   // eslint-disable-line react-hooks/exhaustive-deps

  // Glide between views: center in lon/lat and zoom on a log scale, 300 ms ease-out; a drag cancels it.
  const viewRef = useRef(view);
  const glideCancel = useRef(null);
  const applyView = useCallback((v) => { viewRef.current = v; setView(v); setLiveZoom(v.zoom); }, []);
  const glideTo = useCallback((target) => {
    if (glideCancel.current) glideCancel.current();
    const from = viewRef.current;
    if (from.zoom === target.zoom && from.center[0] === target.center[0] && from.center[1] === target.center[1]) return;
    glideCancel.current = tween({
      from: [from.center[0], from.center[1], Math.log(from.zoom)],
      to: [target.center[0], target.center[1], Math.log(target.zoom)],
      duration: MS[300],
      onFrame: ([x, y, lz], t) => applyView(t >= 1 ? target : { center: [x, y], zoom: Math.exp(lz) }),
      onDone: () => { glideCancel.current = null; },
    });
  }, [applyView]);
  useEffect(() => () => glideCancel.current && glideCancel.current(), []);

  // The first fit lands at once; later ones (region, agent, iteration, inspected service) glide.
  const fittedOnce = useRef(false);
  useEffect(() => {
    if (!fittedOnce.current) { fittedOnce.current = true; applyView(fitted); return; }
    glideTo(fitted);
  }, [fitted]); // eslint-disable-line react-hooks/exhaustive-deps

  const zoomBy = (f) => {
    const v = viewRef.current;
    glideTo({ ...v, zoom: Math.min(MAX_ZOOM, Math.max(1, Math.round(v.zoom * f * 100) / 100)) });
  };
  const pickPort = useCallback((code) => {
    const c = loc(code);
    if (onPortOpen) onPortOpen(code); else setClickedPort(code);
    if (c) glideTo({ center: c, zoom: Math.max(PORT_ZOOM, viewRef.current.zoom) });
  }, [loc, glideTo, onPortOpen]);
  // A port asked for from outside (command palette → Network tab).
  useEffect(() => { if (focusPort) pickPort(focusPort); }, [focusPort]); // eslint-disable-line react-hooks/exhaustive-deps

  // Route draw-on, once per run and surface. Layout effect: the legs start hidden on the first painted frame.
  const [drawing, setDrawing] = useState(false);
  const hasLegs = aggregatedCorridors.length > 0;
  useLayoutEffect(() => {
    if (!drawKey || !hasLegs || drawnKeys.has(drawKey)) return;
    drawnKeys.add(drawKey);
    if (motion !== 'off') setDrawing(true);
  }, [drawKey, hasLegs]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!drawing) return undefined;
    const t = setTimeout(() => setDrawing(false), DRAW_TOTAL_MS);
    return () => clearTimeout(t);
  }, [drawing]);
  const drawDelay = useMemo(() => {
    const ranked = [...aggregatedCorridors].sort((a, b) => b.total_load - a.total_load);
    const n = Math.max(1, ranked.length - 1);
    return new Map(ranked.map((l, i) => [l.id, Math.round((i / n) * DRAW_SPREAD_MS)]));
  }, [aggregatedCorridors]);

  // Hover link: legs and ports of the hovered service / agent stay lit, the rest dims.
  const hoverLit = useMemo(() => {
    if (!hover || inspectedService) return null;
    const legs = new Set(); const ports = new Set();
    aggregatedCorridors.forEach((l) => {
      if (l.serviceObjs.some((s) => matchesHover(s, hover))) { legs.add(l.id); ports.add(l.from); ports.add(l.to); }
    });
    return legs.size ? { legs, ports } : null;
  }, [hover, inspectedService, aggregatedCorridors]);

  // Stable zoom handlers: react-simple-maps rebinds d3-zoom whenever these change, which a glide would do per frame.
  const filterZoom = useCallback((e) => (e.type === 'wheel' ? (e.ctrlKey || e.metaKey) : !e.button), []);
  const onMoveStart = useCallback(() => { if (glideCancel.current) { glideCancel.current(); glideCancel.current = null; } }, []);
  const onMove = useCallback(({ zoom }) => setLiveZoom(zoom), []);
  const onMoveEnd = useCallback(({ coordinates, zoom }) => applyView({ center: coordinates, zoom }), [applyView]);

  // Vessel animation controls (single-service inspection).
  const [vesselsPaused, setVesselsPaused] = useState(false);
  const dayRef = useRef(null);
  const voyageTiming = useMemo(() => legScheduleOf(inspectedService, getPortCoordinates)?.source || null, [inspectedService]);

  // Marks keep their screen size while the map zooms.
  const k = liveZoom || 1;
  const s = (v) => v / k;
  const fittedToWorld = fitted === WORLD_VIEW;
  const atFit = view.zoom === fitted.zoom && view.center[0] === fitted.center[0] && view.center[1] === fitted.center[1];

  return (
    <div className={`wm-root relative w-full h-full min-h-[360px] bg-[#030a14] overflow-hidden select-none font-mono ${hoverLit ? 'wm-hovering' : ''} ${drawing ? 'wm-draw' : ''}`}>
      {/* ── MODE STATUS CHIP (Top-Left) ── */}
      {inspectedService && (
        <div className="absolute top-3 left-3 z-20 flex items-center gap-2 flex-wrap p-1.5 px-3 rounded bg-black/85 backdrop-blur-md border border-cyan-500/50 shadow-xl" style={{ maxWidth: 'calc(100% - 140px)' }}>
          <span className="w-2 h-2 rounded-full bg-cyan-400" />
          <span className="text-[12px] font-bold text-white uppercase tracking-wider">
            SERVICE INSPECTION: <span className="text-cyan-400">{inspectedService.id}</span>
          </span>
          <span className="text-[12px] px-1.5 py-0.5 rounded uppercase font-bold" style={{ background: `${getRegionColor(inspectedService.region)}25`, color: getRegionColor(inspectedService.region) }}>
            {inspectedService.region}
          </span>
          {Number(inspectedService.cycle_time_days) > 0 && (
            <span className="wm-voyage" title={`Vessel markers sail the loop at its real ${inspectedService.cycle_time_days}-day cycle time, scaled to ${DAYS_PER_SECOND} day per second. ${voyageTiming === 'run'
              ? "Sail days per leg and port stays are the run's own (ledger) figures; slack between them and the whole-day cycle is spent waiting at the first port."
              : 'Estimated timing: this run has no per-leg times, so sea time (cycle minus a 24 h stay per call) is split by leg distance.'} ${inspectedService.vessels || 1} vessel(s), one departure every ${(7 / (Number(inspectedService.frequency_per_week) || 1)).toFixed(0)} days.`}>
              <span ref={dayRef}>day 0.0 of {inspectedService.cycle_time_days}</span>
              <span className="wm-voyage-scale">· 1 s = 1 day · {voyageTiming === 'run' ? 'run leg times' : 'estimated leg times'}{motion !== 'full' ? ' · still (motion setting)' : ''}</span>
              {motion === 'full' && (
                <button type="button" onClick={() => setVesselsPaused((v) => !v)} aria-pressed={vesselsPaused} aria-label={vesselsPaused ? 'Resume the vessels' : 'Pause the vessels'}>
                  {vesselsPaused ? '▶' : '❚❚'}
                </button>
              )}
            </span>
          )}
          {onClearService && (
            <button
              type="button"
              onClick={onClearService}
              className="ml-2 text-[12px] px-2 py-0.5 rounded bg-white/10 hover:bg-white/20 text-slate-200 uppercase font-semibold transition-colors"
            >
              ✕ BACK TO REGION
            </button>
          )}
        </div>
      )}

      {/* ── ZOOM CONTROLS (Top-Right) ── */}
      <div className="wm-zoom" role="group" aria-label="Map zoom">
        <button type="button" onClick={() => zoomBy(1.6)} aria-label="Zoom in" title="Zoom in">+</button>
        <button type="button" onClick={() => zoomBy(1 / 1.6)} aria-label="Zoom out" title="Zoom out" disabled={view.zoom <= 1}>−</button>
        <button
          type="button"
          onClick={() => glideTo(fitted)}
          aria-label={fittedToWorld ? 'Show the whole world' : 'Fit the map to the ports shown'}
          title="Drag to pan · Ctrl + scroll to zoom"
          className={atFit ? 'is-on' : ''}
        >
          {fittedToWorld ? 'World' : 'Fit'}
        </button>
      </div>

      <div className="absolute inset-0 z-0">
        <ComposableMap
          projection={projection}
          width={W}
          height={H}
          style={{ width: "100%", height: "100%" }}
        >
          <ZoomableGroup
            center={view.center}
            zoom={view.zoom}
            minZoom={1}
            maxZoom={MAX_ZOOM}
            filterZoomEvent={filterZoom}
            onMoveStart={onMoveStart}
            onMove={onMove}
            onMoveEnd={onMoveEnd}
          >
            {/* ── Basemap: land a step lighter than the sea ── */}
            {BASEMAP}

            {/* ══ MODE A: SINGLE SERVICE INSPECTION ══ */}
            {inspectedService && singleServiceLegs.map((leg) => {
              const strokeColor = leg.color;
              if (leg.isTransPacific) {
                return (
                  <Line key={leg.id} from={leg.fromLoc} to={leg.toLoc} stroke={strokeColor}
                    strokeWidth={s(3.5)} strokeLinecap="round" />
                );
              }
              const pathD = arcPath(leg.p1, leg.p2, 0.16);
              return (
                <g key={leg.id}>
                  <path d={pathD} fill="none" stroke={strokeColor} strokeWidth={s(7.5)} strokeOpacity={0.3} strokeLinecap="round" />
                  <path d={pathD} fill="none" stroke={strokeColor} strokeWidth={s(3.5)} strokeOpacity={0.95} strokeLinecap="round"
                    className="wm-flow" strokeDasharray={`${s(7)} ${s(4)}`} style={{ '--dash': s(11) }} />
                </g>
              );
            })}

            {inspectedService && (inspectedService.ports || []).map((portId, idx) => {
              const c = loc(portId);
              if (!c) return null;
              const isOrigin = idx === 0;
              const isDest = idx === (inspectedService.ports.length - 1);
              const regColor = getRegionColor(inspectedService.region);
              const tag = isOrigin ? 'ORIGIN' : isDest ? 'LAST CALL' : `CALL ${idx + 1}`;
              return (
                <Marker key={`insp_port_${portId}_${idx}`} coordinates={c}>
                  {isOrigin && <circle r={s(9)} fill={regColor} fillOpacity={0.2} />}
                  <circle r={s(isOrigin || isDest ? 5 : 4)} fill={isOrigin ? '#10b981' : isDest ? '#00d4ff' : regColor}
                    stroke="#ffffff" strokeWidth={s(1.5)} />
                  <g transform={`translate(0, ${s(isOrigin ? -14 : 16)}) scale(${1 / k})`}>
                    <rect x="-45" y="-8" width="90" height="17" rx="3" fill="#050d18" fillOpacity="0.9" stroke={regColor} strokeWidth="0.8" />
                    <text x="0" y="-1" textAnchor="middle" fontSize="5" fill={regColor} fontWeight="800" fontFamily="monospace" letterSpacing="0.08em">
                      {tag} · {portId}
                    </text>
                    <text x="0" y="6" textAnchor="middle" fontSize="5" fill="#e2e8f0" fontWeight="600" fontFamily="monospace">
                      {getPortName(portId)}
                    </text>
                  </g>
                </Marker>
              );
            })}

            {inspectedService && (
              <ServiceVessels key={inspectedService.id} service={inspectedService} k={k} motion={motion} paused={vesselsPaused} dayRef={dayRef} />
            )}

            {/* ── Unserved lanes: the largest OD demands the plan leaves uncarried, dashed, under the routes ── */}
            {unservedLanes.map((l) => {
              const tip = `${l.o} → ${l.d}: ${fmtNum(l.teu)} of ${fmtNum(l.demand)} TEU/week not carried`;
              const w = s(0.8 + 2.2 * Math.sqrt(l.teu / (unservedLanes[0]?.teu || 1)));
              return l.transPacific ? (
                <Line key={`un_${l.o}_${l.d}`} from={l.a} to={l.b} stroke={VIZ_2} strokeWidth={w} strokeOpacity={0.75}
                  strokeDasharray={`${s(4)} ${s(3)}`} className="wm-unserved-lane"><title>{tip}</title></Line>
              ) : (
                <path key={`un_${l.o}_${l.d}`} d={l.d} fill="none" stroke={VIZ_2} strokeWidth={w} strokeOpacity={0.75}
                  strokeDasharray={`${s(4)} ${s(3)}`} className="wm-unserved-lane"><title>{tip}</title></path>
              );
            })}

            {/* ══ MODE B: SERVICES ON SCREEN, ONE LINE PER LEG, WIDTH BY TEU ══ */}
            {!inspectedService && showSelected && aggregatedCorridors.map((leg) => {
              const w = s(legWidth(leg.total_load, maxLegLoad));
              const open = () => {
                if (onSelectService && leg.serviceObjs.length > 0) onSelectService(leg.serviceObjs[0]);
                else setSelectedCorridor(leg);
              };
              const tip = `${leg.from} → ${leg.to}: ${fmtNum(leg.total_load)} TEU on ${leg.service_count} service${leg.service_count === 1 ? '' : 's'}${leg.diffStatus ? ` · ${leg.diffStatus === 'kept' ? 'in both runs' : leg.diffStatus === 'added' ? 'only in run B' : 'only in run A'}` : ''}`;
              const lit = hoverLit?.legs.has(leg.id);
              const draw = { pathLength: 1, style: { '--d': `${drawDelay.get(leg.id) || 0}ms` } };
              if (leg.diffStatus === 'removed' && !drawing) draw.strokeDasharray = '0.02 0.012';
              if (leg.isTransPacific) {
                return (
                  <Line key={leg.id} from={leg.fromLoc} to={leg.toLoc} stroke={leg.color} strokeWidth={lit ? w * 1.6 : w}
                    strokeLinecap="round" strokeOpacity={0.8} className={`cursor-pointer wm-leg wm-leg-line ${lit ? 'is-hl' : ''}`} onClick={open} {...draw}>
                    <title>{tip}</title>
                  </Line>
                );
              }
              const pathD = arcPath(leg.p1, leg.p2, leg.isInterRegional ? 0.16 : 0.08);
              return (
                <g key={leg.id} className={`cursor-pointer wm-leg ${lit ? 'is-hl' : ''}`} onClick={open}>
                  <title>{tip}</title>
                  <path d={pathD} fill="none" stroke="transparent" strokeWidth={s(8)} />
                  <path d={pathD} fill="none" stroke={leg.color} strokeWidth={lit ? w * 1.6 : w} strokeOpacity={0.85} strokeLinecap="round" className="wm-leg-line" {...draw} />
                </g>
              );
            })}

            {/* ── Unserved rings: area ∝ TEU a port could not ship or receive ── */}
            {unservedRings.map((p) => (
              <Marker key={`ur_${p.code}`} coordinates={p.coords} onClick={() => pickPort(p.code)} className="wm-unserved">
                <title>{`${getPortName(p.code)} (${p.code}) · ${fmtNum(p.teu)} TEU/week unserved (${fmtNum(p.out)} out, ${fmtNum(p.in)} in) of ${fmtNum(p.demand)} demand`}</title>
                <circle r={s(ringR(p.teu))} fill={VIZ_2} fillOpacity={0.1} stroke={VIZ_2} strokeWidth={s(1.4)} strokeOpacity={0.9} className="cursor-pointer" />
              </Marker>
            ))}

            {/* ── PORTS: the dataset's ports; called ports sized by calls ── */}
            {!inspectedService && showPorts && portDots.map((p) => {
              const called = p.calls > 0;
              const r = called ? 1.8 + 3.2 * Math.sqrt(p.calls / maxCalls) : 1.4;
              const color = called ? getRegionColor(p.region) : '#4b6478';
              return (
                <Marker key={p.code} coordinates={p.coords} onClick={() => pickPort(p.code)} className={`wm-port ${hoverLit?.ports.has(p.code) ? 'is-hl' : ''}`}>
                  <title>{`${getPortName(p.code)} (${p.code})${called ? ` · ${p.calls} call${p.calls === 1 ? '' : 's'}` : ' · not called by the plan'}`}</title>
                  {called && <circle r={s(r + 2.5)} fill={color} fillOpacity={0.18} />}
                  <circle r={s(r)} fill={color} fillOpacity={called ? 0.95 : 0.7} className="cursor-pointer" />
                  {openPort === p.code && <circle r={s(r + 5)} fill="none" stroke="#f8fafc" strokeWidth={s(1.6)} />}
                </Marker>
              );
            })}

            {/* ── Busiest port labels ── */}
            {!inspectedService && keyPortLabels.map((p) => (
              <Marker key={`lbl_${p.id}`} coordinates={p.coords} className={`wm-port ${hoverLit?.ports.has(p.id) ? 'is-hl' : ''}`}>
                <text
                  y={s(-8)}
                  textAnchor="middle"
                  fontSize={s(6.5)}
                  fill="#e2e8f0"
                  fontWeight="700"
                  fontFamily="monospace"
                  letterSpacing="0.06em"
                  style={{ pointerEvents: "none", paintOrder: "stroke", stroke: "#030a14", strokeWidth: s(2) }}
                >
                  {p.id} {p.n}
                </text>
              </Marker>
            ))}
          </ZoomableGroup>
        </ComposableMap>
      </div>

      {/* ── INTERACTIVE SERVICE CORRIDOR INSPECTOR POPUP ── */}
      {selectedCorridor && !inspectedService && (
        <div className="absolute top-12 left-6 z-20 p-3 rounded-lg bg-black/90 border border-cyan-500/50 backdrop-blur-md min-w-[210px] text-left font-mono shadow-2xl">
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
          </div>
          <div className="mt-2 pt-2 border-t border-white/10">
            <div className="text-[12px] text-slate-400 uppercase tracking-widest mb-1">SERVICES</div>
            <div className="text-[12px] text-slate-300 space-y-1 max-h-20 overflow-y-auto">
              {selectedCorridor.serviceObjs.slice(0, 6).map((sv, idx) => (
                <div key={idx} className="truncate text-cyan-300">▶ {sv.id} ({(sv.ports || []).join('→')})</div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── PORT INSPECTION POPUP ── */}
      {clickedPort && (() => {
        const c = loc(clickedPort);
        const calls = callCount.get(clickedPort) || 0;
        return (
          <div className="absolute top-12 right-3 z-20 p-2.5 rounded-lg bg-black/90 border border-emerald-500/50 backdrop-blur-md min-w-[180px] text-left font-mono">
            <div className="flex justify-between items-center pb-1 border-b border-white/10 mb-1.5">
              <span className="text-[12px] text-emerald-400 font-bold uppercase tracking-wider">PORT {clickedPort}</span>
              <button type="button" onClick={() => setClickedPort(null)} className="text-slate-400 hover:text-white text-xs" aria-label="Close">✕</button>
            </div>
            <div className="text-[12px] text-slate-200 font-semibold">{getPortName(clickedPort)}</div>
            <div className="text-[12px] text-slate-300 mt-0.5">Region: <span className="text-cyan-400 font-semibold">{portGeoRegion(clickedPort) || 'unknown'}</span></div>
            <div className="text-[12px] text-slate-300 mt-0.5">Calls in plan: <span className="text-slate-100 font-semibold">{calls}</span></div>
            <div className="text-[12px] text-slate-300 mt-0.5">Lon, lat: <span className="text-slate-400">{c ? `${c[0].toFixed(2)}, ${c[1].toFixed(2)}` : 'not in ports.csv'}</span></div>
          </div>
        );
      })()}

      {/* ── LEGEND (Bottom-Left) ── */}
      <div className="absolute bottom-3 left-3 z-10 p-2.5 rounded bg-black/80 backdrop-blur-md border border-white/10 min-w-[210px] max-w-[260px] pointer-events-auto">
        <button
          type="button"
          className={`w-full flex justify-between items-center gap-3 text-left ${legendOpen ? 'mb-1.5 pb-1 border-b border-white/10' : ''}`}
          onClick={() => setLegendOpen((v) => !v)}
          aria-expanded={legendOpen}
          title={legendOpen ? 'Fold the legend' : 'Show the legend'}
        >
          <span className="text-[12px] text-slate-400 font-mono tracking-widest uppercase font-bold">
            <span aria-hidden="true">{legendOpen ? '▾' : '▸'}</span> LEGEND
          </span>
          <span className="text-[12px] font-mono text-emerald-400 font-bold">
            {inspectedService ? 'ONE SERVICE' : `${services.length} SERVICES`}
          </span>
        </button>

        {!legendOpen ? null : inspectedService ? (
          <div className="space-y-1 text-[12px]">
            <div className="flex justify-between gap-3"><span className="text-slate-400">SERVICE</span><span className="text-cyan-400 font-bold">{inspectedService.id}</span></div>
            <div className="flex justify-between gap-3"><span className="text-slate-400">CALLS</span><span className="text-slate-100 font-semibold">{(inspectedService.ports || []).length}</span></div>
            <div className="flex justify-between gap-3"><span className="text-slate-400">VESSEL</span><span className="text-slate-200">{inspectedService.vessel_class || '—'}</span></div>
            <div className="flex justify-between gap-3"><span className="text-slate-400">LOAD</span><span className="text-emerald-400 font-bold">{fmtNum(inspectedService.load)} TEU</span></div>
            <div className="flex justify-between gap-3"><span className="text-slate-400">P&amp;L / WK</span><span className={`font-bold ${Number(inspectedService.weekly_profit) < 0 ? 'text-red-400' : 'text-emerald-300'}`}>{fmtUsd(inspectedService.weekly_profit)}</span></div>
          </div>
        ) : (
          <>
            {diff && (
              <div className="mb-1.5 pb-1.5 border-b border-white/10 space-y-1">
                {[['added', 'Only in run B'], ['removed', 'Only in run A (dashed)'], ['kept', 'In both runs']].map(([k2, label]) => (
                  <div key={k2} className="flex items-center gap-2">
                    <svg width="28" height="8" aria-hidden="true"><line x1="1" y1="4" x2="27" y2="4" stroke={DIFF_TONE[k2]} strokeWidth="2.4" strokeLinecap="round" strokeDasharray={k2 === 'removed' ? '5 3' : undefined} /></svg>
                    <span className="text-[12px] text-slate-300">{label}</span>
                  </div>
                ))}
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
                  <span className="text-[12px] text-slate-300">Top {unservedLanes.length} unserved lanes</span>
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
                <div className="flex items-center gap-2 mt-1.5 mb-1">
                  <span className="w-4 h-[3px] bg-amber-400 rounded" aria-hidden="true" />
                  <span className="text-[12px] text-amber-300">Leg between two regions</span>
                </div>
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="w-4 h-[3px] rounded" style={{ background: 'linear-gradient(90deg,#10b981,#7c3aed,#00d4ff)' }} aria-hidden="true" />
                  <span className="text-[12px] text-slate-300">Leg within a region (region colour)</span>
                </div>
              </>
            )}
            <div className="text-[12px] text-slate-400 mb-1.5">Dot size = port calls · grey = not called</div>
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
    </div>
  );
}
