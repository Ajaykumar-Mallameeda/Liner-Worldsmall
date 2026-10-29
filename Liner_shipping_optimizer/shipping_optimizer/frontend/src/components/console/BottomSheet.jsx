/**
 * BottomSheet.jsx — port and service details on phones (design D9). Below 768 px the detail panel slides up from
 * the bottom over the map instead of stacking under it; wider screens keep the side column (the caller decides
 * with useIsPhone).
 *
 * Two heights: half (the map stays visible above) and full. Drag the handle or header: up opens full, down
 * goes back to half or closes; the handle button and Esc do the same from the keyboard. Non-modal, so the map
 * above keeps working; focus moves into the sheet when it opens and back when it closes.
 */

import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { sheetAfterDrag } from '../../utils/bottomSheet.js';

const PHONE = '(max-width: 767px)';
const SIZE_DVH = { half: 55, full: 92 };   // also in index.css (.bs-sheet.is-half / .is-full)

export function useIsPhone() {
  const [phone, setPhone] = useState(() => typeof window !== 'undefined' && Boolean(window.matchMedia?.(PHONE).matches));
  useEffect(() => {
    const mq = window.matchMedia?.(PHONE);
    if (!mq) return undefined;
    const on = () => setPhone(mq.matches);
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, []);
  return phone;
}

export default function BottomSheet({ open, title, eyebrow, onClose, children }) {
  const [size, setSize] = useState('half');
  const [dy, setDy] = useState(0);
  const drag = useRef(null);
  const dragged = useRef(false);   // a drag that started on the handle must not also count as its click
  const sheetRef = useRef(null);
  const lastFocus = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    setSize('half');
    lastFocus.current = document.activeElement;
    setTimeout(() => sheetRef.current?.focus({ preventScroll: true }), 0);
    const onKey = (e) => { if (e.key === 'Escape') onClose?.(); };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      if (lastFocus.current?.isConnected && lastFocus.current.focus) lastFocus.current.focus({ preventScroll: true });
    };
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!open) return null;
  const onDown = (e) => {
    if (e.button != null && e.button !== 0) return;
    if (e.target.closest('button:not(.bs-handle)')) return;   // the close button is a click, not a drag
    drag.current = { y: e.clientY, id: e.pointerId, captured: false };
  };
  const onMove = (e) => {
    const d = drag.current;
    if (!d) return;
    const delta = e.clientY - d.y;
    // Capture only once it is a drag: capturing on press would send the handle's click to the header instead.
    if (!d.captured && Math.abs(delta) > 6) { d.captured = true; e.currentTarget.setPointerCapture?.(d.id); }
    if (d.captured) setDy(Math.max(-window.innerHeight, delta));
  };
  const onUp = () => {
    if (!drag.current) return;
    const next = sheetAfterDrag(size, dy);
    const moved = Math.abs(dy) > 6;
    dragged.current = moved;
    setTimeout(() => { dragged.current = false; }, 0);   // the click, if any, fires before this
    drag.current = null;
    setDy(0);
    if (!moved) return;
    if (next === 'closed') onClose?.(); else setSize(next);
  };

  return createPortal(
    <section ref={sheetRef} className={`bs-sheet is-${size} ${dy ? 'is-dragging' : ''}`} role="dialog" aria-modal="false"
      aria-label={title} tabIndex={-1} style={dy ? { height: `max(64px, min(92dvh, calc(${SIZE_DVH[size]}dvh - ${dy}px)))` } : undefined}>
      <header className="bs-head" onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp}>
        <button type="button" className="bs-handle" onClick={() => { if (dragged.current) { dragged.current = false; return; } setSize(size === 'full' ? 'half' : 'full'); }}
          aria-label={size === 'full' ? 'Show the map: half-height details' : 'Expand the details to full height'} aria-expanded={size === 'full'}>
          <span aria-hidden="true" />
        </button>
        <div className="bs-title">
          {eyebrow && <span className="bs-eyebrow">{eyebrow}</span>}
          <span>{title}</span>
        </div>
        <button type="button" className="bs-close" onClick={onClose} aria-label={`Close ${title}`}>✕</button>
      </header>
      <div className="bs-body">{children}</div>
    </section>,
    document.body,
  );
}
