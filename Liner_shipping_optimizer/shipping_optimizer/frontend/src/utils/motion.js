/**
 * Motion helpers shared by the console. Durations come from the tokens in index.css (100 / 150 / 200 / 300 ms);
 * every helper checks the viewer's motion level first (prefsStore.motionLevel): "off" jumps straight to the end
 * state, "reduced" keeps opacity changes only.
 *
 *   withViewTransition(update, dir)  swaps the main pane with a crossfade (View Transitions API when available)
 *   tween({ from, to, duration, onFrame, onDone })  requestAnimationFrame tween with the token ease-out
 *   usePresence(open, exitMs)  keeps an overlay mounted through its exit animation
 */
import { useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { motionLevel } from '../services/prefsStore.js';

export const MS = { 100: 100, 150: 150, 200: 200, 300: 300 };

/** JS twin of --ease-out: cubic-bezier(0.16, 1, 0.3, 1) is close to an exponential ease-out. */
export const easeOut = (t) => (t >= 1 ? 1 : 1 - 2 ** (-10 * t));

/**
 * Run a React state update inside a view transition so only the main pane crossfades (header, sidebar and
 * status bar carry no view-transition-name and stay still). dir: 'next' | 'prev' | null picks the sub-tab slide.
 * Falls back to a plain update where the API is missing, motion is off, or the tab is hidden.
 */
export function withViewTransition(update, dir = null) {
  const level = motionLevel();
  const root = document.documentElement;
  if (level === 'off' || typeof document.startViewTransition !== 'function' || document.hidden) {
    update();
    return;
  }
  root.dataset.vtDir = level === 'full' && dir ? dir : 'fade';
  try {
    const vt = document.startViewTransition(() => flushSync(update));
    // A quick second tab press skips the running transition; that rejection is expected, not an error.
    vt.ready.catch(() => {});
    vt.finished.catch(() => {}).finally(() => { if (root.dataset.vtDir) delete root.dataset.vtDir; });
  } catch (_) {
    delete root.dataset.vtDir;
    update();
  }
}

/** Tween a number (or an array of numbers) from `from` to `to`. Returns a cancel function. */
export function tween({ from, to, duration = MS[300], ease = easeOut, onFrame, onDone }) {
  const level = motionLevel();
  if (level !== 'full' || duration <= 0 || typeof requestAnimationFrame !== 'function') {
    onFrame(to, 1);
    if (onDone) onDone();
    return () => {};
  }
  const isArr = Array.isArray(from);
  const lerp = (a, b, k) => a + (b - a) * k;
  let raf = 0;
  const t0 = performance.now();
  const step = (now) => {
    const t = Math.min(1, (now - t0) / duration);
    const k = ease(t);
    onFrame(isArr ? from.map((a, i) => lerp(a, to[i], k)) : lerp(from, to, k), t);
    if (t < 1) raf = requestAnimationFrame(step);
    else if (onDone) onDone();
  };
  raf = requestAnimationFrame(step);
  return () => cancelAnimationFrame(raf);
}

/**
 * Enter/exit for overlays: { mounted, state } where state is 'open' or 'closing'. The element stays mounted
 * for exitMs after `open` turns false so the exit animation can play; Escape and focus restore are the
 * caller's and happen immediately (the closing element gets pointer-events: none from the stylesheet).
 */
export function usePresence(open, exitMs = MS[150]) {
  const [mounted, setMounted] = useState(open);
  const timer = useRef(null);
  useEffect(() => {
    clearTimeout(timer.current);
    if (open) { setMounted(true); return undefined; }
    if (!mounted) return undefined;
    const wait = motionLevel() === 'off' ? 0 : exitMs;
    timer.current = setTimeout(() => setMounted(false), wait);
    return () => clearTimeout(timer.current);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  return { mounted: open || mounted, state: open ? 'open' : 'closing' };
}
