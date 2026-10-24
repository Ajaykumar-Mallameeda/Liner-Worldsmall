/**
 * rawDatasetService.js
 * --------------------
 * Service layer to load, parse, and validate raw project CSV datasets
 * and calculate authoritative metrics for Port Intelligence.
 *
 * Reads the same files the engine reads for the run's dataset (src/data/dataset_registry.py),
 * served read-only by the backend under /data/raw/<dir>/.
 */

// dataset key (any case, with or without dash) -> raw directory and the engine's demand / fleet files
const RAW_FILES = {
  worldsmall: { dir: 'WorldSmall', demand: 'Demand_WorldSmall_Fixed_Sep.csv', fleet: 'fleet_WorldSmall.csv' },
  baltic:     { dir: 'baltic',     demand: 'Demand_Baltic.csv',               fleet: 'fleet_Baltic.csv' },
  waf:        { dir: 'WAF',        demand: 'Demand_WAF.csv',                  fleet: 'fleet_WAF.csv' },
  world500:   { dir: 'World-500',  demand: 'Demand_World-500.csv',            fleet: 'fleet_World-500.csv' },
  world1000:  { dir: 'World-1000', demand: 'Demand_World-1000.csv',           fleet: 'fleet_World-1000.csv' },
};

export function rawFilesFor(datasetKey) {
  const k = String(datasetKey || 'worldsmall').toLowerCase().replace(/[^a-z0-9]/g, '');
  return RAW_FILES[k] || null;
}

