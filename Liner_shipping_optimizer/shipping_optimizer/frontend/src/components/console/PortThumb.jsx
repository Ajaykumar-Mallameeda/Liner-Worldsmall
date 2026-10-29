/**
 * PortThumb.jsx — a small Sentinel-2 cloudless image of a port (design D8: port cards in the drawer and in search
 * results). About 4 km of ground around IMF PortWatch's point for the port (services/portLocate.js), else the
 * dataset's point. Same EOX tiles as the full view (PortSatellite.jsx); the caller shows the CC BY-NC-SA attribution.
 */

import React, { useMemo, useState } from 'react';
import { usePortLocation } from '../../services/portLocate.js';
import { getPortName } from '../../utils/portLookup.js';
import { S2_YEARS, s2TileUrl, thumbZoom, tilesFor } from '../../utils/s2tiles.js';

export const THUMB_CREDIT = 'Sentinel-2 cloudless by EOX IT Services (Copernicus Sentinel data), CC BY-NC-SA 4.0';

export default function PortThumb({ code, size = 64, metres = 4000 }) {
  const { dataset, portwatch: pw, loaded } = usePortLocation(code);
  const [failed, setFailed] = useState(0);
  // Wait for the PortWatch answer before drawing, so the image does not jump from the city to the port.
  const coords = loaded ? (pw ? [pw.lon, pw.lat] : dataset) : null;
  const z = coords ? thumbZoom(coords[1], size, metres) : null;
  const tiles = useMemo(() => (coords ? tilesFor(coords[0], coords[1], z, size, size) : []), [coords?.[0], coords?.[1], z, size]);
  const year = S2_YEARS[0];
  const off = tiles.length > 0 && failed >= tiles.length;
  return (
    <span className={`pt-thumb ${off || (loaded && !coords) ? 'is-off' : ''}`} style={{ width: size, height: size }}
      role="img" aria-label={`Sentinel-2 image of ${getPortName(code) || code}${pw ? '' : ' (dataset point)'}`}
      title={coords ? `${getPortName(code) || code} · Sentinel-2 cloudless ${year}${pw ? ` · PortWatch point (${pw.name})` : ' · dataset point'}` : undefined}>
      {!off && tiles.map((t) => (
        <img key={t.key} src={s2TileUrl(year, z, t.x, t.y)} alt="" draggable="false" loading="lazy" decoding="async"
          style={{ left: t.left, top: t.top }} onError={() => setFailed((n) => n + 1)} />
      ))}
    </span>
  );
}
