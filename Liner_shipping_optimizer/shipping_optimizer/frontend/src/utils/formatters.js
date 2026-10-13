export const fmt = (n) => {
  if (n == null || n !== n) return '—';
  const num = Number(n);
  const neg = num < 0;
  const abs = Math.abs(num);
  let s = abs >= 1e9 ? `$${(abs / 1e9).toFixed(2)}B` : abs >= 1e6 ? `$${(abs / 1e6).toFixed(1)}M` : abs >= 1e3 ? `$${(abs / 1e3).toFixed(0)}K` : `$${Math.round(abs).toLocaleString()}`;
  return neg ? `-${s}` : s;
};

export const fmtNum = (n) => (n != null ? n.toLocaleString() : '—');
export const fmtUsd = (n) => {
  if (n == null || n !== n) return '—';
  const num = Number(n);
  const neg = num < 0;
  const abs = Math.abs(num);
  let s = abs >= 1e9 ? `$${(abs / 1e9).toFixed(2)}B` : abs >= 1e6 ? `$${(abs / 1e6).toFixed(1)}M` : abs >= 1e3 ? `$${(abs / 1e3).toFixed(0)}K` : `$${Math.round(abs).toLocaleString()}`;
  return neg ? `-${s}` : s;
};
export const fmtPct = (n, d = 1) => (n != null ? `${Number(n).toFixed(d)}%` : '—');
export const fmtTs = (ts) => {
  if (!ts) return '—';
  try { return new Date(ts).toISOString().replace('T', ' ').slice(0, 19) + ' UTC'; }
  catch (_) { return String(ts); }
};

export const parseStrategyCode = (raw) => {
  if (!raw) return '—';
  const m = raw.match(/Strategy[:\s]+([A-Z])/i);
  return m ? `Strategy ${m[1]}` : raw.split('\n')[0].slice(0, 20);
};

export const parseStrategyReasons = (raw) => {
  if (!raw) return [];
  return raw
    .split('\n')
    .filter((l) => l.trim().startsWith('Reason'))
    .map((l) => l.replace(/^Reason\s*\d+:\s*/i, '').trim());
};

export const hexToRgba = (hex, alpha) => {
  if (!hex || hex[0] !== '#') return `rgba(0, 212, 255, ${alpha})`;
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};
