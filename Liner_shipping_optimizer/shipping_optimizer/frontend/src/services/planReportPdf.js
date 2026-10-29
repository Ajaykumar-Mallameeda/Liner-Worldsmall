/**
 * planReportPdf — the one-click, one-page PDF plan report (design D12): headline KPIs, a snapshot of the plan map,
 * the revenue → profit waterfall and the service table on a single A4 landscape page. Content: utils/planReport.js;
 * map picture: services/mapSnapshot.js ('plan', the Command Center map). jsPDF loads only when a report is asked for.
 */

import { reportModel, SERVICE_COLUMNS, TABLE_ROWS } from '../utils/planReport.js';
import { snapshot } from './mapSnapshot.js';
import { toast } from './toastStore.js';
import { getMapPrefs } from './mapPrefsStore.js';
import { BASEMAPS } from '../components/map/basemaps.js';

// jsPDF's built-in Helvetica is Latin-1 (WinAnsi): map the few typographic characters the UI uses, drop the rest.
const latin = (s) => String(s ?? '').replace(/−/g, '-').replace(/→/g, '->').replace(/÷/g, '/').replace(/≤/g, '<=')
  .replace(/[–—]/g, '-').replace(/[^\x20-\xff]/g, '');
const money = (v) => {
  const a = Math.abs(v);
  const s = a >= 1e9 ? `$${(a / 1e9).toFixed(2)}B` : a >= 1e6 ? `$${(a / 1e6).toFixed(1)}M` : a >= 1e3 ? `$${Math.round(a / 1e3)}K` : `$${Math.round(a)}`;
  return v < 0 ? `-${s}` : s;
};

const INK = [15, 23, 42]; const DIM = [100, 116, 139]; const EDGE = [203, 213, 225];
const BLUE = [57, 135, 229]; const GREY = [148, 163, 184]; const RED = [220, 38, 38];

function drawWaterfall(doc, steps, x, y, w, h) {
  doc.setDrawColor(...EDGE); doc.setLineWidth(0.5);
  if (!steps.length) { doc.setFontSize(8); doc.setTextColor(...DIM); doc.text('No revenue / cost breakdown in this run.', x, y + 12); return; }
  const top = y + 16; const bottom = y + h - 26;
  const lo = Math.min(0, ...steps.map((s) => Math.min(s.from, s.to)));
  const hi = Math.max(...steps.map((s) => Math.max(s.from, s.to)));
  const Y = (v) => top + (bottom - top) * (1 - (v - lo) / (hi - lo || 1));
  const band = w / steps.length; const bw = Math.min(40, band * 0.6);
  doc.line(x, Y(0), x + w, Y(0));
  steps.forEach((s, i) => {
    const cx = x + band * i + band / 2;
    const y1 = Y(Math.max(s.from, s.to)); const y2 = Y(Math.min(s.from, s.to));
    doc.setFillColor(...(s.kind === 'total' ? (s.to < 0 ? RED : BLUE) : GREY));
    doc.rect(cx - bw / 2, y1, bw, Math.max(0.8, y2 - y1), 'F');
    if (i < steps.length - 1) {   // connector to the next step's start
      doc.setDrawColor(...EDGE); doc.setLineDashPattern([2, 2], 0);
      doc.line(cx + bw / 2, Y(s.to), cx + band - bw / 2, Y(s.to)); doc.setLineDashPattern([], 0);
    }
    doc.setFontSize(7); doc.setTextColor(...INK);
    doc.text(s.kind === 'cost' ? `-${money(s.v)}` : money(s.to), cx, y1 - 3, { align: 'center' });
    doc.setTextColor(...DIM);
    doc.text(latin(s.k === 'Vessel operating' ? 'Vessels' : s.k), cx, bottom + 11, { align: 'center' });
  });
}

