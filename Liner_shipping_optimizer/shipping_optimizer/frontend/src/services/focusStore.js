/**
 * Cross-filter focus shared by every view: one regional agent (the engine's own label, e.g. "Asia").
 * Choosing an agent anywhere (Regional Agents card, coverage chart, command palette, header chip) narrows the
 * map, the services table, Fleet and the per-service charts to that agent's services. null = no filter.
 *
 * Also carries one-shot "open this service" requests from the command palette to the Network tab.
 */
import { useSyncExternalStore } from 'react';

function createStore(initial) {
  let value = initial;
  const listeners = new Set();
  return {
    get: () => value,
    set: (next) => {
      if (next === value) return;
      value = next;
      listeners.forEach((fn) => { try { fn(next); } catch (_) { /* listener error */ } });
    },
    subscribe: (fn) => { listeners.add(fn); return () => listeners.delete(fn); },
  };
}

const agentStore = createStore(null);
const serviceStore = createStore(null);

export function getAgentFocus() {
  return agentStore.get();
}

export function setAgentFocus(next) {
  agentStore.set(next ? String(next) : null);
}

export function toggleAgentFocus(next) {
  setAgentFocus(next && sameAgent(next, agentStore.get()) ? null : next);
}

/** [agent, setAgent] for components. */
export function useAgentFocus() {
  const value = useSyncExternalStore(agentStore.subscribe, agentStore.get, agentStore.get);
  return [value, setAgentFocus];
}

/** Agent labels compare without case, spaces or underscores ("Middle East" = "middle_east"). */
export const agentKey = (a) => String(a ?? '').toLowerCase().replace(/[\s_]+/g, '_');
export const sameAgent = (a, b) => a != null && b != null && agentKey(a) === agentKey(b);

/** True when a service belongs to the focused agent (or no agent is focused). */
export function matchesAgent(service, focus = agentStore.get()) {
  if (!focus) return true;
  return sameAgent(service && (service.agent_region ?? service.region), focus);
}

/** Ask the Network tab to open one service, or to list the services calling one port. */
export function requestService(id) {
  serviceStore.set(id == null ? null : { kind: 'service', id: String(id) });
}
export function requestPort(code) {
  serviceStore.set(code == null ? null : { kind: 'port', id: String(code) });
}

/** [{ kind, id } or null, clear] — the Network tab consumes and clears it. */
export function useServiceRequest() {
  const value = useSyncExternalStore(serviceStore.subscribe, serviceStore.get, serviceStore.get);
  return [value, () => serviceStore.set(null)];
}
