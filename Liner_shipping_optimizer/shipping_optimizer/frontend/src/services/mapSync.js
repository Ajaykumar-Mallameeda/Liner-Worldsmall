/**
 * mapSync — keeps the cameras of several MapLibre maps together (design D7: Run diff split screen, A | B).
 *
 * The map the viewer last touched (pointer, wheel, touch or key inside its frame) leads: every camera move it makes,
 * its own button glides included, is copied to the others with jumpTo. Followers never broadcast, so two maps cannot
 * chase each other.
 */

const groups = new Map();   // name → { maps: Set, driver }
const LEAD_EVENTS = ['pointerdown', 'wheel', 'touchstart', 'keydown'];

export const cameraOf = (map) => ({ center: map.getCenter(), zoom: map.getZoom(), bearing: map.getBearing(), pitch: map.getPitch() });

/** Adds a map to a group; el is the element whose interactions make this map the leader. Returns the leave function. */
export function joinSync(group, map, el = null) {
  if (!group || !map) return () => {};
  let g = groups.get(group);
  if (!g) { g = { maps: new Set(), driver: null }; groups.set(group, g); }
  g.maps.add(map);
  const lead = () => { g.driver = map; };
  LEAD_EVENTS.forEach((t) => el?.addEventListener(t, lead, { capture: true, passive: true }));
  const onMove = () => {
    if (g.driver !== map) return;
    const cam = cameraOf(map);
    g.maps.forEach((m) => { if (m !== map) m.jumpTo(cam); });
  };
  map.on('move', onMove);
  return () => {
    map.off('move', onMove);
    LEAD_EVENTS.forEach((t) => el?.removeEventListener(t, lead, { capture: true }));
    g.maps.delete(map);
    if (g.driver === map) g.driver = null;
    if (!g.maps.size) groups.delete(group);
  };
}

export const syncGroupSize = (group) => groups.get(group)?.maps.size || 0;
