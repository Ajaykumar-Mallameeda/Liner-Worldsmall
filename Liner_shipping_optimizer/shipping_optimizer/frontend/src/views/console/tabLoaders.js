/**
 * One code chunk per console tab. MaritimeDashboard builds its React.lazy views from these loaders, and the
 * sidebar, sub-tab bar and command palette call preloadTab() on hover / focus so the chunk is usually in the
 * browser before the click lands. import() is cached by the browser, so preloading twice costs nothing.
 */
export const tabLoaders = {
  command_center: () => import('./CommandCenter.jsx'),
  network_intel: () => import('./NetworkIntelligence.jsx'),
  fleet_intel: () => import('./FleetIntelligence.jsx'),
  demand_intel: () => import('./DemandIntelligence.jsx'),
  port_intel: () => import('./PortIntelligence.jsx'),
  maritime_situation: () => import('./MaritimeSituation.jsx'),
  pipeline_ops: () => import('./PipelineOps.jsx'),
  regional_agents: () => import('./RegionalAgents.jsx'),
  ga_milp: () => import('./GaMilp.jsx'),
  feedback_loop: () => import('./FeedbackLoop.jsx'),
  decision_center: () => import('./DecisionCenter.jsx'),
  scenario_analysis: () => import('./ScenarioAnalysis.jsx'),
  benchmarks: () => import('./Benchmarks.jsx'),
  run_diff: () => import('./RunDiff.jsx'),
  whatif: () => import('./WhatIf.jsx'),
  telemetry: () => import('./Telemetry.jsx'),
  data_sources: () => import('./DataSources.jsx'),
  system_health: () => import('./SystemHealth.jsx'),
};

const started = new Set();

/** Start loading a tab's code; errors are left for the real load (ViewBoundary shows them). */
export function preloadTab(tabId) {
  if (!tabId || started.has(tabId) || !tabLoaders[tabId]) return;
  started.add(tabId);
  tabLoaders[tabId]().catch(() => started.delete(tabId));
}
