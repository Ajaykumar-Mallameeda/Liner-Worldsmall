/**
 * WorldMap — the map every page uses. Shows the WebGL map (GlMap.jsx: MapLibre GL + deck.gl, sea lanes,
 * globe, vessel replay) where the browser has WebGL2, and the classic SVG map (SvgWorldMap.jsx) otherwise,
 * when the WebGL map fails, or when the viewer picks it (mapPrefsStore.engine). Both take the same props.
 *
 * `dataset` (optional) names the dataset whose sea lanes to load; by default it is the run's own.
 */
import React, { Suspense, lazy } from 'react';
import SvgWorldMap, { getRegionColor } from './SvgWorldMap.jsx';
import { useMapPrefs, setMapPrefs } from '../../services/mapPrefsStore.js';
import { datasetKeyOf } from '../../runtime/consoleSelectors.js';

export { getRegionColor };

const GlMap = lazy(() => import('./GlMap.jsx'));

let webgl2 = null;
/** True when this browser can create a WebGL2 context (deck.gl interleaved rendering needs it). */
export function hasWebGL2() {
  if (webgl2 !== null) return webgl2;
  try {
    const c = document.createElement('canvas');
    const gl = c.getContext('webgl2');
    webgl2 = Boolean(gl);
    gl?.getExtension('WEBGL_lose_context')?.loseContext();
  } catch (_) {
    webgl2 = false;
  }
  return webgl2;
}

class GlBoundary extends React.Component {
  constructor(props) { super(props); this.state = { failed: false }; }
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(err) { console.warn('[WorldMap] WebGL map failed; showing the SVG map.', err); }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}

function GlLoading() {
  return <div className="wm-root relative w-full h-full min-h-[360px] bg-[#030a14]" aria-busy="true" aria-label="Loading the map" />;
}

export default function WorldMap(props) {
  const prefs = useMapPrefs();
  const gl = hasWebGL2();
  if (!gl || prefs.engine === 'svg') {
    return <SvgWorldMap {...props} onUseGl={gl ? () => setMapPrefs({ engine: 'gl' }) : null} />;
  }
  const dataset = props.dataset || datasetKeyOf(props.optimizationState);
  return (
    <GlBoundary fallback={<SvgWorldMap {...props} glNote="WebGL map unavailable here · classic map shown" />}>
      <Suspense fallback={<GlLoading />}>
        <GlMap {...props} dataset={dataset} />
      </Suspense>
    </GlBoundary>
  );
}
