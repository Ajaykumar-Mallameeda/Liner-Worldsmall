/**
 * Viewer preferences: colour theme and row density. Kept per browser in localStorage ("vr.prefs") and
 * applied as data-theme / data-density on <html>, which the stylesheet keys off. Storage can be missing
 * (private window, blocked site data); the dashboard then runs on the defaults.
 */
import { useSyncExternalStore } from 'react';

const KEY = 'vr.prefs';
const DEFAULTS = { theme: 'dark', density: 'comfortable' };
const THEMES = ['dark', 'light'];
const DENSITIES = ['comfortable', 'compact'];

function read() {
  try {
    const p = JSON.parse(localStorage.getItem(KEY) || '{}') || {};
    return {
      theme: THEMES.includes(p.theme) ? p.theme : DEFAULTS.theme,
      density: DENSITIES.includes(p.density) ? p.density : DEFAULTS.density,
    };
  } catch (_) {
    return { ...DEFAULTS };
  }
}

let prefs = read();
const listeners = new Set();

function apply() {
  if (typeof document === 'undefined') return;
  const el = document.documentElement;
  el.dataset.theme = prefs.theme;
  el.dataset.density = prefs.density;
  el.style.colorScheme = prefs.theme;
}
apply();

export function getPrefs() {
  return prefs;
}

export function setPrefs(patch) {
  prefs = { ...prefs, ...patch };
  try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch (_) { /* storage blocked: keep in memory */ }
  apply();
  listeners.forEach((fn) => fn(prefs));
}

export const toggleTheme = () => setPrefs({ theme: prefs.theme === 'dark' ? 'light' : 'dark' });
export const toggleDensity = () => setPrefs({ density: prefs.density === 'compact' ? 'comfortable' : 'compact' });

export function usePrefs() {
  return useSyncExternalStore((fn) => { listeners.add(fn); return () => listeners.delete(fn); }, getPrefs, getPrefs);
}
