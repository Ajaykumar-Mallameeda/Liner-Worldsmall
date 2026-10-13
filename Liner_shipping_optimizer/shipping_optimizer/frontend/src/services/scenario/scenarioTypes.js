/**
 * Scenario Analysis — Types, Categories, Presets & Thresholds
 * ============================================================
 * Defines the scenario data structures, categories, adjustable parameters,
 * standard maritime presets, and deterministic severity thresholds.
 */

export const SCENARIO_CATEGORIES = {
  ECONOMIC: {
    id: 'economic',
    label: 'Economic',
    icon: '💲',
    description: 'Bunker fuel prices, port tariff adjustments, freight revenue rates, and vessel capital costs.',
  },
  WEATHER: {
    id: 'weather',
    label: 'Weather & Metocean',
    icon: '🌊',
    description: 'Adverse sea states, wave/wind resistance, vessel steaming speed reductions, and weather routing delays.',
  },
  NETWORK: {
    id: 'network',
    label: 'Network & Chokepoints',
    icon: '⚓',
    description: 'Key maritime canal transit delays (Suez, Panama), chokepoint congestion, and port terminal closures.',
  },
  DEMAND: {
    id: 'demand',
    label: 'Demand Dynamics',
    icon: '📦',
    description: 'Global container volume shifts and regional trade lane demand contractions or surges.',
  },
  FLEET: {
    id: 'fleet',
    label: 'Fleet Constraints',
    icon: '🚢',
    description: 'Vessel capacity reductions, fleet availability changes, and fuel efficiency adjustments.',
  },
};

export const DEFAULT_PARAMETERS = {
  // Economic
  fuelPriceMultiplier: 1.0, // 1.0 = baseline, 1.25 = +25%
  portCostMultiplier: 1.0,  // 1.0 = baseline
  revenueMultiplier: 1.0,   // 1.0 = baseline (freight rates)
  vesselCostMultiplier: 1.0,// 1.0 = baseline

  // Weather
  weatherSeverity: 'normal', // normal | moderate | severe | extreme
  weatherSpeedFactor: 1.0,   // 1.0 = 100% speed, 0.75 = 25% speed cut
  weatherAffectedRegions: ['all'], // 'all' or list of region names

  // Network & Chokepoint
  chokepointId: 'none', // none | suez | panama | malacca | hormuz | bab_el_mandeb
  chokepointDelayHours: 0, // 0 - 240 hours
  chokepointCongestionLevel: 'normal', // normal | moderate | high | severe | closed

  // Port Closure
  closedPortCode: 'none', // 'none' or UN/LOCODE e.g. 'USLAX', 'NLRTM', 'CNSHA'
  portClosureSeverity: 'closed', // restricted | closed

  // Demand
  globalDemandMultiplier: 1.0, // 1.0 = baseline, 1.25 = +25%
  regionalDemandMultipliers: {
    Asia: 1.0,
    Europe: 1.0,
    Americas: 1.0,
    'Middle East': 1.0,
    Africa: 1.0,
  },

  // Fleet
  vesselCapacityMultiplier: 1.0, // 1.0 = 100% capacity
  vesselAvailabilityMultiplier: 1.0, // 1.0 = 100% active vessels
  fuelEfficiencyFactor: 1.0, // 1.0 = baseline, 0.9 = 10% more efficient
};

export const SCENARIO_PRESETS = [
  {
    id: 'fuel_shock',
    name: 'Bunker Fuel Shock (+50%)',
    category: 'ECONOMIC',
    badge: '+50% Fuel',
    description: 'Global crude oil escalation increases VLSFO/MGO bunker prices by 50% across all bunkering hubs.',
    parameters: {
      fuelPriceMultiplier: 1.50,
    },
    activeScenarios: ['fuel_cost'],
  },
  {
    id: 'severe_weather',
    name: 'Severe Metocean Storm Cycle',
    category: 'WEATHER',
    badge: 'Storm Cycle',
    description: 'Adverse winter storms in North Pacific and North Atlantic enforce a 25% steaming speed reduction and heavy sea routing.',
    parameters: {
      weatherSeverity: 'severe',
      weatherSpeedFactor: 0.75,
      weatherAffectedRegions: ['Asia', 'Europe', 'Americas'],
    },
    activeScenarios: ['weather_severity'],
  },
  {
    id: 'suez_disruption',
    name: 'Suez Canal Transit Crisis (+72h)',
    category: 'NETWORK',
    badge: 'Suez Delay',
    description: 'Critical bottleneck congestion in the Red Sea / Suez corridor causes average 72-hour transit delays and additional holding burn.',
    parameters: {
      chokepointId: 'suez',
      chokepointDelayHours: 72,
      chokepointCongestionLevel: 'severe',
    },
    activeScenarios: ['chokepoint_delay'],
  },
  {
    id: 'panama_restriction',
    name: 'Panama Canal Draft / Transit Restriction',
    category: 'NETWORK',
    badge: 'Panama Delay',
    description: 'Freshwater draft restrictions in Gatun Lake restrict daily booking slots, inducing a 96-hour queue on Transpacific / Transatlantic loops.',
    parameters: {
      chokepointId: 'panama',
      chokepointDelayHours: 96,
      chokepointCongestionLevel: 'high',
    },
    activeScenarios: ['chokepoint_delay'],
  },
  {
    id: 'global_demand_surge',
    name: 'Global Peak Demand Surge (+25%)',
    category: 'DEMAND',
    badge: '+25% Demand',
    description: 'Holiday peak season drives a 25% surge in container booking volumes across global liner trade lanes.',
    parameters: {
      globalDemandMultiplier: 1.25,
      regionalDemandMultipliers: {
        Asia: 1.30,
        Europe: 1.25,
        Americas: 1.25,
        'Middle East': 1.15,
        Africa: 1.15,
      },
    },
    activeScenarios: ['demand_change'],
  },
  {
    id: 'uslax_port_closure',
    name: 'Port of Los Angeles (USLAX) Disruption',
    category: 'NETWORK',
    badge: 'USLAX Closed',
    description: 'Terminal outage or labor stoppage completely suspends container operations at Port of Los Angeles.',
    parameters: {
      closedPortCode: 'USLAX',
      portClosureSeverity: 'closed',
    },
    activeScenarios: ['port_closure'],
  },
  {
    id: 'combined_global_shock',
    name: 'Combined Geopolitical & Economic Shock',
    category: 'MULTIPLE',
    badge: 'Triple Shock',
    description: 'Simultaneous 30% fuel cost surge, 72h Suez transit bottleneck, and severe winter weather across East-West trade routes.',
    parameters: {
      fuelPriceMultiplier: 1.30,
      weatherSeverity: 'severe',
      weatherSpeedFactor: 0.80,
      chokepointId: 'suez',
      chokepointDelayHours: 72,
      chokepointCongestionLevel: 'high',
    },
    activeScenarios: ['fuel_cost', 'weather_severity', 'chokepoint_delay'],
  },
];

