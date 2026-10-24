/**
 * Placeholder in the shape of a console view (page head, a row of figure tiles, two panels) while a tab's
 * code or the run file is loading. It stays invisible for the first 150 ms so fast loads never flash it.
 */
import React from 'react';

export default function ViewSkeleton({ label = 'view' }) {
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
