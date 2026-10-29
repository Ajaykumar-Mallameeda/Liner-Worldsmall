/**
 * mapSnapshot — maps that can hand over a picture of themselves (the PDF plan report, design D12). A map registers
 * under an id (GlMap's snapshotId prop); snapshot(id) resolves to { url, width, height } (JPEG data URL) or null when
 * that map is not on screen or its canvas cannot be read.
 */

const makers = new Map();

export function registerSnapshot(id, make) {
  makers.set(id, make);
  return () => { if (makers.get(id) === make) makers.delete(id); };
}

export const hasSnapshot = (id) => makers.has(id);

export async function snapshot(id) {
  const make = makers.get(id);
  if (!make) return null;
  try { return await make(); } catch (_) { return null; }
}

/** Waits up to ms for a map to register (a tab that has just been opened). */
export function whenSnapshot(id, ms = 8000) {
  return new Promise((resolve) => {
    const t0 = Date.now();
    const tick = () => {
      if (makers.has(id)) resolve(true);
      else if (Date.now() - t0 > ms) resolve(false);
      else setTimeout(tick, 200);
    };
    tick();
  });
}