export async function fetchAndParseRawDatasets(datasetKey = 'worldsmall') {
  const spec = rawFilesFor(datasetKey);
  const base = spec ? `/data/raw/${spec.dir}/` : null;
  const results = {
    ports: { status: 'loading', records: 0, metrics: {} },
    distance: { status: 'loading', records: 0, metrics: {} },
    demand: { status: 'loading', records: 0, metrics: {} },
    fleet: { status: 'loading', records: 0, metrics: {} },
    lastFetchedAt: Date.now(),
    dataset: spec ? spec.dir : null,
  };
  if (!spec) {
    ['ports', 'distance', 'demand', 'fleet'].forEach((k) => { results[k] = { status: 'offline', records: 0, metrics: {}, error: 'unknown dataset ' + datasetKey }; });
    return results;
  }

  // Helper to parse TSV / CSV text
  const parseDelimited = (text, delimiter = '\t') => {
    if (!text) return { headers: [], rows: [] };
    const lines = text.trim().split(/\r?\n/).filter((l) => l.trim().length > 0);
    if (lines.length === 0) return { headers: [], rows: [] };
    const headers = lines[0].split(delimiter).map((h) => h.trim());
    const rows = lines.slice(1).map((line) => {
      const parts = line.split(delimiter);
      const row = {};
      headers.forEach((h, i) => {
        row[h] = parts[i] ? parts[i].trim() : '';
      });
      return row;
    });
    return { headers, rows };
  };

  const fetchDataset = (name) => fetch(base + name);

  // 1. ports.csv
  try {
    const res = await fetchDataset('ports.csv');
    if (res.ok) {
      const text = await res.text();
      const { headers, rows } = parseDelimited(text, '\t');
      const validCoords = rows.filter((r) => r.Latitude && r.Longitude && !isNaN(Number(r.Latitude))).length;
      results.ports = {
        status: 'healthy',
        filename: 'ports.csv',
        records: rows.length,
        networkPorts: rows.length,
        headers,
        metrics: {
          totalPorts: rows.length,
          activeNetworkPorts: rows.length,
          coordCompleteness: rows.length > 0 ? `${((validCoords / rows.length) * 100).toFixed(0)}%` : null,
          uniqueCountries: new Set(rows.map((r) => r.Country).filter(Boolean)).size,
          cabotageRegions: new Set(rows.map((r) => r.Cabotage_Region).filter(Boolean)).size,
        },
        rows,
      };
    } else {
      results.ports.status = 'offline';
    }
  } catch (err) {
    results.ports = { status: 'error', error: err.message, records: 0 };
  }

  // 2. dist_dense.csv
  try {
    const res = await fetchDataset('dist_dense.csv');
    if (res.ok) {
      const text = await res.text();
      const { headers, rows } = parseDelimited(text, '\t');
      let minDist = Infinity, maxDist = -Infinity, sumDist = 0, distCount = 0;
      const origins = new Set(), dests = new Set();

      rows.forEach((r) => {
        const d = parseFloat(r.Distance);
        if (!isNaN(d)) {
          minDist = Math.min(minDist, d);
          maxDist = Math.max(maxDist, d);
          sumDist += d;
          distCount++;
        }
        if (r.fromUNLOCODe) origins.add(r.fromUNLOCODe);
        if (r.ToUNLOCODE) dests.add(r.ToUNLOCODE);
      });

      results.distance = {
        status: 'healthy',
        filename: 'dist_dense.csv',
        records: rows.length,
        headers,
        metrics: {
          totalDistanceRecords: rows.length,
          problemLanes: rows.length,
          avgDistance: distCount > 0 ? Math.round(sumDist / distCount) : 0,
          minDistance: minDist !== Infinity ? minDist : 0,
          maxDistance: maxDist !== -Infinity ? maxDist : 0,
          uniqueOrigins: origins.size,
          uniqueDestinations: dests.size,
        },
      };
    } else {
      results.distance.status = 'offline';
    }
  } catch (err) {
    results.distance = { status: 'error', error: err.message, records: 0 };
  }

  // 3. demand file used by the engine for this dataset
  try {
    const res = await fetchDataset(spec.demand);
    if (res.ok) {
      const text = await res.text();
      const { headers, rows } = parseDelimited(text, '\t');
      let sumFFE = 0, sumRevenue = 0;
      const origins = new Set(), dests = new Set();

      rows.forEach((r) => {
        const ffe = parseFloat(r.FFEPerWeek);
        const rev = parseFloat(r.Revenue_1);
        if (!isNaN(ffe)) sumFFE += ffe;
        if (!isNaN(rev)) sumRevenue += rev;
        if (r.Origin) origins.add(r.Origin);
        if (r.Destination) dests.add(r.Destination);
      });

      results.demand = {
        status: 'healthy',
        filename: spec.demand,
        records: rows.length,
        headers,
        metrics: {
          demandRecords: rows.length,
          totalFFE: Math.round(sumFFE),
          totalTEU: Math.round(sumFFE * 2),
          uniqueOrigins: origins.size,
          uniqueDestinations: dests.size,
          avgRevenuePerFFE: sumFFE > 0 ? Math.round(sumRevenue / sumFFE) : 0,
        },
      };
    } else {
      results.demand.status = 'offline';
    }
  } catch (err) {
    results.demand = { status: 'error', error: err.message, records: 0 };
  }

  // 4. fleet file used by the engine for this dataset
  try {
    const res = await fetchDataset(spec.fleet);
    if (res.ok) {
      const text = await res.text();
      const { headers, rows } = parseDelimited(text, '\t');
      let totalVessels = 0;
      const classes = [];

      rows.forEach((r) => {
        const q = parseInt(r.Quantity, 10);
        if (!isNaN(q)) {
          totalVessels += q;
          classes.push({ name: r['Vessel class'] || 'Class', quantity: q });
        }
      });

      results.fleet = {
        status: 'healthy',
        filename: spec.fleet,
        records: rows.length,
        headers,
        metrics: {
          totalVessels,
          vesselClassesCount: classes.length,
          classes,
        },
      };
    } else {
      results.fleet.status = 'offline';
    }
  } catch (err) {
    results.fleet = { status: 'error', error: err.message, records: 0 };
  }

  return results;
}
