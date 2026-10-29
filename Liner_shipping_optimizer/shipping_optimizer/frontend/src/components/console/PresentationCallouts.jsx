/**
 * PresentationCallouts.jsx — guided-tour annotations in presentation mode (design D11). On each slide the key
 * findings (utils/tourFindings.js, computed from the run on screen) appear one after another as numbered callouts,
 * each ringing the panel it is about and pinned to it. The first panel is scrolled into view. C toggles them.
 *
 * Positions follow the panels: measured after the view renders, again on scroll and resize, and for the first
 * seconds while lazy panels settle. A finding whose panel is not on the page is listed in the corner instead.
 */

import React, { useEffect, useLayoutEffect, useMemo, useState } from 'react';
import { tourFindings } from '../../utils/tourFindings.js';
import { useBenchBaseline } from '../../services/benchBaseline.js';
import { datasetKeyOf } from '../../runtime/consoleSelectors.js';
import { motionLevel } from '../../services/prefsStore.js';

const STAGGER_MS = 1500;
const SETTLE_MS = 4000;
const CARD_W = 300;

const findPanel = (prefix) => [...document.querySelectorAll('#console-workspace section.cx-instr[aria-label]')]
  .find((el) => el.getAttribute('aria-label').toLowerCase().startsWith(prefix.toLowerCase()));

export default function PresentationCallouts({ tab, runtime, optimizationState, slideKey }) {
  const bench = useBenchBaseline(datasetKeyOf(optimizationState));
  const findings = useMemo(() => tourFindings(runtime, bench)[tab] || [], [runtime, bench, tab]);
  const [shown, setShown] = useState(0);
  const [rects, setRects] = useState([]);

  // One more callout every STAGGER_MS; all at once without motion.
  useEffect(() => {
    if (motionLevel() !== 'full') { setShown(findings.length); return undefined; }
    setShown(findings.length ? 1 : 0);
    const t = setInterval(() => setShown((k) => (k >= findings.length ? k : k + 1)), STAGGER_MS);
    return () => clearInterval(t);
  }, [slideKey, findings.length]);

  useLayoutEffect(() => {
    let first = true;
    const measure = () => {
      const els = findings.map((f) => findPanel(f.panel));
      if (first && els[0]) {
        first = false;
        els[0].scrollIntoView({ block: 'start', behavior: motionLevel() === 'full' ? 'smooth' : 'auto' });
      }
      setRects(els.map((el) => (el ? el.getBoundingClientRect() : null)));
    };
    measure();
    const ws = document.getElementById('console-workspace');
    const poll = setInterval(measure, 400);
    const stop = setTimeout(() => clearInterval(poll), SETTLE_MS);
    ws?.addEventListener('scroll', measure, { passive: true });
    window.addEventListener('resize', measure);
    return () => { clearInterval(poll); clearTimeout(stop); ws?.removeEventListener('scroll', measure); window.removeEventListener('resize', measure); };
  }, [slideKey, findings]);

  if (!findings.length) return null;
  const vw = typeof window !== 'undefined' ? window.innerWidth : 1280;
  const vh = typeof window !== 'undefined' ? window.innerHeight : 800;
  // Cards stay above the presentation controls (they sit low on the screen, higher on phones where they wrap).
  const floor = Math.min(vh, document.querySelector('.pres-hud')?.getBoundingClientRect().top ?? vh) - 8;
  const docked = [];
  return (
    <div className="tour-layer" aria-live="polite">
      {findings.slice(0, shown).map((f, i) => {
        const r = rects[i];
        const w = Math.min(CARD_W, vw - 32);
        const estH = 44 + Math.ceil((f.text.length * 7.2) / (w - 50)) * 19;   // two lines of padding + wrapped text
        const visible = r && r.bottom > 60 && r.top + 40 + estH < floor + 80;
        if (!visible) { docked.push([f, i]); return null; }
        const left = Math.max(16, Math.min(r.right - w - 12, vw - w - 16));
        const top = Math.max(56, Math.min(r.top + 40, floor - estH));
        return (
          <React.Fragment key={`${slideKey}-${i}`}>
            <span className="tour-ring" style={{ left: r.left - 3, top: r.top - 3, width: r.width + 6, height: r.height + 6 }} aria-hidden="true" />
            <div className="tour-card" style={{ left, top, width: w }} role="note" aria-label={`Finding ${i + 1}: ${f.title}`}>
              <span className="tour-n" aria-hidden="true">{i + 1}</span>
              <div><b>{f.title}</b><p>{f.text}</p></div>
            </div>
          </React.Fragment>
        );
      })}
      {docked.length > 0 && (
        <div className="tour-dock" role="note" aria-label="Findings on panels off screen" style={{ bottom: vh - floor + 8 }}>
          {docked.map(([f, i]) => (
            <div key={`${slideKey}-d${i}`} className="tour-card is-docked"><span className="tour-n" aria-hidden="true">{i + 1}</span><div><b>{f.title}</b><p>{f.text}</p></div></div>
          ))}
        </div>
      )}
    </div>
  );
}
