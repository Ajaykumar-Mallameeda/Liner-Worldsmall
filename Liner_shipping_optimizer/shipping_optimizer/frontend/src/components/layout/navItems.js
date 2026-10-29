// Navigation: 8 sidebar groups, each with one or more tabs (2026-10-24 restructure of the 15 flat tabs).
// Tab ids are unchanged so every view keeps its id; a group with several tabs shows a sub-tab bar.
export const navGroups = [
  { id: 'overview',     label: 'Overview',       icon: '❖', tabs: [
    { id: 'command_center',     label: 'Command Center' },
  ] },
  { id: 'network',      label: 'Network',        icon: '⊕', tabs: [
    { id: 'network_intel',      label: 'Routes & Services' },
    { id: 'transshipment',      label: 'Transshipment' },
    { id: 'transit_finder',     label: 'Transit finder' },
    { id: 'schedules',          label: 'Schedules' },
    { id: 'sea_conditions',     label: 'Sea state & currents' },
  ] },
  { id: 'demand_ports', label: 'Demand & Ports', icon: '◍', tabs: [
    { id: 'demand_intel',       label: 'Demand' },
    { id: 'port_intel',         label: 'Ports' },
  ] },
  { id: 'fleet',        label: 'Fleet',          icon: '⎈', tabs: [
    { id: 'fleet_intel',        label: 'Fleet' },
  ] },
  { id: 'optimization', label: 'Optimization',   icon: '◆', tabs: [
    { id: 'decision_center',    label: 'Decision' },
    { id: 'pipeline_ops',       label: 'Pipeline' },
    { id: 'regional_agents',    label: 'Regional Agents' },
    { id: 'ga_milp',            label: 'GA · MILP' },
    { id: 'feedback_loop',      label: 'Feedback Loop' },
  ] },
  { id: 'benchmarks',   label: 'Benchmarks',     icon: '▦', tabs: [
    { id: 'benchmarks',         label: '30-seed benchmark' },
    { id: 'run_diff',           label: 'Run diff' },
  ] },
  { id: 'scenarios',    label: 'Scenarios',      icon: '⌁', tabs: [
    { id: 'scenario_analysis',  label: 'Scenario Analysis' },
    { id: 'whatif',             label: 'What-if' },
    { id: 'emissions',          label: 'Emissions & ETS' },
    { id: 'reliability',        label: 'Reliability & congestion' },
  ] },
  { id: 'system',       label: 'System',         icon: '▣', tabs: [
    { id: 'system_health',      label: 'Health' },
    { id: 'maritime_situation', label: 'Maritime' },
    { id: 'telemetry',          label: 'Telemetry' },
    { id: 'data_sources',       label: 'Data Sources' },
  ] },
];

/** The group that contains a tab id (falls back to the first group). */
export function groupOfTab(tabId) {
  return navGroups.find((g) => g.tabs.some((t) => t.id === tabId)) || navGroups[0];
}

/** Flat tab list, kept for callers that iterate every tab (demo mode). */
const navItems = navGroups.flatMap((g) => g.tabs.map((t) => ({ ...t, icon: g.icon, section: g.label, group: g.id })));

export default navItems;
