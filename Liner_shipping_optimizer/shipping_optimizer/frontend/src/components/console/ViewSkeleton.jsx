/**
 * Placeholder in the shape of a console view (page head, a row of figure tiles, two panels) while a tab's
 * code or the run file is loading. It stays invisible for the first 150 ms so fast loads never flash it.
 *
 * Reveal wraps the view that replaces it: when a skeleton was actually on screen, the content fades in over
 * it (200 ms, opacity only) instead of popping; when the content was ready at once, nothing animates.
 */
import React, { useEffect, useLayoutEffect, useState } from 'react';

const VISIBLE_AFTER_MS = 150;   // matches the .skel delay in index.css
let shownAt = 0;                // when the last skeleton became visible (0 = none since the last reveal)

export default function ViewSkeleton({ label = 'view' }) {
  useEffect(() => {
    const t = setTimeout(() => { shownAt = performance.now(); }, VISIBLE_AFTER_MS);
    return () => clearTimeout(t);
  }, []);
  return (
    <div className="skel" role="status" aria-label={`Loading ${label}`}>
      <div className="skel-head"><span className="skel-line w40" /><span className="skel-line w70" /></div>
      <div className="skel-tiles">
        {[0, 1, 2, 3].map((i) => <div key={i} className="skel-block h72" />)}
      </div>
      <div className="skel-split">
        <div className="skel-block h300" />
        <div className="skel-block h300" />
      </div>
      <span className="sr-only">Loading {label}…</span>
    </div>
  );
}

export function Reveal({ children }) {
  const [reveal] = useState(() => shownAt > 0 && performance.now() - shownAt < 10000);
  useLayoutEffect(() => { shownAt = 0; }, []);
  return <div className={`cx-reveal ${reveal ? 'is-revealing' : ''}`}>{children}</div>;
}
