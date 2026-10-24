import React, { useState, useCallback, useMemo, useEffect } from "react";
import { ComposableMap, Geographies, Geography, Marker, Line, ZoomableGroup } from "react-simple-maps";
import { geoEquirectangular } from "d3-geo";
import { getPortName, getPortCoordinates } from '../../utils/portLookup.js';
import { activeDatasetPorts, portRegistryVersion } from '../../utils/portRegistry.js';
import { fmtNum, fmtUsd } from '../../utils/formatters.js';
import { portGeoRegion } from '../../utils/geoRegion.js';
import { useAgentFocus, matchesAgent } from '../../services/focusStore.js';

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

export default function WorldMap({
  optimizationState,
  selectedServices: propSelectedServices = null,
  inspectedService = null,
  regionFilter = 'world',
  layerVisibility = null,
  onSelectService = null,
  onClearService = null,
}) {
  const [selectedCorridor, setSelectedCorridor] = useState(null);
  const [clickedPort, setClickedPort] = useState(null);
  // Legend starts folded on narrow screens, where it would cover most of the map.
  const [legendOpen, setLegendOpen] = useState(() => typeof window === 'undefined' || window.innerWidth >= 768);
  const [view, setView] = useState(WORLD_VIEW);
  const [liveZoom, setLiveZoom] = useState(1);
  const [agentFocus] = useAgentFocus();
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
      return {
        ...leg,
        fromLoc,
        toLoc,
        p1: projection(fromLoc),
        p2: projection(toLoc),
        isTransPacific: Math.abs(fromLoc[0] - toLoc[0]) > 160,
        isInterRegional,
        color: isInterRegional && regionFilter === 'world' ? '#fbbf24' : getRegionColor(fromReg),
        regions: Array.from(leg.regions),
        avg_load: Math.round(leg.total_load / (leg.service_count || 1)),
      };
    }).filter(Boolean);
  }, [services, inspectedService, regionFilter, loc]);

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
  useEffect(() => { setView(fitted); setLiveZoom(fitted.zoom); }, [fitted]);

  const zoomBy = (f) => setView((v) => {
    const zoom = Math.min(MAX_ZOOM, Math.max(1, Math.round(v.zoom * f * 100) / 100));
    setLiveZoom(zoom);
    return { ...v, zoom };
  });

  // Marks keep their screen size while the map zooms.
  const k = liveZoom || 1;
  const s = (v) => v / k;
  const fittedToWorld = fitted === WORLD_VIEW;
  const atFit = view.zoom === fitted.zoom && view.center[0] === fitted.center[0] && view.center[1] === fitted.center[1];

  return (
    <div className="wm-root relative w-full h-full min-h-[360px] bg-[#030a14] overflow-hidden select-none font-mono">
      {/* ── MODE STATUS CHIP (Top-Left) ── */}
      {inspectedService && (
        <div className="absolute top-3 left-3 z-20 flex items-center gap-2 p-1.5 px-3 rounded bg-black/85 backdrop-blur-md border border-cyan-500/50 shadow-xl">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          <span className="text-[12px] font-bold text-white uppercase tracking-wider">
            SERVICE INSPECTION: <span className="text-cyan-400">{inspectedService.id}</span>
          </span>
          <span className="text-[12px] px-1.5 py-0.5 rounded uppercase font-bold" style={{ background: `${getRegionColor(inspectedService.region)}25`, color: getRegionColor(inspectedService.region) }}>
            {inspectedService.region}
          </span>
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
          onClick={() => { setView(fitted); setLiveZoom(fitted.zoom); }}
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
            filterZoomEvent={(e) => (e.type === 'wheel' ? (e.ctrlKey || e.metaKey) : !e.button)}
            onMove={({ zoom }) => setLiveZoom(zoom)}
            onMoveEnd={({ coordinates, zoom }) => { setView({ center: coordinates, zoom }); setLiveZoom(zoom); }}
          >
            {/* ── Basemap: land a step lighter than the sea ── */}
            <Geographies geography={geoUrl}>
              {({ geographies }) =>
                geographies.map((geo) => (
                  <Geography
                    key={geo.rsmKey}
                    geography={geo}
                    fill="#11253a"
                    stroke="#21405e"
                    strokeWidth={s(0.5)}
                    style={{
                      default: { outline: "none" },
                      hover: { fill: "#152c44", outline: "none" },
                      pressed: { outline: "none" },
                    }}
                  />
                ))
              }
            </Geographies>

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

            {/* ══ MODE B: SERVICES ON SCREEN, ONE LINE PER LEG, WIDTH BY TEU ══ */}
            {!inspectedService && showSelected && aggregatedCorridors.map((leg) => {
              const w = s(legWidth(leg.total_load, maxLegLoad));
              const open = () => {
                if (onSelectService && leg.serviceObjs.length > 0) onSelectService(leg.serviceObjs[0]);
                else setSelectedCorridor(leg);
              };
              const tip = `${leg.from} → ${leg.to}: ${fmtNum(leg.total_load)} TEU on ${leg.service_count} service${leg.service_count === 1 ? '' : 's'}`;
              if (leg.isTransPacific) {
                return (
                  <Line key={leg.id} from={leg.fromLoc} to={leg.toLoc} stroke={leg.color} strokeWidth={w}
                    strokeLinecap="round" strokeOpacity={0.8} className="cursor-pointer" onClick={open}>
                    <title>{tip}</title>
                  </Line>
                );
              }
              const pathD = arcPath(leg.p1, leg.p2, leg.isInterRegional ? 0.16 : 0.08);
              return (
                <g key={leg.id} className="cursor-pointer wm-leg" onClick={open}>
                  <title>{tip}</title>
                  <path d={pathD} fill="none" stroke="transparent" strokeWidth={s(8)} />
                  <path d={pathD} fill="none" stroke={leg.color} strokeWidth={w} strokeOpacity={0.85} strokeLinecap="round" />
                </g>
              );
            })}

            {/* ── PORTS: the dataset's ports; called ports sized by calls ── */}
            {!inspectedService && showPorts && portDots.map((p) => {
              const called = p.calls > 0;
              const r = called ? 1.8 + 3.2 * Math.sqrt(p.calls / maxCalls) : 1.4;
              const color = called ? getRegionColor(p.region) : '#4b6478';
              return (
                <Marker key={p.code} coordinates={p.coords} onClick={() => setClickedPort(p.code)}>
                  <title>{`${getPortName(p.code)} (${p.code})${called ? ` · ${p.calls} call${p.calls === 1 ? '' : 's'}` : ' · not called by the plan'}`}</title>
                  {called && <circle r={s(r + 2.5)} fill={color} fillOpacity={0.18} />}
                  <circle r={s(r)} fill={color} fillOpacity={called ? 0.95 : 0.7} className="cursor-pointer" />
                </Marker>
              );
            })}

            {/* ── Busiest port labels ── */}
            {!inspectedService && keyPortLabels.map((p) => (
              <Marker key={`lbl_${p.id}`} coordinates={p.coords}>
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
            <div className="text-[12px] text-slate-400 mb-1">Line width = TEU on the leg</div>
            {[1, 0.25, 0.04].map((f) => (
              <div key={f} className="flex items-center gap-2 mb-1">
                <svg width="28" height="8" aria-hidden="true"><line x1="1" y1="4" x2="27" y2="4" stroke="#cbd5e1" strokeWidth={legWidth(f * maxLegLoad, maxLegLoad)} strokeLinecap="round" /></svg>
                <span className="text-[12px] text-slate-300">{maxLegLoad > 0 ? `${fmtNum(Math.round(f * maxLegLoad))} TEU` : '—'}</span>
              </div>
            ))}
            <div className="flex items-center gap-2 mt-1.5 mb-1">
              <span className="w-4 h-[3px] bg-amber-400 rounded" aria-hidden="true" />
              <span className="text-[12px] text-amber-300">Leg between two regions</span>
            </div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="w-4 h-[3px] rounded" style={{ background: 'linear-gradient(90deg,#10b981,#7c3aed,#00d4ff)' }} aria-hidden="true" />
              <span className="text-[12px] text-slate-300">Leg within a region (region colour)</span>
            </div>
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
