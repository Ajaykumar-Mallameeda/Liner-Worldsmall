import { useState, useEffect, useRef } from "react";
import PipeNode from './PipeNode.jsx';
import RegionPipelineNode from './RegionPipelineNode.jsx';
import PulseDot from '../common/PulseDot.jsx';
import { fmt, fmtNum } from '../../utils/formatters.js';

const REGION_LIST = [
  { id: "asia",        name: "ASIA",        color: "#00d4ff" },
  { id: "europe",      name: "EUROPE",      color: "#7c3aed" },
  { id: "americas",    name: "AMERICAS",    color: "#10b981" },
  { id: "africa",      name: "AFRICA",      color: "#ef4444" },
  { id: "middle_east", name: "MIDDLE EAST", color: "#f59e0b" },
];

const STAGES = [
  { id: "sg", lbl: "SVC GEN",   color: "#4b8eff" },
  { id: "sf", lbl: "FILTER",    color: "#888" },
  { id: "ga", lbl: "GA L1+L2", color: "#ff9a45" },
  { id: "ml", lbl: "MILP FLOW", color: "#10b981" },
  { id: "pr", lbl: "PROFIT",    color: "#aaaaaa" },
];

const NODE_INFO = {
  "PORTS DB":    { label: "Port Database",         items: ["47 network ports worldwide", "UN/LOCODE port identifiers", "Draft · capacity · geographic coords", "Port cost & handling fees"] },
  "DEMAND OD":   { label: "OD Demand Matrix",      items: ["1,764 origin-destination lanes", "FFE/week → TEU/week (×2 conversion)", "Revenue rates per corridor", "Transit time requirements"] },
  "FLEET DB":    { label: "Fleet Database",         items: ["4 vessel size classes", "Capacity per vessel type (TEU)", "Operating cost specs", "Fuel curve: Ronen (1982) cubic v³"] },
  "DIST MATRIX": { label: "Distance Matrix",        items: ["2,162 inter-port pairs", "Nautical miles + canal flags", "Panama / Suez Canal routing", "Steaming time model"] },
  "COST MODEL":  { label: "Cost Model",             items: ["Port handling cost per TEU", "Fuel: cubic law v³ (Ronen 1982)", "Vessel operating cost / day", "Transshipment premium costs"] },
  "HIST ROUTES": { label: "Historical Routes",      items: ["Past shipping service patterns", "LINERLIB benchmark baselines", "WorldSmall, WorldLarge, Baltic", "Incumbent solution comparison"] },
  "EXT SIGNALS": { label: "External Signals",       items: ["AIS vessel tracking data", "Maritime market intelligence", "Weather routing input", "Port congestion signals"] },
  "etl":         { label: "ETL + Validation",       items: ["Schema validation (Pydantic strict)", "FFE→TEU conversion (×2.0)", "K-means geographic clustering", "Origin-only OD ownership rule", "800–2,000 candidate routes per region"] },
  "orch":        { label: "Global Orchestrator",    items: ["LLM problem analysis (GPT-OSS-120B)", "α=0.50 β=0.40 γ=0.10 initial weights", "Adaptive weight adjustment per iter", "Up to 3 feedback iterations", "Global fleet constraint: ≤300 vessels"] },
  "split":       { label: "Regional Splitter",      items: ["K-means on 47 port coordinates", "Origin-only OD demand assignment", "No demand duplication across regions", "800–2,000 candidates per region", "Demand conservation assert: Σregional==global"] },
  "aggr":        { label: "Global Aggregation",     items: ["Merges 5 regional results", "Coverage from unique served_od_map", "NOT averaged regional figures", "Max-profit region wins each OD pair", "Conservation: Σregional TEU == global TEU"] },
  "coord":       { label: "Coordinator Agent",      items: ["Coverage gap vs 70% target", "If gap > 5%: β↑, α↓ (adaptive)", "Conflict detection across regions", "Convergence score computation (0–1)", "Triggers rerun if not converged"] },
  "valid":       { label: "Route Validator",        items: ["Fleet ≤300 vessels (hard constraint)", "MILP status == Optimal required", "Flow conservation at all hub ports", "FFE/TEU consistency check (×2)", "EBIT profit margin standard verified"] },
  "bench":       { label: "Benchmark Engine",       items: ["LINERLIB WorldSmall baseline", "WorldLarge + Baltic comparison", "Coverage % vs benchmark target", "Weekly profit delta (USD)", "Fleet utilization ratio analysis"] },
  "final":       { label: "Final Optimizer",        items: ["Hard constraint validation pass", "Relative FP tolerance: 1e-6", "Service frequencies → integers", "Zero demand edge case handled", "Structured error on MILP infeasibility"] },
  "infra":       { label: "Infrastructure / Obs",   items: ["Redis Streams: async job queue", "PostgreSQL: persistent solution store", "FastAPI + Nginx: API gateway", "Prometheus: metrics collection", "Grafana: optimization dashboards", "OpenTelemetry: distributed tracing"] },
  "resil":       { label: "Resilience / Fault",     items: ["Circuit Breakers: 5 fail → 60s cooldown", "Exponential backoff retry logic", "MILP timeout fallback strategy", "Last-known-good solution cache", "Partial Recovery Engine"] },
  "output":      { label: "Optimized Network",      items: ["Service route configurations", "Vessel deployment plan", "Sailing frequency schedules", "Profit dashboard (Revenue − OpCost)", "Benchmark comparison report", "Executive summary output"] },
};

