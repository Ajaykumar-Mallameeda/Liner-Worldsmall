/**
 * timelineStore — one simulated clock shared by every map view (vessel markers, network replay, flows).
 *
 *   day      simulated days since the plan's week started (unbounded; positions use it modulo each cycle)
 *   playing  whether the clock runs
 *   speed    simulated days per second of screen time (1, 2 or 7)
 *
 * The viewer starts and stops it (the timeline bar). Motion "full" advances it every frame; "reduced" and
 * "off" advance it in discrete half-day steps twice a second, so nothing glides.
 */
import { useSyncExternalStore } from 'react';

const STEP_DAYS = 0.5;
const STEP_MS = 500;
let state = { day: 0, playing: false, speed: 1 };
const listeners = new Set();
let raf = 0; let timer = 0; let last = 0; let mode = 'full';

const emit = () => listeners.forEach((fn) => { try { fn(); } catch (_) { /* listener error */ } });
const set = (patch) => { state = { ...state, ...patch }; emit(); };

function stopLoops() {
  if (raf) cancelAnimationFrame(raf);
  if (timer) clearInterval(timer);
  raf = 0; timer = 0;
}

function startLoops() {
  stopLoops();
  if (!state.playing || typeof window === 'undefined') return;
  if (mode === 'full') {
    last = performance.now();
    const step = (now) => {
      const dt = Math.min(0.25, (now - last) / 1000); last = now;
      set({ day: state.day + dt * state.speed });
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
  } else {
    timer = setInterval(() => set({ day: state.day + STEP_DAYS * state.speed }), STEP_MS);
  }
}

export const getTimeline = () => state;
export function subscribeTimeline(fn) { listeners.add(fn); return () => listeners.delete(fn); }
export function useTimeline() { return useSyncExternalStore(subscribeTimeline, getTimeline, getTimeline); }

export function playTimeline() { if (!state.playing) { set({ playing: true }); startLoops(); } }
export function pauseTimeline() { if (state.playing) { set({ playing: false }); stopLoops(); } }
export function toggleTimeline() { if (state.playing) pauseTimeline(); else playTimeline(); }
export function seekTimeline(day) { set({ day: Math.max(0, Number(day) || 0) }); }
export function setTimelineSpeed(speed) { set({ speed: Number(speed) || 1 }); }
/** Motion level from prefsStore ('full' | 'reduced' | 'off'); switches between smooth and stepped clock. */
export function setTimelineMotion(level) { if (level !== mode) { mode = level; if (state.playing) startLoops(); } }
export function resetTimeline() { stopLoops(); state = { day: 0, playing: false, speed: 1 }; emit(); }

export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
/** "Week 2 · Wed 14:00" for a simulated day. */
export function clockLabel(day) {
  const d = Math.max(0, day);
  const week = Math.floor(d / 7) + 1;
  const wd = Math.floor(d % 7);
  const h = Math.floor((d % 1) * 24);
  return `Week ${week} · ${WEEKDAYS[wd]} ${String(h).padStart(2, '0')}:00`;
}
