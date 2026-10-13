/**
 * Fleet intelligence — computed from selected_services (runtime truth).
 * No mock data. No assumptions beyond what the backend provides.
 */

export function computeFleetStats(selectedServices = []) {
  if (!selectedServices || selectedServices.length === 0) {
    return {
      totalVessels: 0,
      vesselClasses: {},
      totalCapacity: 0,
      totalLoad: 0,
      utilizationPct: null,
      legLoadFactorPct: null,
      serviceCount: 0,
      servicesByRegion: {},
    };
  }

  const classes = {};
  let totalCap = 0;
  let totalLoad = 0;
  let carriedLegs = 0;
  let offeredLegs = 0;
  let vesselsAssigned = 0;
  let vesselsKnown = true;
  const regionCounts = {};

  selectedServices.forEach(s => {
    const cls = s.vessel_class || 'Unknown';
    classes[cls] = (classes[cls] || 0) + 1;
    totalCap += s.capacity || 0;
    totalLoad += s.load || 0;
    if (s.offered_teu_legs != null && s.carried_teu_legs != null) {
      carriedLegs += Number(s.carried_teu_legs);
      offeredLegs += Number(s.offered_teu_legs);
    }
    if (s.vessels != null) vesselsAssigned += Number(s.vessels); else vesselsKnown = false;
    const reg = s.region || 'Unknown';
    regionCounts[reg] = (regionCounts[reg] || 0) + 1;
  });

  const sorted = Object.entries(classes).sort((a, b) => b[1] - a[1]);

  return {
    // vessels assigned = sum of the plan's vessel counts (NOT the number of services); null when the field is absent
    totalVessels: vesselsKnown ? vesselsAssigned : selectedServices.length,
    vesselsAssigned: vesselsKnown ? vesselsAssigned : null,
    serviceCount: selectedServices.length,
    vesselClasses: Object.fromEntries(sorted),
    vesselClassList: sorted.map(([cls, count]) => ({ cls, count, pct: ((count / selectedServices.length) * 100).toFixed(0) })),
    totalCapacity: totalCap,
    totalLoad,
    // leg load factor = carried TEU-legs / offered TEU-legs (capacity x weekly departures x legs).
    // The weekly cargo `totalLoad` divided by the per-departure `totalCapacity` is NOT a utilisation
    // (it exceeds 100 % for any service with several legs or departures) and is no longer computed.
    legLoadFactorPct: offeredLegs > 0 ? Number(((carriedLegs / offeredLegs) * 100).toFixed(1)) : null,
    utilizationPct: offeredLegs > 0 ? Number(((carriedLegs / offeredLegs) * 100).toFixed(1)) : null,
    servicesByRegion: regionCounts,
  };
}

export function computeRegionalInsights(regions = []) {
  if (!regions || regions.length === 0) return {};

  const withProfit = regions.filter(r => r.profit != null);
  const withCoverage = regions.filter(r => r.coverage != null);
  const withServices = regions.filter(r => r.services != null);

  const bestProfit = withProfit.length > 0 ? withProfit.reduce((a, b) => (a.profit || 0) > (b.profit || 0) ? a : b) : null;
  const worstProfit = withProfit.length > 0 ? withProfit.reduce((a, b) => (a.profit || 0) < (b.profit || 0) ? a : b) : null;
  const bestCoverage = withCoverage.length > 0 ? withCoverage.reduce((a, b) => (a.coverage || 0) > (b.coverage || 0) ? a : b) : null;
  const worstCoverage = withCoverage.length > 0 ? withCoverage.reduce((a, b) => (a.coverage || 0) < (b.coverage || 0) ? a : b) : null;
  const mostServices = withServices.length > 0 ? withServices.reduce((a, b) => (a.services || 0) > (b.services || 0) ? a : b) : null;
  const bestMargin = regions.filter(r => r.margin != null).reduce((a, b) => (a.margin || 0) > (b.margin || 0) ? a : b, regions[0] || null);

  return {
    bestProfit,
    worstProfit,
    bestCoverage,
    worstCoverage,
    mostServices,
    bestMargin,
    totalProfit: regions.reduce((s, r) => s + (r.profit || 0), 0),
    avgCoverage: regions.length > 0 ? regions.reduce((s, r) => s + (r.coverage || 0), 0) / regions.length : 0,
  };
}
