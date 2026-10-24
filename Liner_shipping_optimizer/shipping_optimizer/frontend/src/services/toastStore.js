/**
 * Short confirmations after a user action ("Saved …csv", "Loaded baltic · seed 00"). Bottom-right, polite
 * live region, gone after a few seconds; never used for errors that need a decision.
 */
import { useSyncExternalStore } from 'react';

let toasts = [];
let seq = 0;
const listeners = new Set();
const emit = () => listeners.forEach((fn) => fn(toasts));

export function dismissToast(id) {
  toasts = toasts.filter((t) => t.id !== id);
  emit();
}

/** toast('Saved run_services.csv') or toast('…', { tone: 'warn', ms: 6000 }) */
export function toast(text, { tone = 'ok', ms = 3500 } = {}) {
  const id = ++seq;
  toasts = [...toasts.slice(-2), { id, text, tone }];
  emit();
  setTimeout(() => dismissToast(id), ms);
  return id;
}

export function useToasts() {
  return useSyncExternalStore((fn) => { listeners.add(fn); return () => listeners.delete(fn); }, () => toasts, () => toasts);
}
