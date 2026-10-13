export default function ProgressBar({ value, max = 100, color, animated = true }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="w-full h-1.5 rounded-full bg-white/10 overflow-hidden">
      <div
        className={`h-full rounded-full transition-all duration-1000 ${animated ? "" : ""}`}
        style={{ width: `${pct}%`, background: `linear-gradient(90deg, ${color}aa, ${color})`, boxShadow: `0 0 8px ${color}66` }}
      />
    </div>
  );
}
