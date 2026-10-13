export default function PipeNode({ x, y, w = 150, h, color, lbl, tit, desc, pills = [], active, onClick }) {
  return (
    <div onClick={onClick} style={{
      position: "absolute", left: x, top: y, width: w, height: h || "auto",
      background: active ? `${color}18` : "rgba(255,255,255,0.03)",
      border: `1px solid ${active ? color + "66" : "rgba(255,255,255,0.08)"}`,
      borderLeft: `3px solid ${color}`,
      borderRadius: 6, cursor: "pointer", padding: "9px 10px 8px",
      boxShadow: active ? `0 0 18px ${color}25` : "0 2px 8px rgba(0,0,0,0.25)",
      transition: "all 0.2s", zIndex: 10, overflow: "hidden",
    }}>
      <div style={{ fontSize: 7.5, fontWeight: 700, letterSpacing: "1.2px", textTransform: "uppercase", color, marginBottom: 3, fontFamily: "monospace", opacity: 0.85, lineHeight: 1.3 }}>{lbl}</div>
      <div style={{ fontSize: 10, fontWeight: 800, color: "rgba(255,255,255,0.92)", marginBottom: 4, lineHeight: 1.2, fontFamily: "monospace", letterSpacing: "0.03em" }}>{tit}</div>
      {desc && <div style={{ fontSize: 8, color: "rgba(255,255,255,0.42)", lineHeight: 1.55, whiteSpace: "pre-line" }}>{desc}</div>}
      {pills.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 3, marginTop: 6 }}>
          {pills.map(p => <span key={p} style={{ fontSize: 7, padding: "2px 5px", borderRadius: 3, background: `${color}18`, color, border: `1px solid ${color}33`, fontWeight: 700, fontFamily: "monospace" }}>{p}</span>)}
        </div>
      )}
    </div>
  );
}
