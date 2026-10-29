/**
 * PortIntelligence.jsx
 * --------------------
 * Port Intelligence & Raw Dataset Infrastructure Console.
 *
 * Data Integration:
 * - SOURCE A: the run on screen (pipeline_output.json): hub ports per regional agent, port calls of the plan.
 * - SOURCE B: the raw files the engine read for that run's dataset (ports.csv, dist_dense.csv, demand and
 *   fleet files; see services/rawDatasetService.js), served read-only under /data/raw/<dataset>/.
 *
 * Every number on this page comes from one of those two sources. A file that does not load shows
 * "not found" and its figures show "—"; nothing falls back to WorldSmall constants.
 */

import React, { useState, useEffect, useMemo } from 'react';
import { useOptimizationState } from '../../hooks/useOptimizationState.js';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import { Stat, Tag, Dot, Provenance } from '../../components/console/p12.jsx';
import { fetchAndParseRawDatasets, rawFilesFor } from '../../services/rawDatasetService.js';
import { getPortName } from '../../utils/portLookup.js';
import { portGeoRegion } from '../../utils/geoRegion.js';
import { getRegionColor } from '../../components/map/WorldMap.jsx';
import { fmtNum } from '../../utils/formatters.js';
import { datasetKeyOf } from '../../runtime/consoleSelectors.js';
import PortOutsideData from '../../components/console/PortOutsideData.jsx';
import { useTransshipment } from '../../services/transshipmentData.js';
import { hubAt } from '../../utils/transshipment.js';

const EM = '—';
const n0 = (v) => (v == null || Number.isNaN(Number(v)) ? EM : fmtNum(Math.round(Number(v))));

function FileStatus({ part }) {
  if (!part || part.status === 'loading') return <Tag variant="muted">LOADING</Tag>;
  if (part.status === 'healthy') return <Tag variant="good">PARSED</Tag>;
  return <Tag variant="warn">NOT FOUND</Tag>;
}

function Quadrant({ title, color, part, children, foot }) {
  return (
    <div className="p-3 bg-white/[0.02] border border-white/5 flex flex-col justify-between min-w-0">
      <div>
        <div className="flex justify-between items-center gap-2 pb-1.5 border-b border-white/5 mb-2">
          <span className="text-[12px] font-bold uppercase tracking-widest flex items-center gap-1.5 min-w-0 truncate" style={{ color }}>
            <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: color }} />
            {title}
          </span>
          <FileStatus part={part} />
        </div>
        <div className="grid grid-cols-2 gap-2 text-[12px]">{children}</div>
      </div>
      {foot && <div className="pt-2 mt-2 border-t border-white/5 text-[12px] text-slate-400">{foot}</div>}
    </div>
  );
}

function Cell({ k, v, accent }) {
  return (
    <div className="min-w-0">
      <span className="text-slate-400 block text-[12px] uppercase">{k}</span>
      <span className={`font-bold text-[13px] ${accent || 'text-slate-100'}`}>{v}</span>
    </div>
  );
}

