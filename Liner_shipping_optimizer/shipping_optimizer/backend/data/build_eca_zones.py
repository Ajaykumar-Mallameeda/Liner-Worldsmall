"""Build backend/data/eca_zones.geojson (run once, needs shapely; not a runtime dependency).

Inputs (Marine Regions WFS, https://geo.vliz.be/geoserver/MarineRegions/wfs, outputFormat=application/json):
  typeName=MarineRegions:eca_reg14_sox_pm                          -> eca_reg14_sox_pm.json
  typeName=MarineRegions:iho, 11 Mediterranean IHO sea areas (CQL)  -> iho_med.json
Usage: python build_eca_zones.py <input dir> <output geojson>
"""
import json, sys
from shapely.geometry import shape, mapping, box
from shapely.ops import unary_union
src = sys.argv[1]; out = sys.argv[2]
TOL = 0.02   # degrees (~1.2 nm): enough for a leg's share inside a zone
feats = []
d = json.load(open(f"{src}/eca_reg14_sox_pm.json"))
groups = {}
for f in d["features"]:
    name = f["properties"]["area"]
    key = "North American area" if name.startswith("North American area") else name
    groups.setdefault(key, []).append(shape(f["geometry"]).simplify(0.005).buffer(0)); print("read", name, flush=True)
med = json.load(open(f"{src}/iho_med.json"))
mg = unary_union([shape(f["geometry"]).simplify(0.005).buffer(0) for f in med["features"]]); print("med union", flush=True)
# MARPOL Annex I reg. 1.11.1: west limit 5°36'W (Strait of Gibraltar), Black Sea boundary the 41°N parallel
mg = mg.intersection(box(-5.6, 29.0, 37.5, 46.0)).difference(box(26.0, 41.0, 30.5, 46.0))
groups["Mediterranean Sea area"] = [mg]
META = {
  "Baltic Sea area": ("2006-05-19", "MARPOL Annex VI reg. 14; Marine Regions eca_reg14_sox_pm"),
  "North Sea area": ("2007-11-22", "MARPOL Annex VI reg. 14; Marine Regions eca_reg14_sox_pm"),
  "North American area": ("2012-08-01", "MARPOL Annex VI reg. 14; Marine Regions eca_reg14_sox_pm (areas 1-3)"),
  "United States Caribbean sea area": ("2014-01-01", "MARPOL Annex VI reg. 14; Marine Regions eca_reg14_sox_pm"),
  "Mediterranean Sea area": ("2025-05-01", "MEPC.361(79); boundary = MARPOL Annex I reg. 1.11.1 (Mediterranean proper, W of 5°36'W excluded, Black Sea N of 41°N excluded) from Marine Regions IHO sea areas"),
}
for name, geoms in groups.items():
    g = unary_union([x.buffer(0) for x in geoms])
    # islands (holes) and slivers under 0.05 deg2 change neither a lane's share inside the zone nor the map
    from shapely.geometry import Polygon, MultiPolygon
    parts = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
    parts = [Polygon(pp.exterior, [h for h in pp.interiors if Polygon(h).area >= 0.05]) for pp in parts if pp.area >= 0.05]
    g = MultiPolygon(parts).simplify(TOL, preserve_topology=True)
    g = json.loads(json.dumps(mapping(g)), parse_float=lambda s: round(float(s), 3))
    feats.append({"type": "Feature", "properties": {"name": name, "sox_limit_pct": 0.10, "in_force": META[name][0], "source": META[name][1]}, "geometry": g})
fc = {"type": "FeatureCollection", "name": "sox_emission_control_areas",
      "description": "SOx emission control areas (0.10 % sulphur limit), simplified to 0.02 degrees for lane-share calculation and map display",
      "licence": "Marine Regions (VLIZ), CC-BY 4.0", "retrieved": "2026-10-28",
      "source_urls": ["https://geo.vliz.be/geoserver/MarineRegions/wfs (typeName MarineRegions:eca_reg14_sox_pm, MarineRegions:iho)"],
      "features": feats}
json.dump(fc, open(out, "w"), separators=(",", ":"))
for f in feats:
    g = shape(f["geometry"]); print(f["properties"]["name"], g.geom_type, round(g.area, 1), "deg2", len(json.dumps(f["geometry"])) // 1024, "KB", [round(v,1) for v in g.bounds])
