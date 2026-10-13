import React, { useState, useCallback, useMemo } from "react";
import { ComposableMap, Geographies, Geography, Marker, Line } from "react-simple-maps";
import { geoEquirectangular } from "d3-geo";
import portCoords from '../../assets/port_coordinates.json';
import { getPortName, getPortFullLabel } from '../../utils/portLookup.js';
import { fmtNum, fmtUsd } from '../../utils/formatters.js';

const geoUrl = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

// Projection matching ComposableMap config
const projection = geoEquirectangular()
  .scale(145)
  .center([15, 12])
  .translate([450, 200]);

export function getRegionColor(regionId) {
  const r = String(regionId || '').toLowerCase().trim();
  if (r.includes('americ')) return '#10b981'; // Emerald
  if (r.includes('europ')) return '#7c3aed';  // Purple
  if (r.includes('middl') || r.includes('east')) return '#f59e0b'; // Amber
  if (r.includes('asia') || r.includes('pacif')) return '#00d4ff'; // Cyan
  if (r.includes('afric')) return '#ef4444';  // Red
  return '#00d4ff';
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
  if (!Number.isFinite(dist) || dist < 1.0) return `M ${x1} ${y1} L ${x2} ${y2}`;

  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  const nx = -dy / dist;
  const ny = dx / dist;

  // Arc towards upper half of map (north bow)
  const bow = curvature * dist * (y1 > y2 ? -1 : 1);
  const cx = mx + nx * bow;
  const cy = my + ny * bow;

  return `M ${x1.toFixed(1)} ${y1.toFixed(1)} Q ${cx.toFixed(1)} ${cy.toFixed(1)} ${x2.toFixed(1)} ${y2.toFixed(1)}`;
}

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

  // Filtered services for the active region
  const services = useMemo(() => {
    if (inspectedService) {
      return [inspectedService];
    }
    if (!regionFilter || regionFilter === 'world') {
      return allServices;
    }
    return allServices.filter((s) => matchesRegion(s.region, regionFilter));
  }, [allServices, inspectedService, regionFilter, matchesRegion]);

  const portRegionMap = useMemo(() => {
    const counts = {};
    allServices.forEach((svc) => {
      const region = svc.region || 'Asia';
      (svc.ports || []).forEach((p) => {
        if (!counts[p]) counts[p] = {};
        counts[p][region] = (counts[p][region] || 0) + 1;
      });
    });
    const map = {};
    Object.entries(counts).forEach(([port, regionCounts]) => {
      map[port] = Object.entries(regionCounts).sort((a, b) => b[1] - a[1])[0][0];
    });
    return map;
  }, [allServices]);

  const getPortLocation = useCallback((portId, fallbackRegion) => {
    if (portId && portCoords[portId]) {
      const coord = portCoords[portId];
      // portCoords is [lat, lng] -> convert to [lng, lat]
      return [coord[1], coord[0]];
    }
    const regionId = String(portRegionMap[portId] || fallbackRegion || 'asia').toLowerCase();
    const strHash = (str) => {
      let h = 0;
      for (let i = 0; i < str.length; i++) h = ((h << 5) - h) + str.charCodeAt(i);
      return Math.abs(h);
    };
    const seed = typeof portId === 'string' ? strHash(portId) : (portId * 9301 + 49297);
    const rnd1 = (seed % 233280) / 233280;
    const rnd2 = ((seed * 9301 + 49297) % 233280) / 233280;
    const bounds = {
      asia:        { minLng: 70,  maxLng: 135, minLat: 5,   maxLat: 40  },
      europe:      { minLng: -5,  maxLng: 28,  minLat: 38,  maxLat: 58  },
      americas:    { minLng: -115,maxLng: -45, minLat: -25, maxLat: 48  },
      middle_east: { minLng: 38,  maxLng: 58,  minLat: 14,  maxLat: 29  },
      africa:      { minLng: -10, maxLng: 45,  minLat: -30, maxLat: 30  },
    };
    const b = bounds[regionId] || bounds.asia;
    return [b.minLng + rnd1 * (b.maxLng - b.minLng), b.minLat + rnd2 * (b.maxLat - b.minLat)];
  }, [portRegionMap]);

  /* ── SINGLE SERVICE MODE DATA ── */
  const singleServiceLegs = useMemo(() => {
    if (!inspectedService || !inspectedService.ports || inspectedService.ports.length < 2) {
      return [];
    }
    const regColor = getRegionColor(inspectedService.region);
    const legs = [];
    for (let i = 0; i < inspectedService.ports.length - 1; i++) {
      const from = inspectedService.ports[i];
      const to = inspectedService.ports[i + 1];
      if (!from || !to || from === to) continue;
      const fromLoc = getPortLocation(from, inspectedService.region);
      const toLoc = getPortLocation(to, inspectedService.region);
      const p1 = projection(fromLoc);
      const p2 = projection(toLoc);
      const isTransPacific = Math.abs(fromLoc[0] - toLoc[0]) > 160;

      legs.push({
        id: `${inspectedService.id}_leg_${i}`,
        from,
        to,
        fromLoc,
        toLoc,
        p1,
        p2,
        isTransPacific,
        color: regColor,
        load: inspectedService.load || 1000,
        index: i,
      });
    }
    return legs;
  }, [inspectedService, getPortLocation]);

  /* ── REGION MODE: DERIVE AND AGGREGATE REAL SERVICE FLOWS ── */
  const aggregatedCorridors = useMemo(() => {
    if (inspectedService) return [];
    const legMap = {};

    services.forEach((svc) => {
      if (!svc.ports || !Array.isArray(svc.ports) || svc.ports.length < 2) return;
      const svcRegion = svc.region || 'Asia';
      const color = getRegionColor(svcRegion);

      for (let i = 0; i < svc.ports.length - 1; i++) {
        const from = svc.ports[i];
        const to = svc.ports[i + 1];
        if (!from || !to || from === to) continue;
        const key = `${from}__${to}`;

        if (!legMap[key]) {
          legMap[key] = {
            id: key,
            from,
            to,
            service_count: 0,
            total_load: 0,
            regions: new Set(),
            services: [],
            serviceObjs: [],
            color,
            isInterRegional: false,
          };
        }
        legMap[key].service_count += 1;
        legMap[key].total_load += (svc.load || 1000);
        legMap[key].regions.add(svcRegion);
        legMap[key].services.push(svc.id || `svc_${i}`);
        legMap[key].serviceObjs.push(svc);

        const fromReg = portRegionMap[from] || svcRegion;
        const toReg = portRegionMap[to] || svcRegion;
        if (fromReg !== toReg) {
          legMap[key].isInterRegional = true;
          if (regionFilter === 'world') {
            legMap[key].color = '#fbbf24'; // Cross-region gold in World view
          }
        }
      }
    });

    return Object.values(legMap).map((leg) => {
      const fromLoc = getPortLocation(leg.from);
      const toLoc = getPortLocation(leg.to);
      const p1 = projection(fromLoc);
      const p2 = projection(toLoc);
      const regionsArr = Array.from(leg.regions);
      const isTransPacific = Math.abs(fromLoc[0] - toLoc[0]) > 160;

      return {
        ...leg,
        fromLoc,
        toLoc,
        p1,
        p2,
        isTransPacific,
        regions: regionsArr,
        avg_load: Math.round(leg.total_load / (leg.service_count || 1)),
      };
    });
  }, [services, inspectedService, regionFilter, portRegionMap, getPortLocation]);

  // Top corridors for the legend
  const topCorridors = useMemo(() => {
    return [...aggregatedCorridors]
      .sort((a, b) => b.total_load - a.total_load)
      .slice(0, 4);
  }, [aggregatedCorridors]);

  // Layer toggles
  const showPorts = !layerVisibility || layerVisibility.has('ports');
  const showSelected = !layerVisibility || layerVisibility.has('selected');

  // Key maritime hub port labels in Region view
  const KEY_PORT_LABELS = [
    { id: 'USLAX', label: 'USLAX 114', coords: [-118.24, 33.74], region: 'americas' },
    { id: 'USLIM', label: 'USLIM 80', coords: [-77.15, -12.05], region: 'americas' },
    { id: 'USENY', label: 'USENY 30', coords: [-74.00, 40.71], region: 'americas' },
    { id: 'USSAV', label: 'USSAV 36', coords: [-81.09, 32.08], region: 'americas' },
    { id: 'NLRTM', label: 'NLRTM 111', coords: [4.47, 51.92], region: 'europe' },
    { id: 'ZAJUR', label: 'ZAJUR 64', coords: [31.02, -29.85], region: 'africa' },
    { id: 'SAJED', label: 'SAJED 21', coords: [39.19, 21.48], region: 'middle_east' },
    { id: 'CNSHA', label: 'CNSHA 188', coords: [121.47, 31.23], region: 'asia' },
    { id: 'HKHKG', label: 'HKHKG 62', coords: [114.16, 22.31], region: 'asia' },
    { id: 'SGSIN', label: 'SGSIN 59', coords: [103.81, 1.35], region: 'asia' },
  ];

  return (
    <div className="relative w-full h-full min-h-[360px] bg-[#030a14] overflow-hidden select-none font-mono">
      {/* ── MODE STATUS CHIP (Top-Left) ── */}
      {inspectedService && (
        <div className="absolute top-3 left-3 z-20 flex items-center gap-2 p-1.5 px-3 rounded bg-black/85 backdrop-blur-md border border-cyan-500/50 shadow-xl">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          <span className="text-[9px] font-bold text-white uppercase tracking-wider">
            SERVICE INSPECTION: <span className="text-cyan-400">{inspectedService.id}</span>
          </span>
          <span className="text-[8px] px-1.5 py-0.5 rounded uppercase font-bold" style={{ background: `${getRegionColor(inspectedService.region)}25`, color: getRegionColor(inspectedService.region) }}>
            {inspectedService.region}
          </span>
          {onClearService && (
            <button
              type="button"
              onClick={onClearService}
              className="ml-2 text-[8px] px-2 py-0.5 rounded bg-white/10 hover:bg-white/20 text-slate-200 uppercase font-semibold transition-colors"
            >
              ✕ BACK TO REGION
            </button>
          )}
        </div>
      )}

      <div className="absolute inset-0 z-0">
        <ComposableMap
          projection="geoEquirectangular"
          projectionConfig={{ scale: 145, center: [15, 12] }}
          width={900}
          height={400}
          style={{ width: "100%", height: "100%" }}
        >
          {/* ── Basemap: Dark oceanic continents ── */}
          <Geographies geography={geoUrl}>
            {({ geographies }) =>
              geographies.map((geo) => (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  fill="#061222"
                  stroke="#0f2942"
                  strokeWidth={0.5}
                  style={{
                    default: { outline: "none" },
                    hover: { fill: "#0a1d36", outline: "none" },
                    pressed: { outline: "none" },
                  }}
                />
              ))
            }
          </Geographies>

          {/* ══════════════════════════════════════════════════════
              MODE A: SINGLE SERVICE INSPECTION MODE
             ══════════════════════════════════════════════════════ */}
          {inspectedService && singleServiceLegs.map((leg) => {
            if (!leg.p1 || !leg.p2) return null;
            const strokeColor = leg.color;
            const strokeWidth = 3.5;

            if (leg.isTransPacific) {
              return (
                <Line
                  key={leg.id}
                  from={leg.fromLoc}
                  to={leg.toLoc}
                  stroke={strokeColor}
                  strokeWidth={strokeWidth}
                  strokeLinecap="round"
                />
              );
            }

            const pathD = arcPath(leg.p1, leg.p2, 0.16);

            return (
              <g key={leg.id}>
                {/* Glow underlay */}
                <path
                  d={pathD}
                  fill="none"
                  stroke={strokeColor}
                  strokeWidth={strokeWidth + 4.0}
                  strokeOpacity={0.35}
                  strokeLinecap="round"
                />
                {/* Main animated service path */}
                <path
                  d={pathD}
                  fill="none"
                  stroke={strokeColor}
                  strokeWidth={strokeWidth}
                  strokeOpacity={0.95}
                  strokeLinecap="round"
                />
              </g>
            );
          })}

          {/* ── SINGLE SERVICE MANDATORY PORT LABELS ── */}
          {inspectedService && (inspectedService.ports || []).map((portId, idx) => {
            const loc = getPortLocation(portId, inspectedService.region);
            const isOrigin = idx === 0;
            const isDest = idx === (inspectedService.ports.length - 1);
            const portName = getPortName(portId);
            const regColor = getRegionColor(inspectedService.region);
            const tag = isOrigin ? 'ORIGIN' : isDest ? 'DESTINATION' : `WAYPOINT ${idx}`;

            return (
              <Marker key={`insp_port_${portId}_${idx}`} coordinates={loc}>
                {/* Pulsing halo for origin */}
                {isOrigin && (
                  <circle r={9} fill={regColor} fillOpacity={0.2} className="animate-ping" />
                )}
                {/* Center marker dot */}
                <circle
                  r={isOrigin || isDest ? 5 : 4}
                  fill={isOrigin ? '#10b981' : isDest ? '#00d4ff' : regColor}
                  stroke="#ffffff"
                  strokeWidth={1.5}
                />

                {/* Detailed Port Label Badge */}
                <g transform={`translate(0, ${isOrigin ? -14 : 16})`}>
                  <rect
                    x="-45"
                    y="-8"
                    width="90"
                    height="17"
                    rx="3"
                    fill="#050d18"
                    fillOpacity="0.9"
                    stroke={regColor}
                    strokeWidth="0.8"
                  />
                  <text
                    x="0"
                    y="-1"
                    textAnchor="middle"
                    fontSize="5"
                    fill={regColor}
                    fontWeight="800"
                    fontFamily="monospace"
                    letterSpacing="0.08em"
                  >
                    {tag} · {portId}
                  </text>
                  <text
                    x="0"
                    y="6"
                    textAnchor="middle"
                    fontSize="5"
                    fill="#e2e8f0"
                    fontWeight="600"
                    fontFamily="monospace"
                  >
                    {portName} {isOrigin ? `· ${fmtNum(inspectedService.load)} TEU` : ''}
                  </text>
                </g>
              </Marker>
            );
          })}

          {/* ══════════════════════════════════════════════════════
              MODE B: REGION VIEW (Filtered by active region)
             ══════════════════════════════════════════════════════ */}
          {!inspectedService && showSelected && aggregatedCorridors.map((leg) => {
            if (!leg.p1 || !leg.p2) return null;
            const isHigh = leg.total_load >= 30000;
            const strokeColor = leg.color;
            const strokeWidth = Math.max(1.2, Math.min(3.6, (leg.total_load / 35000) * 2.2 + 1.0));

            // Trans-Pacific line wrap
            if (leg.isTransPacific) {
              return (
                <Line
                  key={leg.id}
                  from={leg.fromLoc}
                  to={leg.toLoc}
                  stroke={strokeColor}
                  strokeWidth={strokeWidth}
                  strokeLinecap="round"
                  className="cursor-pointer hover:opacity-100 opacity-80 transition-opacity"
                  onClick={() => {
                    if (onSelectService && leg.serviceObjs.length > 0) {
                      onSelectService(leg.serviceObjs[0]);
                    } else {
                      setSelectedCorridor(leg);
                    }
                  }}
                />
              );
            }

            const pathD = arcPath(leg.p1, leg.p2, leg.isInterRegional ? 0.16 : 0.08);

            return (
              <g
                key={leg.id}
                className="cursor-pointer"
                onClick={() => {
                  if (onSelectService && leg.serviceObjs.length > 0) {
                    onSelectService(leg.serviceObjs[0]);
                  } else {
                    setSelectedCorridor(leg);
                  }
                }}
              >
                {/* Glow underlay for high load */}
                {isHigh && (
                  <path
                    d={pathD}
                    fill="none"
                    stroke={strokeColor}
                    strokeWidth={strokeWidth + 2.0}
                    strokeOpacity={0.2}
                    strokeLinecap="round"
                  />
                )}
                {/* Main service corridor stroke in identical region color */}
                <path
                  d={pathD}
                  fill="none"
                  stroke={strokeColor}
                  strokeWidth={strokeWidth}
                  strokeOpacity={0.85}
                  strokeLinecap="round"
                />
              </g>
            );
          })}

          {/* ── REGION VIEW PORTS LAYER (Filtered to active region) ── */}
          {!inspectedService && showPorts && Object.entries(portCoords).map(([portId, coords]) => {
            const location = [coords[1], coords[0]];
            const region = portRegionMap[portId] || 'asia';

            // Filter if specific region selected
            if (regionFilter && regionFilter !== 'world') {
              if (!matchesRegion(region, regionFilter)) return null;
            }

            const regionColor = getRegionColor(region);

            return (
              <Marker
                key={portId}
                coordinates={location}
                onClick={() => setClickedPort(portId)}
              >
                <circle r={2.5} fill={regionColor} fillOpacity={0.85} className="cursor-pointer hover:r-4 transition-all" />
                <circle r={5} fill={regionColor} fillOpacity={0.2} />
              </Marker>
            );
          })}

          {/* ── Key Port Labels (Filtered to active region) ── */}
          {!inspectedService && KEY_PORT_LABELS.map((p) => {
            if (regionFilter && regionFilter !== 'world') {
              if (!matchesRegion(p.region, regionFilter)) return null;
            }
            return (
              <Marker key={p.id} coordinates={p.coords}>
                <circle r={3.5} fill={getRegionColor(p.region)} fillOpacity={0.9} />
                <text
                  x={0}
                  y={-8}
                  textAnchor="middle"
                  fontSize="6.5"
                  fill="#e2e8f0"
                  fontWeight="700"
                  fontFamily="monospace"
                  letterSpacing="0.08em"
                  style={{ pointerEvents: "none", textShadow: "0 0 4px #000" }}
                >
                  {p.label}
                </text>
              </Marker>
            );
          })}

          {/* Cape of Good Hope Label */}
          {(!regionFilter || regionFilter === 'world' || matchesRegion('africa', regionFilter)) && !inspectedService && (
            <Marker coordinates={[18.47, -34.35]}>
              <text
                x={0}
                y={10}
                textAnchor="middle"
                fontSize="6"
                fill="#94a3b8"
                fontWeight="600"
                fontFamily="monospace"
                letterSpacing="0.1em"
                style={{ pointerEvents: "none", textShadow: "0 0 3px #000" }}
              >
                CAPE OF GOOD HOPE
              </text>
            </Marker>
          )}
        </ComposableMap>
      </div>

      {/* ── INTERACTIVE SERVICE CORRIDOR INSPECTOR POPUP ── */}
      {selectedCorridor && !inspectedService && (
        <div className="absolute top-12 left-6 z-20 p-3 rounded-lg bg-black/90 border border-cyan-500/50 backdrop-blur-md min-w-[210px] text-left font-mono shadow-2xl">
          <div className="flex justify-between items-center pb-1.5 border-b border-white/10 mb-2">
            <span className="text-[8px] text-cyan-400 font-bold uppercase tracking-widest">SERVICE CORRIDOR</span>
            <button
              type="button"
              onClick={() => setSelectedCorridor(null)}
              className="text-slate-400 hover:text-white text-xs px-1"
            >
              ✕
            </button>
          </div>
          <div className="text-sm font-bold text-white mb-2 tracking-wide">
            {selectedCorridor.from} → {selectedCorridor.to}
          </div>
          <div className="space-y-1 text-[9px]">
            <div className="flex justify-between">
              <span className="text-slate-400">SERVICES:</span>
              <span className="text-slate-100 font-bold">{selectedCorridor.service_count}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">TOTAL LOAD:</span>
              <span className="text-emerald-400 font-bold">{selectedCorridor.total_load.toLocaleString()} TEU</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">AVG LOAD:</span>
              <span className="text-slate-200">{selectedCorridor.avg_load.toLocaleString()} TEU</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">REGIONS:</span>
              <span className="text-cyan-400">{selectedCorridor.regions.join(', ')}</span>
            </div>
          </div>
          <div className="mt-2 pt-2 border-t border-white/10">
            <div className="text-[7.5px] text-slate-400 uppercase tracking-widest mb-1">SERVICES (CLICK TO INSPECT)</div>
            <div className="text-[8.5px] text-slate-300 space-y-1 max-h-20 overflow-y-auto">
              {selectedCorridor.serviceObjs.slice(0, 6).map((s, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => {
                    if (onSelectService) onSelectService(s);
                    setSelectedCorridor(null);
                  }}
                  className="w-full text-left truncate text-cyan-300 hover:text-white hover:underline block"
                >
                  ▶ {s.id} ({s.ports.join('→')})
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── PORT INSPECTION POPUP ── */}
      {clickedPort && (
        <div className="absolute bottom-20 left-6 z-20 p-2.5 rounded-lg bg-black/90 border border-emerald-500/50 backdrop-blur-md min-w-[160px] text-left font-mono">
          <div className="flex justify-between items-center pb-1 border-b border-white/10 mb-1.5">
            <span className="text-[8px] text-emerald-400 font-bold uppercase tracking-wider">PORT {clickedPort}</span>
            <button type="button" onClick={() => setClickedPort(null)} className="text-slate-400 hover:text-white text-xs">✕</button>
          </div>
          <div className="text-[9px] text-slate-200 font-semibold">{getPortName(clickedPort)}</div>
          <div className="text-[9px] text-slate-300 mt-0.5">Region: <span className="text-cyan-400 font-semibold">{portRegionMap[clickedPort] || 'Asia'}</span></div>
          <div className="text-[9px] text-slate-300 mt-0.5">Coordinates: <span className="text-slate-400">{portCoords[clickedPort] ? `${portCoords[clickedPort][0]}, ${portCoords[clickedPort][1]}` : 'Derived'}</span></div>
        </div>
      )}

      {/* ── ROUTE LEGEND OVERLAY (Bottom-Left) ── */}
      <div className="absolute bottom-3 left-3 z-10 p-2.5 rounded bg-black/80 backdrop-blur-md border border-white/10 min-w-[210px] pointer-events-auto">
        <div className="flex justify-between items-center mb-1.5 pb-1 border-b border-white/10">
          <span className="text-[8px] text-slate-400 font-mono tracking-widest uppercase font-bold">ROUTE LEGEND</span>
          <span className="text-[8px] font-mono text-emerald-400 font-bold">
            {inspectedService ? 'SINGLE SERVICE' : `${String(regionFilter).toUpperCase()} (${services.length})`}
          </span>
        </div>

        {inspectedService ? (
          <div className="space-y-1 text-[8.5px]">
            <div className="flex justify-between"><span className="text-slate-400">SERVICE:</span><span className="text-cyan-400 font-bold">{inspectedService.id}</span></div>
            <div className="flex justify-between"><span className="text-slate-400">ROUTE:</span><span className="text-slate-100 font-semibold">{inspectedService.ports.join(' → ')}</span></div>
            <div className="flex justify-between"><span className="text-slate-400">VESSEL:</span><span className="text-slate-200">{inspectedService.vessel_class}</span></div>
            <div className="flex justify-between"><span className="text-slate-400">LOAD:</span><span className="text-emerald-400 font-bold">{fmtNum(inspectedService.load)} TEU</span></div>
            <div className="flex justify-between"><span className="text-slate-400">PROFIT:</span><span className="text-cyan-300 font-bold">{fmtUsd(inspectedService.weekly_profit)}</span></div>
          </div>
        ) : (
          <>
            <div className="flex items-center gap-2 mb-1">
              <div className="w-4 h-[2px] bg-amber-400" />
              <span className="text-[8.5px] text-amber-300 font-semibold">High-Load Cross-Region</span>
            </div>
            <div className="flex items-center gap-2 mb-1">
              <div className="w-4 h-[2.5px] bg-emerald-400" />
              <span className="text-[8.5px] text-emerald-300">High Load (&gt;30K TEU)</span>
            </div>
            <div className="flex items-center gap-2 mb-1">
              <div className="w-4 h-[1.5px] bg-cyan-400" />
              <span className="text-[8.5px] text-cyan-300">Medium Load (&gt;15K TEU)</span>
            </div>
            <div className="flex items-center gap-2 mb-2">
              <div className="w-4 h-[1px] bg-slate-500" />
              <span className="text-[8.5px] text-slate-400">Standard Selected Flow</span>
            </div>

            {/* Top corridors list */}
            <div className="text-[7.5px] text-slate-500 font-mono uppercase tracking-wider mb-1">TOP ACTIVE CORRIDORS:</div>
            {topCorridors.map((c, i) => (
              <div key={i} className="flex items-center gap-1.5 text-[8.5px] text-slate-300 py-0.5">
                <span className="text-emerald-400">•</span>
                <span className="font-semibold">{c.from}→{c.to}:</span>
                <span className="text-cyan-300">{fmtNum(c.total_load)} TEU</span>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
