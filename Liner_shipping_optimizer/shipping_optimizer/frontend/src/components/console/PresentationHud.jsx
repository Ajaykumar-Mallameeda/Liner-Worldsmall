/**
 * PresentationHud — the control strip shown while presentation mode steps through the main views.
 * Space pauses, ← / → step, Esc stops (handled by MaritimeDashboard). The bar under the strip fills over the
 * dwell time; under reduced or no motion the seconds left are shown instead of the moving bar.
 */
import React, { useEffect, useState } from 'react';
import { useMotionLevel } from '../../services/prefsStore.js';

/** Header button and command palette start presentation mode through this event (MaritimeDashboard listens). */
export const startPresentation = () => window.dispatchEvent(new Event('vr:present'));

export default function PresentationHud({ label, index, total, dwellMs, paused, onPrev, onNext, onTogglePause, onStop }) {
  const level = useMotionLevel();
  const [left, setLeft] = useState(Math.round(dwellMs / 1000));
  useEffect(() => {
    setLeft(Math.round(dwellMs / 1000));
    if (paused) return undefined;
    const t = setInterval(() => setLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(t);
  }, [index, paused, dwellMs]);

  return (
    <div className={`pres-hud ${paused ? 'is-paused' : ''}`} role="region" aria-label="Presentation controls">
      <span className="pres-dot" aria-hidden="true" />
      <span className="pres-k">Presenting</span>
      <span className="pres-v" aria-live="polite">{label}</span>
      <span className="pres-n">{index + 1} / {total}</span>
      <span className="pres-left">{paused ? 'paused' : `next in ${left} s`}</span>
      <span className="pres-btns">
        <button type="button" onClick={onPrev} aria-label="Previous view" title="Previous view (←)">◀</button>
        <button type="button" onClick={onTogglePause} aria-label={paused ? 'Resume' : 'Pause'} title={`${paused ? 'Resume' : 'Pause'} (Space)`}>{paused ? '▶' : '❚❚'}</button>
        <button type="button" onClick={onNext} aria-label="Next view" title="Next view (→)">▶▶</button>
        <button type="button" onClick={onStop} aria-label="Stop presenting" title="Stop presenting (Esc)">✕</button>
      </span>
      {level === 'full' && !paused && (
        <span className="pres-bar" aria-hidden="true"><span key={index} style={{ animationDuration: `${dwellMs}ms` }} /></span>
      )}
    </div>
  );
}