/** Builds and saves the report. runtime: the console runtime (final plan); label: run label for the title. */
export async function downloadPlanReport({ runtime, bench = null, label = 'run', iteration = null, sourceFile = 'pipeline_output.json' }) {
  const model = reportModel(runtime, bench);
  if (!model.rows.length && !model.steps.length) { toast('This run has no plan to report', { tone: 'warn' }); return null; }
  const [{ jsPDF }, { autoTable }, shot] = await Promise.all([import('jspdf'), import('jspdf-autotable'), snapshot('plan')]);
  const doc = new jsPDF({ orientation: 'landscape', unit: 'pt', format: 'a4' });
  const W = doc.internal.pageSize.getWidth(); const H = doc.internal.pageSize.getHeight();
  const M = 36; const inner = W - 2 * M;
  const stamp = new Date().toISOString().slice(0, 16).replace('T', ' ');

  // Header
  doc.setTextColor(...INK); doc.setFont('helvetica', 'bold'); doc.setFontSize(16);
  doc.text('Network plan report', M, 40);
  doc.setFont('helvetica', 'normal'); doc.setFontSize(9); doc.setTextColor(...DIM);
  doc.text(latin(`${label}${iteration != null ? ` | final plan, iteration ${String(iteration).padStart(2, '0')}` : ''} | weekly figures | generated ${stamp} UTC`), M, 54);
  doc.text(latin(`Source: ${sourceFile} (engine ledger)${bench ? ` | benchmark: ${bench.n} seeds` : ''}`), W - M, 54, { align: 'right' });

  // KPI strip
  const nk = model.kpis.length; const kw = (inner - (nk - 1) * 6) / nk; const ky = 64;
  model.kpis.forEach(([k, v, sub], i) => {
    const x = M + i * (kw + 6);
    doc.setDrawColor(...EDGE); doc.setLineWidth(0.6); doc.roundedRect(x, ky, kw, 46, 3, 3, 'S');
    doc.setFontSize(7); doc.setTextColor(...DIM); doc.text(latin(k.toUpperCase()), x + 7, ky + 11);
    doc.setFont('helvetica', 'bold'); doc.setFontSize(13); doc.setTextColor(...INK); doc.text(latin(v), x + 7, ky + 28);
    doc.setFont('helvetica', 'normal'); doc.setFontSize(6.5); doc.setTextColor(...DIM);
    if (sub) doc.text(latin(sub), x + 7, ky + 39, { maxWidth: kw - 12 });
  });

  // Map snapshot (left) and waterfall (right)
  const my = 120; const mh = 232; const mw = Math.round(inner * 0.58);
  doc.setFillColor(3, 10, 20); doc.rect(M, my, mw, mh, 'F');
  if (shot) {
    const ar = shot.width / shot.height; let w = mw; let h = mw / ar;
    if (h > mh) { h = mh; w = mh * ar; }
    doc.addImage(shot.url, 'JPEG', M + (mw - w) / 2, my + (mh - h) / 2, w, h);
  } else {
    doc.setFontSize(8); doc.setTextColor(203, 213, 225);
    doc.text('Map snapshot unavailable: open Overview with the WebGL map to include it.', M + mw / 2, my + mh / 2, { align: 'center' });
  }
  doc.setFontSize(6.5); doc.setTextColor(...DIM);
  const bm = BASEMAPS[getMapPrefs().basemap] || BASEMAPS.vector;
  doc.text(latin(`Plan map as on screen (Overview): sea lanes coloured by region, width = TEU on the leg. Basemap: ${bm.label}, ${bm.attribution}.`), M, my + mh + 9, { maxWidth: mw });
  const wx = M + mw + 18; const ww = inner - mw - 18;
  doc.setFont('helvetica', 'bold'); doc.setFontSize(9); doc.setTextColor(...INK); doc.text('Revenue to profit, $ / week', wx, my + 8);
  doc.setFont('helvetica', 'normal');
  drawWaterfall(doc, model.steps, wx, my + 10, ww, mh - 10);
  if (model.costCheck) {
    doc.setFontSize(6.5); doc.setTextColor(...DIM);
    doc.text(latin(`Costs ${money(model.costCheck.costs)}; revenue - costs = profit ${money(model.costCheck.profit)}.`), wx, my + mh + 9);
  }

  // Service table: two columns of up to 16 rows
  const ty = my + mh + 20; const half = Math.ceil(Math.min(model.rows.length, TABLE_ROWS) / 2);
  const colW = (inner - 12) / 2;
  [model.rows.slice(0, half), model.rows.slice(half)].forEach((rows, k) => {
    if (!rows.length) return;
    doc.setPage(1);   // both columns on the one page
    autoTable(doc, {
      head: [SERVICE_COLUMNS], body: rows.map((r) => r.map(latin)), startY: ty, pageBreak: 'avoid', rowPageBreak: 'avoid',
      margin: { left: M + k * (colW + 12), right: W - (M + k * (colW + 12) + colW), bottom: 24 }, tableWidth: colW, theme: 'grid',
      styles: { font: 'helvetica', fontSize: 6, cellPadding: { top: 1, bottom: 1, left: 2, right: 2 }, minCellHeight: 0, textColor: INK, lineColor: EDGE, lineWidth: 0.4 },
      headStyles: { fillColor: [30, 58, 95], textColor: 255, fontStyle: 'bold' },
      columnStyles: { 2: { halign: 'right' }, 3: { halign: 'right' }, 4: { halign: 'right' }, 5: { halign: 'right' }, 6: { halign: 'right' } },
      didParseCell: (d) => { if (d.section === 'body' && d.column.index === 6 && String(d.cell.raw).startsWith('-')) d.cell.styles.textColor = RED; },
    });
  });
  doc.setFontSize(6.5); doc.setTextColor(...DIM);
  doc.text(latin(`${model.tableNote} Load = carried / offered TEU on the legs. Full list: Network > Routes & Services (CSV).`), M, H - 16);
  doc.text('Page 1 of 1', W - M, H - 16, { align: 'right' });

  const name = `${String(label).replace(/[^\w.-]+/g, '_').slice(0, 60)}_plan_report.pdf`;
  doc.save(name);
  toast(`Saved ${name}${shot ? '' : ' (without the map)'}`);
  return { pages: doc.getNumberOfPages(), map: Boolean(shot), name };
}
