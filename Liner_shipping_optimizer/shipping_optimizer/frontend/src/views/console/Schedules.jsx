/**
 * Schedules.jsx — the plan's weekly pro-forma schedules and their export (2026-10-28, feature #23).
 *
 * One row per port call: arrival and departure as weekday + time for each weekly departure, the next leg's distance,
 * sailing days and TEU. Timings: utils/proformaSchedule.js (the same leg schedule as the map's vessel replay).
 * Exports run in the browser: CSV (every call of every weekly departure) and a PDF (one table per service, jsPDF,
 * loaded on demand). Nothing is sent anywhere.
 */
import React, { useMemo, useState } from 'react';
import PageHead from '../../components/console/PageHead.jsx';
import InstrumentPanel from '../../components/console/InstrumentPanel.jsx';
import { Provenance } from '../../components/console/p12.jsx';
import { getPortName, getPortCoordinates } from '../../utils/portLookup.js';
import { fmtNum } from '../../utils/formatters.js';
import { downloadCsv } from '../../utils/exportData.js';
import { proformaSchedule, scheduleRows, weekdayTime } from '../../utils/proformaSchedule.js';
import { toast } from '../../services/toastStore.js';

const d1 = (v) => (v == null || !Number.isFinite(v) ? '—' : v.toFixed(1));
const TIMINGS = { run: 'from the run’s ledger', estimated: 'estimated (run predates per-leg timings)' };

const CSV_COLUMNS = [
  ['service', (r) => r.service], ['vessel_class', (r) => r.vessel_class], ['weekly_departure', (r) => r.weekly_departure],
  ['call', (r) => r.call], ['port', (r) => r.port], ['port_name', (r) => getPortName(r.port)],
  ['arrive', (r) => r.arrive], ['arrive_day', (r) => r.arrive_day], ['depart', (r) => r.depart], ['depart_day', (r) => r.depart_day],
  ['next_port', (r) => r.next_port], ['leg_nm', (r) => r.leg_nm], ['leg_sail_days', (r) => r.leg_sail_days], ['leg_teu', (r) => r.leg_teu],
  ['frequency_per_week', (r) => r.frequency_per_week], ['vessels', (r) => r.vessels], ['round_voyage_days', (r) => r.round_voyage_days],
  ['timings', (r) => r.timings],
];

