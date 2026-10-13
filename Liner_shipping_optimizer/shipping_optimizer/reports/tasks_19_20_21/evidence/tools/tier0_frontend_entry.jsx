// Entry point bundled by tier0_frontend.mjs: the REAL frontend consumers of the margin / verdict
// (components + the runtime adapter that feeds them), re-exported with React's server renderer.
// SRC is replaced by the build script with the frontend/src directory under test.
export { createElement } from 'react';
export { renderToStaticMarkup } from 'react-dom/server';
export { normalizeRuntime } from '__SRC__/runtime/runtimeAdapter.js';
export { default as SummaryView } from '__SRC__/components/overview/SummaryView.jsx';
export { default as RegionCard } from '__SRC__/components/regions/RegionCard.jsx';
export { default as RegionalIntelligence } from '__SRC__/components/regions/RegionalIntelligence.jsx';
export { default as OptimizationInsights } from '__SRC__/components/optimization/OptimizationInsights.jsx';
export { default as ExportPanel } from '__SRC__/components/optimization/ExportPanel.jsx';
export { default as BenchmarkBadge, BENCHMARKS } from '__SRC__/components/common/BenchmarkBadge.jsx';
export { default as CommandCenter } from '__SRC__/views/console/CommandCenter.jsx';