export default function PortIntelligence({
  maritimeOverview,
  runtime: runtimeProp,
}) {
  const hookState = useOptimizationState();
  const opt = (runtimeProp && runtimeProp.global) ? runtimeProp : hookState;
  const rawData = opt?.raw || {};
  const services = opt?.global?.selected_services || rawData.selected_services || [];
  const datasetKey = datasetKeyOf(opt);
  const spec = rawFilesFor(datasetKey);

  const [rawDatasets, setRawDatasets] = useState(null);
  const [selectedHub, setSelectedHub] = useState(null);
  // Cargo that actually changes ship at each port (the plan's routed flows): does a designated hub work as one?
  const transship = useTransshipment(opt);

  // The raw files of the run's dataset (static files: loaded once per dataset, no polling).
  useEffect(() => {
    let cancelled = false;
    setRawDatasets(null);
    fetchAndParseRawDatasets(datasetKey)
      .then((data) => { if (!cancelled) setRawDatasets(data); })
      .catch(() => { /* statuses stay "loading" -> shown as not found below */ });
    return () => { cancelled = true; };
  }, [datasetKey]);

  // Port calls of the plan: how many selected services call each port.
  const callsByPort = useMemo(() => {
    const m = new Map();
    services.forEach((s) => new Set(s.ports || []).forEach((p) => m.set(p, (m.get(p) || 0) + 1)));
    return m;
  }, [services]);

  // SOURCE A: hub ports per regional agent (regional_results[].hub_ports).
  const hubPortsList = useMemo(() => {
    const regionalResults = rawData.regional_results || [];
    const hubs = [];
    const seen = new Set();
    regionalResults.forEach((r) => {
      (r.hub_ports || r.hubs || []).forEach((code) => {
        if (seen.has(code)) return;
        seen.add(code);
        const geo = portGeoRegion(code);
        hubs.push({
          code,
          name: getPortName(code),
          agent: r.region || r.name || null,
          geo,
          color: getRegionColor(geo || r.region),
          calls: callsByPort.get(code) || 0,
        });
      });
    });
    return hubs;
  }, [rawData.regional_results, callsByPort]);

  const busiestPorts = useMemo(() => (
    [...callsByPort.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12)
  ), [callsByPort]);

  const portsPart = rawDatasets?.ports;
  const distPart = rawDatasets?.distance;
  const demandPart = rawDatasets?.demand;
  const fleetPart = rawDatasets?.fleet;
  const portsInDataset = portsPart?.status === 'healthy' ? portsPart.records : null;
  const portsInPlan = callsByPort.size || null;
  const fleetClasses = fleetPart?.metrics?.classes || [];
  const fleetCount = fleetPart?.status === 'healthy' ? fleetPart.metrics.totalVessels : null;
  const runLabel = opt?.source?.label || opt?.global?.run_id || EM;
  const maritimeOn = !!maritimeOverview?.enabled;
  const files = [
    ['ports.csv', portsPart, portsPart?.records, 'UNLocode, name, country, lon/lat, draft, port costs'],
    [spec?.demand || 'demand file', demandPart, demandPart?.records, 'origin, destination, FFE/week, revenue'],
    ['dist_dense.csv', distPart, distPart?.records, 'from, to, distance (nm)'],
    [spec?.fleet || 'fleet file', fleetPart, fleetPart?.records, 'vessel class, quantity'],
  ];

  return (
    <div className="cx-page-body space-y-3 font-mono">
      <PageHead
        section="Intelligence"
        eyebrow="Port Network & Infrastructure"
        title="Port Intelligence"
        subtitle={`Ports of the ${spec ? spec.dir : datasetKey} dataset, the hub ports each regional agent used, the ports the plan calls, and the raw files the engine read.`}
        pills={[
          { tone: 'available', label: `RUN: ${runLabel}` },
          { tone: portsInDataset != null ? 'converged' : 'no_data', label: `${portsInDataset ?? EM} PORTS IN DATASET` },
          { tone: hubPortsList.length ? 'selected' : 'no_data', label: `${hubPortsList.length} HUB PORTS` },
          { tone: maritimeOn ? 'available' : 'unknown', label: maritimeOn ? 'MARITIME: ON' : 'MARITIME: OFF' },
        ]}
      />

      {/* KPI cards */}
      <div className="grid grid-cols-12 gap-3">
        <div className="col-span-12 sm:col-span-6 xl:col-span-3">
          <InstrumentPanel title="Ports" right="ports.csv">
            <Stat k="ports" v={n0(portsInDataset)} variant="accent" sub={portsPart?.metrics?.uniqueCountries != null ? `${portsPart.metrics.uniqueCountries} countries` : 'in the dataset'} />
          </InstrumentPanel>
        </div>
        <div className="col-span-12 sm:col-span-6 xl:col-span-3">
          <InstrumentPanel title="Ports In Plan" right="selected services">
            <Stat k="called" v={n0(portsInPlan)} variant="good" sub={portsInDataset ? `${((portsInPlan || 0) / portsInDataset * 100).toFixed(0)}% of dataset ports are called` : 'ports called by at least one service'} />
          </InstrumentPanel>
        </div>
        <div className="col-span-12 sm:col-span-6 xl:col-span-3">
          <InstrumentPanel title="Hub Ports" right="regional_results">
            <Stat k="hubs" v={fmtNum(hubPortsList.length)} variant="good" sub="hub_ports of the regional agents" />
          </InstrumentPanel>
        </div>
        <div className="col-span-12 sm:col-span-6 xl:col-span-3">
          <InstrumentPanel title="Fleet" right={spec?.fleet || 'fleet file'}>
            <Stat k="vessels" v={n0(fleetCount)} variant="accent" sub={fleetClasses.length ? `${fleetClasses.length} vessel classes available` : 'fleet file not loaded'} />
          </InstrumentPanel>
        </div>
      </div>

      {/* Hub ports + busiest ports */}
      <div className="grid grid-cols-12 gap-3 items-stretch">
        <div className="col-span-12 xl:col-span-6 flex flex-col">
          <InstrumentPanel title="Hub Ports" right={`${hubPortsList.length} HUBS · REGION BY PORT LOCATION · TEU = CARGO CHANGING SHIP THERE`} bodyPadding="flush">
            {hubPortsList.length === 0 ? (
              <div className="cx-compact-empty">This run lists no hub ports for its regional agents.</div>
            ) : (
              <div style={{ maxHeight: 320, overflowY: 'auto' }} className="divide-y divide-white/5">
                {hubPortsList.map((hb) => {
                  const isSelected = selectedHub === hb.code;
                  return (
                    <button
                      type="button"
                      key={hb.code}
                      onClick={() => setSelectedHub(isSelected ? null : hb.code)}
                      aria-pressed={isSelected}
                      className={`w-full text-left text-[12px] hover:bg-white/[0.04] flex items-center justify-between gap-2 p-2 px-3 ${isSelected ? 'bg-cyan-950/40' : ''}`}
                    >
                      <span className="flex items-center gap-2 min-w-0">
                        <span className="w-2 h-2 rounded-full shrink-0" style={{ background: hb.color }} />
                        <span className="font-bold text-white tracking-wider shrink-0">{hb.code}</span>
                        <span className="text-slate-300 truncate">{hb.name !== hb.code ? hb.name : ''}</span>
                      </span>
                      <span className="flex items-center gap-1.5 shrink-0">
                        <span className="px-1.5 py-0.5 font-semibold uppercase tracking-wider" style={{ background: `${hb.color}20`, color: hb.color }}>{hb.geo || EM}</span>
                        <span className="px-1.5 py-0.5 bg-white/10 text-slate-300" title="Regional agent that uses this hub (optimizer label)">agent {hb.agent || EM}</span>
                        <span className="px-1.5 py-0.5 text-slate-300 w-[86px] text-right" title="Selected services calling this port">{hb.calls} services</span>
                        {transship.model && (() => {
                          const h = hubAt(transship.model, hb.code);
                          return <span className={`px-1.5 py-0.5 w-[118px] text-right ${h ? 'text-slate-100' : 'text-slate-500'}`} title={h ? `${fmtNum(Math.round(h.teu))} TEU a week change ship here${h.cost != null ? `, transshipment ${fmtNum(Math.round(h.cost))} USD a week` : ''} (Network → Transshipment)` : 'No routed cargo changes ship here in this plan'}>{h ? `${fmtNum(Math.round(h.teu))} TEU transfer` : 'no transfers'}</span>;
                        })()}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </InstrumentPanel>
        </div>

        <div className="col-span-12 xl:col-span-6 flex flex-col">
          <InstrumentPanel title="Busiest Ports In The Plan" right="SERVICES CALLING" bodyPadding="flush">
            {busiestPorts.length === 0 ? (
              <div className="cx-compact-empty">No selected services in this run.</div>
            ) : (
              <div style={{ maxHeight: 320, overflowY: 'auto' }} className="divide-y divide-white/5">
                {busiestPorts.map(([code, calls]) => {
                  const geo = portGeoRegion(code);
                  const color = getRegionColor(geo);
                  const pct = services.length ? (calls / services.length) * 100 : 0;
                  return (
                    <div key={code} className="text-[12px] grid items-center gap-2 p-2 px-3" style={{ gridTemplateColumns: 'minmax(0, 1fr) minmax(80px, 160px) 70px' }}>
                      <span className="flex items-center gap-2 min-w-0">
                        <span className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
                        <span className="font-bold text-white shrink-0">{code}</span>
                        <span className="text-slate-300 truncate">{getPortName(code) !== code ? getPortName(code) : ''}</span>
                      </span>
                      <span className="h-1.5 bg-white/5" aria-hidden="true"><span className="block h-full" style={{ width: `${pct}%`, background: color }} /></span>
                      <span className="text-right text-slate-200">{calls} / {services.length}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </InstrumentPanel>
        </div>
      </div>

      {/* Raw dataset metrics */}
      <InstrumentPanel title="Raw Dataset Files" right={spec ? `data/raw/${spec.dir}` : `unknown dataset ${datasetKey}`} bodyPadding="normal">
        <div className="grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-4 gap-3">
          <Quadrant title="Ports · ports.csv" color="#22d3ee" part={portsPart}
            foot={portsPart?.metrics?.coordCompleteness ? `${portsPart.metrics.coordCompleteness} of ports have coordinates` : null}>
            <Cell k="records" v={n0(portsPart?.records)} />
            <Cell k="countries" v={n0(portsPart?.metrics?.uniqueCountries)} />
            <Cell k="cabotage regions" v={n0(portsPart?.metrics?.cabotageRegions)} />
            <Cell k="called by plan" v={n0(portsInPlan)} accent="text-cyan-300" />
          </Quadrant>
          <Quadrant title="Distances · dist_dense.csv" color="#c084fc" part={distPart}>
            <Cell k="directed pairs" v={n0(distPart?.records)} />
            <Cell k="avg distance" v={distPart?.metrics?.avgDistance != null ? `${n0(distPart.metrics.avgDistance)} nm` : EM} accent="text-purple-300" />
            <Cell k="min distance" v={distPart?.metrics?.minDistance != null ? `${n0(distPart.metrics.minDistance)} nm` : EM} />
            <Cell k="max distance" v={distPart?.metrics?.maxDistance != null ? `${n0(distPart.metrics.maxDistance)} nm` : EM} />
          </Quadrant>
          <Quadrant title={`Demand · ${spec?.demand || 'file'}`} color="#fbbf24" part={demandPart}
            foot={demandPart?.metrics?.totalFFE != null ? `≈ ${n0(demandPart.metrics.totalTEU)} TEU/week at 2 TEU per FFE` : null}>
            <Cell k="OD rows" v={n0(demandPart?.records)} />
            <Cell k="weekly volume" v={demandPart?.metrics?.totalFFE != null ? `${n0(demandPart.metrics.totalFFE)} FFE` : EM} accent="text-amber-300" />
            <Cell k="origins" v={n0(demandPart?.metrics?.uniqueOrigins)} />
            <Cell k="destinations" v={n0(demandPart?.metrics?.uniqueDestinations)} />
          </Quadrant>
          <Quadrant title={`Fleet · ${spec?.fleet || 'file'}`} color="#34d399" part={fleetPart}
            foot={fleetClasses.length ? fleetClasses.map((c) => `${c.name} (${c.quantity})`).join(' · ') : null}>
            <Cell k="vessels" v={n0(fleetCount)} accent="text-emerald-300" />
            <Cell k="vessel classes" v={fleetClasses.length || EM} />
          </Quadrant>
        </div>
      </InstrumentPanel>

      {/* Maritime layers + file health */}
      <div className="grid grid-cols-12 gap-3 items-stretch">
        <div className="col-span-12 xl:col-span-5 flex flex-col">
          <InstrumentPanel title="Maritime Layers" right={maritimeOn ? 'ENABLED' : 'OFF'} bodyPadding="flush">
            <div className="cx-compact-empty">
              {maritimeOn
                ? `Maritime intelligence is enabled (${maritimeOverview?.overall_state || 'state unknown'}). See Maritime Situation for AIS, weather and congestion layers.`
                : 'Maritime intelligence is off for this run (MARITIME_INTELLIGENCE_ENABLED=0). The plan was built from the dataset files alone; no AIS, weather or congestion data was used.'}
            </div>
          </InstrumentPanel>
        </div>

        <div className="col-span-12 xl:col-span-7 flex flex-col">
          <InstrumentPanel title="Data Source Health" right={`${files.length + 1} SOURCES`} bodyPadding="flush">
            <div style={{ overflowX: 'auto' }}>
              <div className="divide-y divide-white/5" style={{ minWidth: 560 }}>
                <div className="bg-[#060c14] font-bold text-[12px] tracking-wider text-slate-400" style={{ display: 'grid', gridTemplateColumns: '1.3fr 100px 110px 1.4fr', padding: '7px 12px' }}>
                  <div>SOURCE</div><div>STATUS</div><div>RECORDS</div><div style={{ textAlign: 'right' }}>FIELDS USED</div>
                </div>
                {files.map(([name, part, records, fields]) => (
                  <div key={name} className="text-[12px]" style={{ display: 'grid', gridTemplateColumns: '1.3fr 100px 110px 1.4fr', padding: '7px 12px' }}>
                    <div className="font-semibold text-slate-100 flex items-center gap-1.5 min-w-0">
                      <Dot tone={part?.status === 'healthy' ? 'available' : 'warn'} />
                      <span className="truncate">{name}</span>
                    </div>
                    <div><FileStatus part={part} /></div>
                    <div className="text-cyan-300 font-bold">{n0(records)}</div>
                    <div className="text-right text-slate-400">{fields}</div>
                  </div>
                ))}
                <div className="text-[12px]" style={{ display: 'grid', gridTemplateColumns: '1.3fr 100px 110px 1.4fr', padding: '7px 12px' }}>
                  <div className="font-semibold text-slate-100 flex items-center gap-1.5 min-w-0">
                    <Dot tone={services.length ? 'available' : 'warn'} />
                    <span className="truncate">{opt?.source?.url || 'pipeline_output.json'}</span>
                  </div>
                  <div><Tag variant={services.length ? 'good' : 'warn'}>{services.length ? 'LOADED' : 'EMPTY'}</Tag></div>
                  <div className="text-cyan-300 font-bold">{services.length} services</div>
                  <div className="text-right text-slate-400">{runLabel} · {hubPortsList.length} hubs</div>
                </div>
              </div>
            </div>
          </InstrumentPanel>
        </div>
      </div>

      <PortOutsideData />

      <Provenance
        source={`${opt?.source?.url || 'pipeline_output.json'} + data/raw/${spec ? spec.dir : datasetKey}/ (ports.csv, dist_dense.csv, ${spec?.demand || 'demand'}, ${spec?.fleet || 'fleet'})`}
        sourceStatus={rawDatasets ? 'available' : 'no_data'}
        attribution="LINERLIB dataset files + optimizer run"
        license="Internal research dataset"
        recordCount={portsInDataset ?? undefined}
      />
    </div>
  );
}