export default function Schedules({ optimizationState = null }) {
  const services = optimizationState?.global?.selected_services || [];
  // The schedules are the plan on screen (the current run); the file name carries the export date.
  const runLabel = `plan_${new Date().toISOString().slice(0, 10)}`;
  const schedules = useMemo(() => services.map((s) => proformaSchedule(s, getPortCoordinates)).filter(Boolean)
    .sort((a, b) => String(a.id).localeCompare(String(b.id))), [services]);
  const [selId, setSelId] = useState(null);
  const sel = schedules.find((s) => s.id === selId) || schedules[0] || null;
  const estimated = schedules.some((s) => s.source === 'estimated');
  const [pdfBusy, setPdfBusy] = useState(false);

  const csv = (list, name) => downloadCsv(name, CSV_COLUMNS, list.flatMap(scheduleRows));
  const pdf = async (list, name) => {
    setPdfBusy(true);
    try {
      await downloadSchedulePdf(list, name);
    } catch (e) {
      toast(`PDF export failed: ${e?.message || e}`, { tone: 'warn', ms: 6000 });
    } finally {
      setPdfBusy(false);
    }
  };

  return (
    <div className="cx-page-body space-y-3">
      <PageHead
        section="Network"
        eyebrow="Schedules"
        title="Weekly schedules of the plan"
        subtitle="Every service as a carrier would publish it: each port call with its arrival and departure weekday, for every weekly departure. Day 0 is the first departure from the service's first port, Monday 00:00. Download them as CSV or PDF."
        pills={[
          { tone: schedules.length ? 'available' : 'no_data', label: `${schedules.length} service${schedules.length === 1 ? '' : 's'}` },
          { tone: estimated ? 'no_data' : 'available', label: estimated ? 'timings estimated' : 'ledger timings' },
        ]}
      />

      {schedules.length === 0 ? (
        <InstrumentPanel title="No schedules">
          <p className="text-[13px] text-slate-300">No plan loaded: run the optimizer, or open a run that has selected services.</p>
        </InstrumentPanel>
      ) : (
        <>
          <InstrumentPanel title="Export" right={<span className="text-[12px] text-slate-400">in this browser · nothing is uploaded</span>}>
            <div className="sc-actions">
              <button type="button" className="cmp-btn" onClick={() => csv(schedules, `schedules_${runLabel}`)}>Download all as CSV</button>
              <button type="button" className="cmp-btn" disabled={pdfBusy} onClick={() => pdf(schedules, `schedules_${runLabel}`)}>{pdfBusy ? 'Building PDF…' : 'Download all as PDF'}</button>
              {sel && <>
                <span className="sc-sep" aria-hidden="true" />
                <button type="button" className="cmp-btn" onClick={() => csv([sel], `schedule_${sel.id}_${runLabel}`)}>Download {sel.id} as CSV</button>
                <button type="button" className="cmp-btn" disabled={pdfBusy} onClick={() => pdf([sel], `schedule_${sel.id}_${runLabel}`)}>Download {sel.id} as PDF</button>
              </>}
            </div>
            <p className="viz-note mt-2">
              Timings {estimated ? TIMINGS.estimated : TIMINGS.run}: sailing days per leg plus one port stay per call; the round voyage
              (vessels × 7 / departures per week) keeps every port on the same weekday, with the spare time spent at the first port.
            </p>
          </InstrumentPanel>

          <div className="grid grid-cols-12 gap-3">
            <div className="col-span-12 xl:col-span-5 min-w-0">
              <InstrumentPanel title="Services" right={<span className="text-[12px] text-slate-400">pick one to see its schedule</span>} bodyPadding="flush">
                <div className="tf-scroll sc-list">
                  <table className="viz-table wi-table tf-table">
                    <thead><tr><th>Service</th><th className="r">Calls</th><th className="r">Sailings / wk</th><th className="r">Vessels</th><th className="r">Round voyage</th><th>Leaves first port</th></tr></thead>
                    <tbody>
                      {schedules.map((s) => (
                        <tr key={s.id} aria-selected={s === sel} className={s === sel ? 'tf-on' : ''} tabIndex={0}
                          onClick={() => setSelId(s.id)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelId(s.id); } }}>
                          <td>{s.id}<div className="dz-pct">{s.vesselClass}</div></td>
                          <td className="r">{s.calls.length}</td>
                          <td className="r">{s.frequency}</td>
                          <td className="r">{s.vessels}</td>
                          <td className="r">{d1(s.roundVoyageDays)} d</td>
                          <td>{s.calls[0].port} · {s.departures.map(weekdayTime).join(', ')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </InstrumentPanel>
            </div>
            <div className="col-span-12 xl:col-span-7 min-w-0">
              {sel && <ServiceSchedule pf={sel} />}
            </div>
          </div>
        </>
      )}

      <Provenance
        source="selected_services of the run (legs, port stay, cycle, vessels) → utils/proformaSchedule.js"
        sourceStatus={schedules.length ? 'available' : 'no_data'}
        attribution="Pro-forma schedules derived from the recorded plan"
        license="Internal artifact"
      />
    </div>
  );
}

function ServiceSchedule({ pf }) {
  return (
    <InstrumentPanel title={`${pf.id} pro-forma`} right={<span className="text-[12px] text-slate-400">{pf.vesselClass} · {pf.frequency}× / wk · {pf.vessels} vessel{pf.vessels === 1 ? '' : 's'}</span>} bodyPadding="flush">
      <div className="tf-scroll">
        <table className="viz-table wi-table tf-table sc-table">
          <thead>
            <tr>
              <th>#</th><th>Port</th>
              {pf.departures.map((_, k) => <th key={k}>{pf.departures.length > 1 ? `Departure ${k + 1}: arrive / depart` : 'Arrive / depart'}</th>)}
              <th className="r">Next leg</th><th className="r">Sail</th><th className="r">TEU on leg</th>
            </tr>
          </thead>
          <tbody>
            {pf.calls.map((c) => (
              <tr key={c.seq}>
                <td>{c.seq}</td>
                <td>{c.port}<div className="dz-pct">{getPortName(c.port)}</div></td>
                {pf.departures.map((d0, k) => (
                  <td key={k} className="sc-times">{c.arrive == null ? '—' : weekdayTime(d0 + c.arrive)} / {weekdayTime(d0 + c.depart)}</td>
                ))}
                <td className="r">{c.next.to}{c.next.nm ? <div className="dz-pct">{fmtNum(Math.round(c.next.nm))} nm</div> : null}</td>
                <td className="r">{d1(c.next.sailDays)} d</td>
                <td className="r">{Number.isFinite(c.next.loadTeu) ? fmtNum(Math.round(c.next.loadTeu)) : '—'}</td>
              </tr>
            ))}
            <tr className="sc-return">
              <td>{pf.calls.length + 1}</td>
              <td>{pf.calls[0].port}<div className="dz-pct">back at the first port</div></td>
              {pf.departures.map((d0, k) => (
                <td key={k} className="sc-times">{weekdayTime(d0 + pf.returnArrival)} / next voyage {weekdayTime(d0 + pf.roundVoyageDays)}</td>
              ))}
              <td colSpan={3} className="r dz-pct">{d1(pf.bufferDays)} d spare in the round voyage</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="viz-note px-3 pb-2">
        Round voyage {d1(pf.roundVoyageDays)} days = {pf.vessels} vessel{pf.vessels === 1 ? '' : 's'} × 7 / {pf.frequency}; sailing and
        {' '}{d1(pf.stayDays)} d port stays take {d1(pf.activeDays)} days. Timings {TIMINGS[pf.source]}.
      </div>
    </InstrumentPanel>
  );
}

/** One table per service, A4 landscape. jsPDF's built-in font is Latin-1: plain ASCII separators only. */
async function downloadSchedulePdf(list, name) {
  const [{ jsPDF }, { autoTable }] = await Promise.all([import('jspdf'), import('jspdf-autotable')]);
  const doc = new jsPDF({ orientation: 'landscape', unit: 'pt', format: 'a4' });
  const W = doc.internal.pageSize.getWidth();
  const ascii = (s) => String(s ?? '').normalize('NFKD').replace(/[^\x20-\x7e]/g, '');
  doc.setFont('helvetica', 'bold'); doc.setFontSize(15);
  doc.text('Weekly pro-forma schedules', 40, 44);
  doc.setFont('helvetica', 'normal'); doc.setFontSize(9);
  doc.text(ascii(`${list.length} service(s) - day 0 = first departure from each service's first port, Monday 00:00 - generated ${new Date().toISOString().slice(0, 16).replace('T', ' ')} UTC`), 40, 60);
  let y = 78;
  list.forEach((pf) => {
    const head = [['#', 'Port', ...pf.departures.map((_, k) => (pf.departures.length > 1 ? `Dep ${k + 1} arrive` : 'Arrive')).flatMap((h, k) => [h, pf.departures.length > 1 ? `Dep ${k + 1} depart` : 'Depart']), 'Next port', 'Leg nm', 'Sail d', 'TEU on leg']];
    const body = pf.calls.map((c) => [
      c.seq, ascii(`${c.port} ${getPortName(c.port) || ''}`),
      ...pf.departures.flatMap((d0) => [c.arrive == null ? '-' : weekdayTime(d0 + c.arrive), weekdayTime(d0 + c.depart)]),
      c.next.to, c.next.nm ? Math.round(c.next.nm) : '-', d1(c.next.sailDays), Number.isFinite(c.next.loadTeu) ? Math.round(c.next.loadTeu) : '-',
    ]);
    body.push([pf.calls.length + 1, ascii(`${pf.calls[0].port} (back)`),
      ...pf.departures.flatMap((d0) => [weekdayTime(d0 + pf.returnArrival), `next ${weekdayTime(d0 + pf.roundVoyageDays)}`]), '', '', '', '']);
    if (y > doc.internal.pageSize.getHeight() - 120) { doc.addPage(); y = 44; }
    doc.setFont('helvetica', 'bold'); doc.setFontSize(11);
    doc.text(ascii(`${pf.id}  -  ${pf.vesselClass || ''}  -  ${pf.frequency}x / week  -  ${pf.vessels} vessel(s)  -  round voyage ${d1(pf.roundVoyageDays)} d`), 40, y);
    doc.setFont('helvetica', 'normal'); doc.setFontSize(8);
    doc.text(ascii(`Timings ${TIMINGS[pf.source]}.`), 40, y + 12);
    autoTable(doc, {
      head, body, startY: y + 18, margin: { left: 40, right: 40 }, theme: 'grid',
      styles: { font: 'helvetica', fontSize: 8, cellPadding: 3 }, headStyles: { fillColor: [30, 58, 95], textColor: 255 },
      tableWidth: W - 80,
    });
    y = doc.lastAutoTable.finalY + 26;
  });
  const pages = doc.getNumberOfPages();
  for (let i = 1; i <= pages; i++) {
    doc.setPage(i); doc.setFontSize(8);
    doc.text(`Page ${i} of ${pages}`, W - 90, doc.internal.pageSize.getHeight() - 20);
  }
  doc.save(`${String(name).replace(/[^\w.-]+/g, '_').slice(0, 80)}.pdf`);
  toast(`Saved ${name}.pdf`);
}
