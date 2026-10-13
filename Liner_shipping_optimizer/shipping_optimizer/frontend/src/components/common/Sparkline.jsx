export default function Sparkline({ data, color, height = 32 }) {
  if (!data || data.length < 2) {
    return (
      <svg width="60" height={height} className="opacity-20">
        <line x1="0" y1={height/2} x2="60" y2={height/2} stroke={color || "#00d4ff"} strokeWidth="1" strokeDasharray="2,2" />
      </svg>
    );
  }

  const sortedData = [...data];
  const max = Math.max(...sortedData), min = Math.min(...sortedData);
  const range = Math.max(1, max - min);

  const trend = sortedData.length > 1
    ? (sortedData[sortedData.length - 1] > sortedData[0] ? "up" : sortedData[sortedData.length - 1] < sortedData[0] ? "down" : "flat")
    : "flat";
  const trendColor = trend === "up" ? "#10b981" : trend === "down" ? "#ef4444" : "#6b7280";
  const trendArrow = trend === "up" ? "↑" : trend === "down" ? "↓" : "—";

  const pts = sortedData.map((v, i) => {
    const x = (i / (sortedData.length - 1)) * 60;
    const y = height - ((v - min) / range) * (height - 8) - 4;
    return `${x},${y}`;
  }).join(" ");

  return (
    <svg width="60" height={height} style={{ overflow: "visible" }}>
      <defs>
        <linearGradient id={`grad-${color}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.4" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`M 0,${height} ${pts} L 60,${height} Z`} fill={`url(#grad-${color})`} opacity="0.3" />
      <polyline points={pts} fill="none" stroke={color || "#00d4ff"} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx="60" cy={height - ((sortedData[sortedData.length-1] - min) / range) * (height - 8) - 4} r="2" fill={color} />
      <text x="52" y="6" fontSize="8" fill={trendColor} fontWeight="bold" textAnchor="end">{trendArrow}</text>
    </svg>
  );
}
