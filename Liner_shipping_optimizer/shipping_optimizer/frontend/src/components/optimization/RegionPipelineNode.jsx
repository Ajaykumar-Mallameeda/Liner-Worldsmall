import { fmt, fmtNum } from '../../utils/formatters.js';

export default function RegionPipelineNode({ x, y, W, H, region, liveData, stages, tick, active, onClick }) {
  const color = region.color;
  const gen = liveData.generated || 0;
  const flt = liveData.filtered || 0;
  const sel = liveData.selected || 0;
  const stageActive = [gen > 0, flt > 0, flt > 0, sel > 0, sel > 0];
  const litIdx = gen > 0 ? Math.floor(tick / 18) % 5 : -1;
  return (
    <div onClick={onClick} style={{
      position: "absolute", left: x, top: y, width: W, height: H,
      border: `1px solid ${active ? color + "77" : "rgba(255,255,255,0.07)"}`,
      borderLeft: `4px solid ${color}`,
      borderRadius: 6,
      background: active ? `${color}12` : "rgba(255,255,255,0.025)",
      cursor: "pointer",
      boxShadow: active ? `0 0 18px ${color}22` : "0 2px 8px rgba(0,0,0,0.15)",
      transition: "all 0.2s", zIndex: 10, overflow: "hidden",
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "5px 11px 4px", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div style={{ width: 5, height: 5, borderRadius: "50%", backgroundColor: color, boxShadow: `0 0 5px ${color}`, flexShrink: 0 }} />
          <div>
            <div style={{ fontSize: 6.5, fontWeight: 700, letterSpacing: "1px", color, fontFamily: "monospace", opacity: 0.8 }}>REGIONAL AGENT — SELF-CONTAINED PIPELINE</div>
            <div style={{ fontSize: 10, fontWeight: 800, color: "rgba(255,255,255,0.9)", fontFamily: "monospace", lineHeight: 1.1 }}>{region.name}</div>
          </div>
        </div>
        <div style={{ textAlign: "right", fontSize: 8, color: "rgba(255,255,255,0.5)", fontFamily: "monospace" }}>
          <div>{liveData.coverage != null ? `${liveData.coverage.toFixed(1)}% cov` : "—"}</div>
          <div style={{ color }}>{liveData.services || "—"} svc</div>
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 3, padding: "6px 11px 5px" }}>
        {stages.map((s, i) => {
          const isLit = stageActive[i] && i === litIdx;
          const isOn  = stageActive[i];
          return (
            <div key={s.id} style={{ display: "flex", alignItems: "center", flex: 1, gap: 3 }}>
              <div style={{
                flex: 1, padding: "3px 5px", borderRadius: 4, textAlign: "center",
                fontSize: 7.5, fontWeight: 800, fontFamily: "monospace",
                border: `1.5px solid ${isLit ? "transparent" : s.color + "44"}`,
                background: isLit ? s.color : (isOn ? s.color + "18" : "rgba(255,255,255,0.04)"),
                color: isLit ? "#fff" : (isOn ? s.color : "rgba(255,255,255,0.28)"),
                boxShadow: isLit ? `0 0 10px ${s.color}` : "none",
                transform: isLit ? "scale(1.06)" : "scale(1)",
                transition: "all 0.3s", letterSpacing: "0.4px",
              }}>
                <div>{s.lbl}</div>
                {i === 0 && gen > 0 && <div style={{ fontSize: 6, opacity: 0.8 }}>{fmtNum(gen)}</div>}
                {i === 1 && flt > 0 && <div style={{ fontSize: 6, opacity: 0.8 }}>{fmtNum(flt)}</div>}
                {i === 3 && sel > 0 && <div style={{ fontSize: 6, opacity: 0.8 }}>{fmtNum(sel)}</div>}
                {i === 4 && liveData.profit && <div style={{ fontSize: 6, opacity: 0.8 }}>{fmt(liveData.profit)}</div>}
              </div>
              {i < stages.length - 1 && <div style={{ color: "rgba(255,255,255,0.2)", fontSize: 9, flexShrink: 0 }}>›</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