export default function PipelineView({ optimizationState }) {
  const liveRegions = Object.values(optimizationState.regions);
  const g = optimizationState.global;
  const [activeNode, setActiveNode] = useState(null);
  const [tick, setTick] = useState(0);
  const containerRef = useRef(null);
  const [containerWidth, setContainerWidth] = useState(1200);

  useEffect(() => {
    const t = setInterval(() => setTick(p => p + 1), 60);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    const updateScale = () => {
      const width = containerRef.current.clientWidth;
      if (width > 0) { setContainerWidth(width); }
    };
    const observer = new ResizeObserver(updateScale);
    observer.observe(containerRef.current);
    updateScale();
    return () => observer.disconnect();
  }, []);

  const CW = 1200;
  const CH = 548;
  const REG_TOP = 40;
  const REG_H   = 83;
  const REG_GAP = 9;
  const totalRegH = 5 * REG_H + 4 * REG_GAP;
  const midY = REG_TOP + totalRegH / 2;

  const C = {
    DATA:  0,    ETL:   105,  CTRL:  210,  REG:   330,
    RES:   650,  VAL:   770,  FIN:   890,  INFRA: 995,
    RESIL: 995,  OUT:   1100,
  };
  const CW2 = { DATA:95, ETL:95, CTRL:110, REG:310, RES:110, VAL:110, FIN:95, INFRA:95, RESIL:95, OUT:95 };

  const scale = Math.min(1, containerWidth / CW);

  const LAYERS = [
    { id: "data",  label: "DATA LAYER",                  color: "#888888", x: C.DATA,  w: CW2.DATA  },
    { id: "etl",   label: "ETL / PROCESSING",            color: "#a0a0ff", x: C.ETL,   w: CW2.ETL   },
    { id: "ctrl",  label: "GLOBAL CONTROL",              color: "#4b8eff", x: C.CTRL,  w: CW2.CTRL  },
    { id: "reg",   label: "PARALLEL REGIONAL EXECUTION", color: "#00d4ff", x: C.REG,   w: CW2.REG   },
    { id: "res",   label: "RESOLUTION",                  color: "#ef4444", x: C.RES,   w: CW2.RES   },
    { id: "val",   label: "VALIDATION + BENCHMARK",      color: "#f59e0b", x: C.VAL,   w: CW2.VAL   },
    { id: "fin",   label: "FINAL OPT",                   color: "#10b981", x: C.FIN,   w: CW2.FIN   },
    { id: "infra_resil", label: "INFRA & RESILIENCE",    color: "#00c8e0", x: C.INFRA, w: CW2.INFRA },
    { id: "out",   label: "OUTPUT",                      color: "#34d882", x: C.OUT,   w: CW2.OUT   },
  ];

  const HALF_H  = Math.floor(totalRegH * 0.45);
  const HALF_GAP = totalRegH - 2 * HALF_H;

  const activeInfo = activeNode ? (NODE_INFO[activeNode] || null) : null;
  const totalGenerated = liveRegions.reduce((s, r) => s + (r.generated || 0), 0);
  const totalFiltered  = liveRegions.reduce((s, r) => s + (r.filtered  || 0), 0);

  const DATA_R  = C.DATA  + CW2.DATA;
  const ETL_L   = C.ETL   + 4;    const ETL_R  = C.ETL  + CW2.ETL;
  const CTRL_L  = C.CTRL  + 4;    const CTRL_R = C.CTRL + CW2.CTRL;
  const REG_L   = C.REG   + 4;    const REG_R  = C.REG  + CW2.REG;
  const RES_L   = C.RES   + 4;    const RES_R  = C.RES  + CW2.RES;
  const VAL_L   = C.VAL   + 4;    const VAL_R  = C.VAL  + CW2.VAL;
  const FIN_L   = C.FIN   + 4;    const FIN_R  = C.FIN  + CW2.FIN;
  const INFRA_L = C.INFRA + 4;    const INFRA_R= C.INFRA+ CW2.INFRA;
  const RESIL_L = C.RESIL + 4;    const RESIL_R= C.RESIL+ CW2.RESIL;
  const OUT_L   = C.OUT   + 4;

  const orchCY = REG_TOP + HALF_H / 2;
  const splitCY = REG_TOP + HALF_H + HALF_GAP + HALF_H / 2;
  const aggrCY  = REG_TOP + HALF_H / 2;
  const coordCY = REG_TOP + HALF_H + HALF_GAP + HALF_H / 2;
  const infraCY = REG_TOP + HALF_H / 2;
  const resilCY = REG_TOP + HALF_H + HALF_GAP + HALF_H / 2;
  const ctrlMidX = C.CTRL + CW2.CTRL / 2;
  const resMidX  = C.RES  + CW2.RES  / 2;
  const valMidX  = C.VAL  + CW2.VAL  / 2;

  return (
    <div style={{ display: "flex", gap: 14, height: "100%", minHeight: 548 }}>
      <div ref={containerRef} style={{ flex: 1, overflow: "hidden", borderRadius: 12, background: "rgba(0,0,0,0.18)", border: "1px solid rgba(255,255,255,0.06)" }}>
        <div style={{
          position: "relative", width: CW, height: CH,
          transform: `scale(${scale})`, transformOrigin: "top left", transition: "transform 0.1s ease-out",
          marginBottom: `-${CH * (1 - scale)}px`, marginRight: `-${CW * (1 - scale)}px`
        }}>
          {LAYERS.map(l => (
            <div key={l.id} style={{
              position: "absolute", left: l.x, top: 0, width: l.w, height: CH,
              background: `${l.color}07`, borderRight: `1px dashed ${l.color}1e`,
            }}>
              <div style={{
                position: "absolute", top: 7, left: 0, right: 0, textAlign: "center",
                fontSize: 12, fontWeight: 800, letterSpacing: "1px",
                color: l.color, fontFamily: "monospace", textTransform: "uppercase", opacity: 0.75,
                whiteSpace: "nowrap", overflow: "hidden",
              }}>{l.label}</div>
            </div>
          ))}

          <svg style={{ position: "absolute", inset: 0, width: CW, height: CH, pointerEvents: "none", overflow: "visible", zIndex: 2 }}>
            <defs>
              <style>{`
                @keyframes df { to { stroke-dashoffset: -24; } }
                @keyframes dr { to { stroke-dashoffset: 24; } }
                .af { animation: df 1.4s linear infinite; }
                .ar { animation: dr 2s linear infinite; }
              `}</style>
              <marker id="ah" markerWidth="5" markerHeight="5" refX="4.5" refY="2.5" orient="auto">
                <path d="M0,0 L0,5 L5,2.5 Z" fill="rgba(255,255,255,0.28)" />
              </marker>
              <marker id="ahr" markerWidth="5" markerHeight="5" refX="4.5" refY="2.5" orient="auto">
                <path d="M0,0 L0,5 L5,2.5 Z" fill="rgba(239,68,68,0.8)" />
              </marker>
            </defs>
            <line x1={DATA_R} y1={midY} x2={ETL_L} y2={midY} stroke="rgba(255,255,255,0.14)" strokeWidth={1} strokeDasharray="5,3" className="af" markerEnd="url(#ah)" />
            <path d={`M ${ETL_R} ${midY} C ${ETL_R+14} ${midY}, ${CTRL_L-14} ${orchCY}, ${CTRL_L} ${orchCY}`} fill="none" stroke="rgba(75,142,255,0.45)" strokeWidth={1.1} strokeDasharray="6,3" className="af" markerEnd="url(#ah)" />
            <line x1={ctrlMidX} y1={REG_TOP + HALF_H} x2={ctrlMidX} y2={REG_TOP + HALF_H + HALF_GAP} stroke="rgba(75,142,255,0.3)" strokeWidth={0.9} strokeDasharray="4,3" />
            {REGION_LIST.map((r, i) => {
              const ry = REG_TOP + i * (REG_H + REG_GAP) + REG_H / 2;
              return (<path key={r.id} d={`M ${CTRL_R} ${splitCY} C ${CTRL_R+16} ${splitCY}, ${REG_L-16} ${ry}, ${REG_L} ${ry}`} fill="none" stroke={`${r.color}38`} strokeWidth={0.8} strokeDasharray="5,3" className="af" markerEnd="url(#ah)" />);
            })}
            {REGION_LIST.map((r, i) => {
              const ry = REG_TOP + i * (REG_H + REG_GAP) + REG_H / 2;
              return (<path key={r.id} d={`M ${REG_R} ${ry} C ${REG_R+16} ${ry}, ${RES_L-16} ${aggrCY}, ${RES_L} ${aggrCY}`} fill="none" stroke={`${r.color}30`} strokeWidth={0.7} strokeDasharray="5,3" className="af" />);
            })}
            <line x1={resMidX} y1={REG_TOP + HALF_H} x2={resMidX} y2={REG_TOP + HALF_H + HALF_GAP} stroke="rgba(239,68,68,0.4)" strokeWidth={0.9} strokeDasharray="4,3" />
            <path d={`M ${RES_R} ${coordCY} C ${RES_R+14} ${coordCY}, ${VAL_L-14} ${midY}, ${VAL_L} ${midY}`} fill="none" stroke="rgba(245,158,11,0.4)" strokeWidth={1.1} strokeDasharray="6,3" className="af" markerEnd="url(#ah)" />
            <line x1={valMidX} y1={REG_TOP + HALF_H} x2={valMidX} y2={REG_TOP + HALF_H + HALF_GAP} stroke="rgba(245,158,11,0.3)" strokeWidth={0.9} strokeDasharray="4,3" />
            <line x1={VAL_R} y1={midY} x2={FIN_L} y2={midY} stroke="rgba(16,185,129,0.4)" strokeWidth={1.1} strokeDasharray="6,3" className="af" markerEnd="url(#ah)" />
            <path d={`M ${FIN_R} ${midY} C ${FIN_R+12} ${midY}, ${INFRA_L-12} ${infraCY}, ${INFRA_L} ${infraCY}`} fill="none" stroke="rgba(0,200,224,0.4)" strokeWidth={1.1} strokeDasharray="6,3" className="af" markerEnd="url(#ah)" />
            <path d={`M ${FIN_R} ${midY} C ${FIN_R+12} ${midY}, ${RESIL_L-12} ${resilCY}, ${RESIL_L} ${resilCY}`} fill="none" stroke="rgba(169,120,255,0.4)" strokeWidth={1.1} strokeDasharray="6,3" className="af" markerEnd="url(#ah)" />
            <path d={`M ${INFRA_R} ${infraCY} C ${INFRA_R+12} ${infraCY}, ${OUT_L-12} ${midY}, ${OUT_L} ${midY}`} fill="none" stroke="rgba(0,200,224,0.4)" strokeWidth={1.1} strokeDasharray="6,3" className="af" markerEnd="url(#ah)" />
            <path d={`M ${RESIL_R} ${resilCY} C ${RESIL_R+12} ${resilCY}, ${OUT_L-12} ${midY}, ${OUT_L} ${midY}`} fill="none" stroke="rgba(52,216,130,0.55)" strokeWidth={1.4} strokeDasharray="6,3" className="af" markerEnd="url(#ah)" />
            <path d={`M ${resMidX} ${REG_TOP + totalRegH + 12} Q ${resMidX} ${CH - 18}, ${ctrlMidX} ${CH - 18} Q ${ctrlMidX - 30} ${CH - 18}, ${ctrlMidX} ${REG_TOP + totalRegH + 12}`} fill="none" stroke="rgba(239,68,68,0.6)" strokeWidth={1.4} strokeDasharray="8,4" className="ar" markerEnd="url(#ahr)" />
            <text x={(resMidX + ctrlMidX) / 2} y={CH - 5} fontSize="6.5" fill="rgba(239,68,68,0.65)" fontFamily="monospace" fontWeight="700" textAnchor="middle">FEEDBACK LOOP — {optimizationState.iterations.length || 3} ITERATIONS</text>
          </svg>

          {[
            { id: "PORTS DB", lbl: "Port Database", desc: "435 ports\nDraft, cost, coords", pills: ["ports.csv"] },
            { id: "DEMAND OD", lbl: "Demand Matrix", desc: "9,622 OD lanes\nFFE/wk, revenue", pills: ["demand.csv"] },
            { id: "FLEET DB", lbl: "Fleet Database", desc: "6 vessel classes\nCapacity & cost", pills: ["fleet.csv"] },
            { id: "DIST MATRIX", lbl: "Distance Matrix", desc: "62,002 pairs\nPanama/Suez flags", pills: ["dist_dense"] },
            { id: "COST MODEL", lbl: "Cost Model", desc: "Port handling\nFuel & vessel ops", pills: ["enrichment"] },
            { id: "HIST ROUTES", lbl: "Historical Routes", desc: "Past service lines\nLINERLIB baseline", pills: ["LINERLIB"] },
            { id: "EXT SIGNALS", lbl: "External Signals", desc: "AIS tracking\nWeather feeds", pills: ["API/AIS"] },
          ].map((n, i) => {
            const nodeH = Math.floor((totalRegH - 6 * 5) / 7);
            return (<PipeNode key={n.id} x={C.DATA + 5} y={REG_TOP + i * (nodeH + 5)} w={CW2.DATA - 10} h={nodeH} color="#888888" lbl={n.lbl} tit={n.id} desc={n.desc} pills={n.pills} active={activeNode === n.id} onClick={() => setActiveNode(activeNode === n.id ? null : n.id)} />);
          })}

          <PipeNode x={C.ETL + 5} y={REG_TOP} w={CW2.ETL - 10} h={totalRegH} color="#a0a0ff" lbl="Layer 2 — ETL Pipeline" tit="ETL + VALIDATION" desc={"Pydantic checks\nFFE→TEU (×2.0)\nPort clustering\nCandidate routes"} pills={["Pydantic", "K-means", "FFE→TEU"]} active={activeNode === "etl"} onClick={() => setActiveNode(activeNode === "etl" ? null : "etl")} />
          <PipeNode x={C.CTRL + 5} y={REG_TOP} w={CW2.CTRL - 10} h={HALF_H} color="#4b8eff" lbl="Layer 3 — Master Controller (LLM)" tit="GLOBAL ORCHESTRATOR" desc={"LLM analysis\nWeight tuning\nIteration control"} pills={["GPT-OSS-120B", "Iter Ctrl", "α/β/γ"]} active={activeNode === "orch"} onClick={() => setActiveNode(activeNode === "orch" ? null : "orch")} />
          <PipeNode x={C.CTRL + 5} y={REG_TOP + HALF_H + HALF_GAP} w={CW2.CTRL - 10} h={HALF_H} color="#4b8eff" lbl="Decomposition Engine" tit="REGIONAL SPLITTER" desc={"K-means split\n5 regions\nOrigin-only OD"} pills={["K-means", "Origin-only", "No Dup"]} active={activeNode === "split"} onClick={() => setActiveNode(activeNode === "split" ? null : "split")} />

          {REGION_LIST.map((r, i) => {
            const liveData = liveRegions.find(rd => rd.id === r.id) || {};
            const ry = REG_TOP + i * (REG_H + REG_GAP);
            return (<RegionPipelineNode key={r.id} x={C.REG + 5} y={ry} W={CW2.REG - 10} H={REG_H} region={r} liveData={liveData} stages={STAGES} tick={tick} active={activeNode === r.id} onClick={() => setActiveNode(activeNode === r.id ? null : r.id)} />);
          })}

          <PipeNode x={C.RES + 5} y={REG_TOP} w={CW2.RES - 10} h={HALF_H} color="#ef4444" lbl="Aggregation Layer" tit="GLOBAL AGGREGATION" desc={"Merge results\nOD uniqueness\nConservation check"} pills={["OD Unique", "Max-Profit", "Conservation"]} active={activeNode === "aggr"} onClick={() => setActiveNode(activeNode === "aggr" ? null : "aggr")} />
          <PipeNode x={C.RES + 5} y={REG_TOP + HALF_H + HALF_GAP} w={CW2.RES - 10} h={HALF_H} color="#ef4444" lbl="Decision Engine (LLM)" tit="COORDINATOR AGENT" desc={"Conflict resolution\nα/β/γ weight tuning\nFeedback loop"} pills={["Conflict Detect", "α/β/γ Tune", "Convergence"]} active={activeNode === "coord"} onClick={() => setActiveNode(activeNode === "coord" ? null : "coord")} />
          <PipeNode x={C.VAL + 5} y={REG_TOP} w={CW2.VAL - 10} h={HALF_H} color="#f59e0b" lbl="Route Validation Engine" tit="ROUTE VALIDATOR" desc={"Fleet limit ≤300\nFlow balance check\nEBIT verified"} pills={["Fleet Cap", "Flow Bal", "EBIT"]} active={activeNode === "valid"} onClick={() => setActiveNode(activeNode === "valid" ? null : "valid")} />
          <PipeNode x={C.VAL + 5} y={REG_TOP + HALF_H + HALF_GAP} w={CW2.VAL - 10} h={HALF_H} color="#f59e0b" lbl="Benchmark Comparator" tit="BENCHMARK ENGINE" desc={"LINERLIB comparison\nKPI scoring\nAcademic metrics"} pills={["WorldLarge", "Baltic", "WorldSmall"]} active={activeNode === "bench"} onClick={() => setActiveNode(activeNode === "bench" ? null : "bench")} />
          <PipeNode x={C.FIN + 5} y={REG_TOP + Math.floor(totalRegH * 0.22)} w={CW2.FIN - 10} h={Math.floor(totalRegH * 0.56)} color="#10b981" lbl="Final Optimizer" tit="FINAL OPTIMIZER" desc={"Constraint pass\nFleet ≤300 limit\nFlow balance"} pills={["Fleet ≤300", "FP 1e-6", "Flow Bal"]} active={activeNode === "final"} onClick={() => setActiveNode(activeNode === "final" ? null : "final")} />
          <PipeNode x={C.INFRA + 5} y={REG_TOP} w={CW2.INFRA - 10} h={HALF_H} color="#00c8e0" lbl="Layer 6 — Infrastructure" tit="INFRA + OBS" desc={"Redis & Postgres\nFastAPI & Nginx\nPrometheus/Grafana"} pills={["Redis", "Prometheus", "Grafana"]} active={activeNode === "infra"} onClick={() => setActiveNode(activeNode === "infra" ? null : "infra")} />
          <PipeNode x={C.RESIL + 5} y={REG_TOP + HALF_H + HALF_GAP} w={CW2.RESIL - 10} h={HALF_H} color="#a978ff" lbl="Layer 7 — Resilience" tit="RESILIENCE + FAULT" desc={"Circuit breakers\nBackoff retries\nPartial recovery"} pills={["Circ.Breaker", "Backoff", "Partial Rec"]} active={activeNode === "resil"} onClick={() => setActiveNode(activeNode === "resil" ? null : "resil")} />
          <PipeNode x={C.OUT + 5} y={REG_TOP + Math.floor(totalRegH * 0.22)} w={CW2.OUT - 10} h={Math.floor(totalRegH * 0.56)} color="#34d882" lbl="Layer 8 — Output" tit="OPTIMIZED NETWORK" desc={"Service plans\nVessel deployment\nProfit report"} pills={["Routes", "Profit", "Report"]} active={activeNode === "output"} onClick={() => setActiveNode(activeNode === "output" ? null : "output")} />
        </div>
      </div>

      <div style={{ width: 258, flexShrink: 0, display: "flex", flexDirection: "column", gap: 10, overflowY: "auto" }}>
        <div className="rounded-xl p-4" style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)", flexShrink: 0 }}>
          <div style={{ fontSize: 12, fontFamily: "monospace", color: "rgba(255,255,255,0.4)", letterSpacing: "2px", textTransform: "uppercase", marginBottom: 12 }}>Pipeline Stats</div>
          {[
            { label: "Total Runtime",       value: g.runtime ? `${g.runtime}s` : "—" },
            { label: "Feedback Iterations", value: optimizationState.iterations.length.toString() },
            { label: "Convergence Score",   value: g.convergence ? g.convergence.toFixed(3) : "—" },
            { label: "Services Generated",  value: fmtNum(totalGenerated) },
            { label: "Services Filtered",   value: fmtNum(totalFiltered) },
            { label: "Services Selected",   value: fmtNum(g.totalServices) },
            { label: "Conflicts Detected",  value: g.decision_output?.conflicts?.length?.toString() || "0" },
          ].map(({ label, value }) => (
            <div key={label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "5px 0", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
              <span style={{ fontSize: 12, color: "rgba(255,255,255,0.42)", fontFamily: "monospace" }}>{label}</span>
              <span style={{ fontSize: 12, fontFamily: "monospace", color: "rgba(255,255,255,0.9)", fontWeight: 700 }}>{value}</span>
            </div>
          ))}
        </div>

        <div className="rounded-xl p-4" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", flex: 1, minHeight: 120 }}>
          {activeInfo ? (
            <>
              <div style={{ fontSize: 12, fontFamily: "monospace", color: "rgba(255,255,255,0.4)", letterSpacing: "2px", textTransform: "uppercase", marginBottom: 8 }}>Node Detail</div>
              <div style={{ fontSize: 12, fontWeight: 700, color: "rgba(255,255,255,0.9)", fontFamily: "monospace", marginBottom: 10 }}>{activeInfo.label}</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {activeInfo.items.map((item, i) => (
                  <div key={i} style={{ fontSize: 12, color: "rgba(255,255,255,0.55)", padding: "4px 8px", background: "rgba(255,255,255,0.03)", borderRadius: 4, borderLeft: "2px solid rgba(255,255,255,0.1)", fontFamily: "monospace", lineHeight: 1.5 }}>{item}</div>
                ))}
              </div>
            </>
          ) : (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 8, height: "100%", minHeight: 80 }}>
              <div style={{ fontSize: 22, opacity: 0.25 }}>◎</div>
              <div style={{ fontSize: 12, color: "rgba(255,255,255,0.28)", fontFamily: "monospace", textAlign: "center" }}>Click any node to see details</div>
            </div>
          )}
        </div>

        <div className="rounded-xl p-4" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", flexShrink: 0 }}>
          <div style={{ fontSize: 12, fontFamily: "monospace", color: "rgba(255,255,255,0.4)", letterSpacing: "2px", textTransform: "uppercase", marginBottom: 10 }}>Feedback Loop</div>
          <div style={{ display: "flex", gap: 6 }}>
            {optimizationState.iterations.length > 0 ? optimizationState.iterations.map((it, i) => (
              <div key={i} style={{
                flex: 1, borderRadius: 6, padding: "8px 4px", textAlign: "center",
                background: it.rerun ? "rgba(239,68,68,0.1)" : "rgba(16,185,129,0.1)",
                border: `1px solid ${it.rerun ? "#ef444430" : "#10b98130"}`,
              }}>
                <div style={{ fontSize: 12, fontFamily: "monospace", color: it.rerun ? "#ef4444" : "#10b981", fontWeight: 700 }}>it.{it.iter}</div>
                <div style={{ fontSize: 12, color: it.rerun ? "#ef4444" : "#10b981", fontFamily: "monospace" }}>{it.rerun ? "RERUN" : "OK"}</div>
                <div style={{ fontSize: 12, color: "rgba(255,255,255,0.5)", fontFamily: "monospace", marginTop: 2 }}>{it.coverage.toFixed(1)}%</div>
              </div>
            )) : (
              <div style={{ color: "rgba(255,255,255,0.25)", fontSize: 12, fontFamily: "monospace", fontStyle: "italic" }}>No iteration data</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