export const CHOKEPOINT_DEFINITIONS = {
  suez: {
    id: 'suez',
    name: 'Suez Canal',
    lat: 30.5,
    lon: 32.3,
    corridors: ['Asia-Europe', 'Med-Asia', 'Europe-Middle East', 'Asia-East Coast NA'],
    shareOfWorldTrade: '12%',
    description: 'Connects Mediterranean Sea to Red Sea. Primary corridor for Asia-Europe and Asia-US East Coast liner trades.',
  },
  panama: {
    id: 'panama',
    name: 'Panama Canal',
    lat: 9.1,
    lon: -79.7,
    corridors: ['Asia-US East Coast', 'South America-Europe', 'US West Coast-Europe'],
    shareOfWorldTrade: '5%',
    description: 'Connects Atlantic to Pacific Ocean. Primary conduit for Asia to US East Coast and Gulf Coast all-water services.',
  },
  malacca: {
    id: 'malacca',
    name: 'Strait of Malacca',
    lat: 2.5,
    lon: 101.5,
    corridors: ['Far East-Europe', 'Far East-Middle East', 'Far East-South Asia'],
    shareOfWorldTrade: '25%',
    description: 'Main shipping channel between Indian and Pacific Oceans.',
  },
  hormuz: {
    id: 'hormuz',
    name: 'Strait of Hormuz',
    lat: 26.5,
    lon: 56.5,
    corridors: ['Persian Gulf-Asia', 'Persian Gulf-Europe', 'Middle East feeder'],
    shareOfWorldTrade: '20% of oil',
    description: 'Strategic passage between Persian Gulf and Gulf of Oman.',
  },
  bab_el_mandeb: {
    id: 'bab_el_mandeb',
    name: 'Bab el-Mandeb',
    lat: 12.6,
    lon: 43.3,
    corridors: ['Red Sea gateway', 'Asia-Europe', 'East Africa-Med'],
    shareOfWorldTrade: '10%',
    description: 'Chokepoint between Yemen on Arabian Peninsula and Djibouti in Horn of Africa.',
  },
};

export const SEVERITY_THRESHOLDS = {
  // Rules for deterministic scenario impact classification
  CRITICAL: {
    level: 'CRITICAL',
    color: '#ef4444',
    badge: 'CRITICAL IMPACT',
    rules: [
      { metric: 'profitDropPct', threshold: 30, desc: 'Weekly profit drops >30%' },
      { metric: 'coverageDropPp', threshold: 10, desc: 'Coverage drops >10 percentage points' },
      { metric: 'unservedDemandSurgePct', threshold: 40, desc: 'Unserved demand increases >40%' },
    ],
  },
  HIGH: {
    level: 'HIGH',
    color: '#f59e0b',
    badge: 'HIGH IMPACT',
    rules: [
      { metric: 'profitDropPct', threshold: 15, desc: 'Weekly profit drops 15% - 30%' },
      { metric: 'coverageDropPp', threshold: 5, desc: 'Coverage drops 5 - 10 pp' },
      { metric: 'unservedDemandSurgePct', threshold: 20, desc: 'Unserved demand increases 20% - 40%' },
    ],
  },
  MODERATE: {
    level: 'MODERATE',
    color: '#06b6d4',
    badge: 'MODERATE IMPACT',
    rules: [
      { metric: 'profitDropPct', threshold: 5, desc: 'Weekly profit drops 5% - 15%' },
      { metric: 'coverageDropPp', threshold: 2, desc: 'Coverage drops 2 - 5 pp' },
      { metric: 'unservedDemandSurgePct', threshold: 5, desc: 'Unserved demand increases 5% - 20%' },
    ],
  },
  LOW: {
    level: 'LOW',
    color: '#10b981',
    badge: 'LOW IMPACT',
    rules: [
      { metric: 'profitDropPct', threshold: 0, desc: 'Weekly profit variation < 5%' },
    ],
  },
};
