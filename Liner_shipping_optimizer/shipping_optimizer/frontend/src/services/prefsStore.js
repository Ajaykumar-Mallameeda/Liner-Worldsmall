/**
 * Viewer preferences: colour theme, row density and motion. Kept per browser in localStorage ("vr.prefs") and
 * applied as data-theme / data-density / data-motion on <html>, which the stylesheet keys off. Storage can be
 * missing (private window, blocked site data); the dashboard then runs on the defaults.
 *
 * Motion: the viewer picks system / reduced / off. "system" follows prefers-reduced-motion. data-motion carries
 * the level in force (full / reduced / off), so CSS and JS read one value; motionLevel() is the JS side.
 */
import { useSyncExternalStore } from 'react';

const KEY = 'vr.prefs';
const DEFAULTS = { theme: 'dark', density: 'comfortable', motion: 'system' };
const THEMES = ['dark', 'light'];
const DENSITIES = ['comfortable', 'compact'];
export const MOTIONS = ['system', 'reduced', 'off'];

function read() {
  try {
    const p = JSON.parse(localStorage.getItem(KEY) || '{}') || {};
    return {
      theme: THEMES.includes(p.theme) ? p.theme : DEFAULTS.theme,
      density: DENSITIES.includes(p.density) ? p.density : DEFAULTS.density,
      motion: MOTIONS.includes(p.motion) ? p.motion : DEFAULTS.motion,
    };
  } catch (_) {
    return { ...DEFAULTS };
  }
}

let prefs = read();
const listeners = new Set();
const reduceQuery = typeof window !== 'undefined' && window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;

/** Motion level in force: 'full', 'reduced' or 'off'. */
export function motionLevel(p = prefs) {
  if (p.motion === 'off') return 'off';
  if (p.motion === 'reduced') return 'reduced';
  return reduceQuery?.matches ? 'reduced' : 'full';
}

function apply() {
  if (typeof document === 'undefined') return;
  const el = document.documentElement;
  el.dataset.theme = prefs.theme;
  el.dataset.density = prefs.density;
  el.dataset.motion = motionLevel();
  el.style.colorScheme = prefs.theme;
}
apply();

function notify() {
  listeners.forEach((fn) => fn(prefs));
}

// "System" follows the OS setting live.
reduceQuery?.addEventListener?.('change', () => {
  apply();
  prefs = { ...prefs };   // new object so subscribers re-render
  notify();
});

export function getPrefs() {
  return prefs;
}

export function setPrefs(patch) {
  prefs = { ...prefs, ...patch };
  try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch (_) { /* storage blocked: keep in memory */ }
  apply();
  notify();
}

export const toggleTheme = () => setPrefs({ theme: prefs.theme === 'dark' ? 'light' : 'dark' });
export const toggleDensity = () => setPrefs({ density: prefs.density === 'compact' ? 'comfortable' : 'compact' });
export const cycleMotion = () => setPrefs({ motion: MOTIONS[(MOTIONS.indexOf(prefs.motion) + 1) % MOTIONS.length] });
export const setMotion = (motion) => MOTIONS.includes(motion) && setPrefs({ motion });

export function usePrefs() {
  return useSyncExternalStore((fn) => { listeners.add(fn); return () => listeners.delete(fn); }, getPrefs, getPrefs);
}

/** Motion level for components; re-renders when the setting or the OS preference changes. */
export function useMotionLevel() {
  return motionLevel(usePrefs());
}
