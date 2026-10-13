export const BENCHMARKS = {
  weeklyProfit: { target: 500_000_000, label: "Weekly Profit Target", higher: true },
  coverage:      { target: 70.0,       label: "Demand Coverage",      higher: true },
  margin:        { target: 20.0,       label: "Profit Margin",       higher: true },
  services:      { target: 450,        label: "Services Deployed",   higher: true },
  convergence:   { target: 0.970,      label: "Convergence Score",   higher: true },
};

export default function BenchmarkBadge({ value, benchmark, compact }) {
  if (value == null || benchmark == null) return null;
  const isMet = value >= benchmark.target;
  if (compact) {
    return (
      <span className="text-[10px] font-mono" style={{ color: isMet ? "#10b981" : "#ef4444" }}>
        {isMet ? "✓" : "▼"}
      </span>
    );
  }
  return (
    <span className="text-[10px] px-1.5 py-0.5 rounded font-mono ml-2"
      style={{ background: isMet ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.15)", color: isMet ? "#10b981" : "#ef4444" }}>
      {isMet ? "● On Target" : "▼ Below Target"}
    </span>
  );
}
