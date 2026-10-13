/**
 * IntelligencePanel
 * -----------------
 * Glassy panel with a consistent header (title + optional right
 * slot), a footer slot, and a smooth fade-in on first mount. This
 * is the structural replacement for the five ad-hoc `Panel`/`Card`
 * wrappers used by the per-phase maritime views. The visual
 * language is unchanged from the existing dashboard (same dark
 * glass, same border, same blur) so any content swapped in keeps
 * its identity.
 *
 * Pure presentational. The parent supplies the title and any
 * right-aligned actions or status pills; the panel never reaches
 * outside its own subtree.
 */

import { useEffect, useState } from 'react';

export default function IntelligencePanel({
  title,
  right,
  children,
  footer,
  density = 'comfortable', // compact | comfortable | spacious
  as: As = 'div',
  ariaLabel,
}) {
  const [entered, setEntered] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setEntered(true), 12);
    return () => clearTimeout(t);
  }, []);
  const padY =
    density === 'compact' ? 'py-2.5' :
      density === 'spacious' ? 'py-5' : 'py-3.5';
  const padX = density === 'compact' ? 'px-3' : 'px-4';
  return (
    <As
      className={`rounded-xl ${padX} ${padY} backdrop-blur maritime-panel ${entered ? 'maritime-panel-enter' : 'maritime-panel-pre'}`}
      style={{
        background: 'rgba(15,23,42,0.55)',
        border: '1px solid rgba(255,255,255,0.06)',
        boxShadow: '0 0 0 1px rgba(0,212,255,0.0)',
      }}
      aria-label={ariaLabel || title}
    >
      {(title || right) && (
        <div className="flex items-center justify-between gap-3 mb-2.5">
          {title && (
            <div className="text-[10px] font-mono uppercase tracking-widest text-white/40">
              {title}
            </div>
          )}
          {right && <div className="flex items-center gap-2">{right}</div>}
        </div>
      )}
      {children}
      {footer && (
        <div
          className="mt-3 pt-2"
          style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}
        >
          {footer}
        </div>
      )}
    </As>
  );
}
