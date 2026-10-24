/**
 * MaritimeDashboard — Phase 12 REVISION
 * -------------------------------------
 * Unified Crucix-style command console shell.
 * Header, grouped navigation rail (8 groups, sub-tabs inside a group), scrollable workspace, system rail.
 *
 * Data contracts are UNCHANGED. useOptimizationState remains the
 * single source of truth. The /api/maritime/overview poll is preserved.
 *
 * The open tab lives in the URL hash (#/<group>/<tab>) so a reload or a shared link opens the same tab.
 * Each view is loaded on first use (React.lazy) to keep the first download small.
 */

import { useCallback, useEffect, useState, lazy, Suspense } from "react";
import { useOptimizationState } from '../hooks/useOptimizationState.js';
import { apiClient } from '../services/apiClient.js';
import { subscribeRun } from '../services/runSelection.js';
import { rawFilesFor } from '../services/rawDatasetService.js';
import { ensurePortNames } from '../utils/portLookup.js';
import { datasetKeyOf } from '../runtime/consoleSelectors.js';

// Console navigation and persistent top/bottom rails
import TopHeaderBar from '../components/console/TopHeaderBar.jsx';
import ConsoleSidebar from '../components/console/ConsoleSidebar.jsx';
import SubTabs from '../components/console/SubTabs.jsx';
import ViewBoundary from '../components/console/ViewBoundary.jsx';
import SystemRail from '../components/console/SystemRail.jsx';
import CommandPalette from '../components/console/CommandPalette.jsx';
import ViewSkeleton from '../components/console/ViewSkeleton.jsx';
import Toaster from '../components/common/Toaster.jsx';
import { toast } from '../services/toastStore.js';
import '../services/prefsStore.js'; // applies the saved theme / density before first paint

import navItems, { groupOfTab } from '../components/layout/navItems.js';

// Command console views, one chunk each
const CommandCenter = lazy(() => import('./console/CommandCenter.jsx'));
const NetworkIntelligence = lazy(() => import('./console/NetworkIntelligence.jsx'));
const FleetIntelligence = lazy(() => import('./console/FleetIntelligence.jsx'));
const DemandIntelligence = lazy(() => import('./console/DemandIntelligence.jsx'));
const PortIntelligence = lazy(() => import('./console/PortIntelligence.jsx'));
const MaritimeSituation = lazy(() => import('./console/MaritimeSituation.jsx'));
const PipelineOps = lazy(() => import('./console/PipelineOps.jsx'));
const RegionalAgents = lazy(() => import('./console/RegionalAgents.jsx'));
const GaMilp = lazy(() => import('./console/GaMilp.jsx'));
const FeedbackLoop = lazy(() => import('./console/FeedbackLoop.jsx'));
const DecisionCenter = lazy(() => import('./console/DecisionCenter.jsx'));
const ScenarioAnalysis = lazy(() => import('./console/ScenarioAnalysis.jsx'));
const Benchmarks = lazy(() => import('./console/Benchmarks.jsx'));
const Telemetry = lazy(() => import('./console/Telemetry.jsx'));
const DataSources = lazy(() => import('./console/DataSources.jsx'));
const SystemHealth = lazy(() => import('./console/SystemHealth.jsx'));

const TAB_IDS = new Set(navItems.map((n) => n.id));
// Tabs that read the selected run's file; they show a skeleton until it has loaded once.
const RUN_TABS = new Set(['command_center', 'network_intel', 'fleet_intel', 'demand_intel', 'port_intel', 'pipeline_ops',
  'regional_agents', 'ga_milp', 'feedback_loop', 'decision_center', 'scenario_analysis', 'system_health']);
const DEFAULT_TAB = 'command_center';

function tabFromHash() {
  const parts = (window.location.hash || '').replace(/^#\/?/, '').split('/');
  const tab = parts[parts.length - 1];
  return TAB_IDS.has(tab) ? tab : DEFAULT_TAB;
}

export default function App() {
  const optimizationState = useOptimizationState();
  const [activeNav, setActiveNavState] = useState(tabFromHash);
  const [lastTabByGroup, setLastTabByGroup] = useState({});
  const [navOpen, setNavOpen] = useState(false);
  const [presentationMode, setPresentationMode] = useState(false);
  const [demoMode] = useState(false);
  const [maritimeOverview, setMaritimeOverview] = useState(null);
  const [runtime, setRuntime] = useState(null);
  const [runtimeFailed, setRuntimeFailed] = useState(false);

  const setActiveNav = useCallback((tab) => {
    if (!TAB_IDS.has(tab)) return;
    const g = groupOfTab(tab);
    setActiveNavState(tab);
    setLastTabByGroup((m) => ({ ...m, [g.id]: tab }));
    const hash = `#/${g.id}/${tab}`;
    if (window.location.hash !== hash) window.history.replaceState(null, '', hash);
  }, []);

  // Back/forward and hand-edited hashes.
  useEffect(() => {
    const onHash = () => setActiveNavState(tabFromHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  // Close the drawer with Escape.
  useEffect(() => {
    if (!navOpen) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') setNavOpen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [navOpen]);

  useEffect(() => {
    const handleFSChange = () => setPresentationMode(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', handleFSChange);
    return () => document.removeEventListener('fullscreenchange', handleFSChange);
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer = null;
    const load = async () => {
      if (document.hidden) return;
      try {
        const r = await fetch('/api/maritime/overview');
        if (r.ok && !cancelled) setMaritimeOverview(await r.json());
      } catch (_) { /* noop */ }
    };
    load();
    timer = setInterval(load, 30000);
    return () => { cancelled = true; if (timer) clearInterval(timer); };
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer = null;
    let announce = false;   // toast once after a run switch, not on every poll
    const load = async () => {
      if (document.hidden) return;
      try {
        const norm = await apiClient.loadRuntimeTruth().catch(() => null);
        if (cancelled) return;
        if (norm) {
          setRuntime(norm);   // same object on 304: React skips the render
          setRuntimeFailed(false);
          if (announce) { announce = false; toast(`Loaded ${norm.source?.label || 'run'}`); }
        } else {
          setRuntimeFailed(true);   // views then show their own "not available" states instead of a skeleton
        }
      } catch (_) { /* noop */ }
    };
    load();
    timer = setInterval(load, 5000);
    const unsubscribe = subscribeRun(() => { setRuntime(null); setRuntimeFailed(false); announce = true; load(); });
    return () => { cancelled = true; if (timer) clearInterval(timer); unsubscribe(); };
  }, []);

  // Real port names for the run's dataset (ports.csv "name" column); re-render once they arrive.
  const [, setPortNamesVersion] = useState(0);
  const rawDir = rawFilesFor(datasetKeyOf(runtime))?.dir;
  useEffect(() => {
    if (!rawDir) return;
    let cancelled = false;
    ensurePortNames(rawDir).then(() => { if (!cancelled) setPortNamesVersion((v) => v + 1); });
    return () => { cancelled = true; };
  }, [rawDir]);

  useEffect(() => {
    if (!demoMode) return;
    const tabs = navItems.map((n) => n.id);
    const interval = setInterval(() => {
      setActiveNavState((prev) => {
        const idx = tabs.indexOf(prev);
        return tabs[(idx + 1) % tabs.length];
      });
    }, 8000);
    return () => clearInterval(interval);
  }, [demoMode]);

  const common = { optimizationState, maritimeOverview, runtime };

  const renderMain = () => {
    switch (activeNav) {
      case 'command_center':     return <CommandCenter {...common} />;
      case 'network_intel':      return <NetworkIntelligence {...common} />;
      case 'fleet_intel':        return <FleetIntelligence {...common} />;
      case 'demand_intel':       return <DemandIntelligence {...common} />;
      case 'port_intel':         return <PortIntelligence {...common} />;
      case 'maritime_situation': return <MaritimeSituation maritimeOverview={maritimeOverview} />;
      case 'pipeline_ops':       return <PipelineOps {...common} />;
      case 'regional_agents':    return <RegionalAgents {...common} />;
      case 'ga_milp':            return <GaMilp optimizationState={optimizationState} runtime={runtime} />;
      case 'feedback_loop':      return <FeedbackLoop {...common} />;
      case 'decision_center':    return <DecisionCenter {...common} />;
      case 'scenario_analysis':  return <ScenarioAnalysis {...common} />;
      case 'benchmarks':         return <Benchmarks />;
      case 'telemetry':          return <Telemetry maritimeOverview={maritimeOverview} />;
      case 'data_sources':       return <DataSources maritimeOverview={maritimeOverview} />;
      case 'system_health':      return <SystemHealth maritimeOverview={maritimeOverview} runtime={runtime} />;
      default:                   return null;
    }
  };

  const isCommandCenter = activeNav === 'command_center';
  const group = groupOfTab(activeNav);

  return (
    <div
      className={`console-shell ${presentationMode ? 'presentation-mode' : ''} ${isCommandCenter ? 'console-shell--command' : ''}`}
      style={{ color: 'var(--cx-text)', fontFamily: 'var(--cx-sans)' }}
    >
      <a className="cx-skip-link" href="#console-workspace">Skip to content</a>
      <TopHeaderBar
        optimizationState={optimizationState}
        runtime={runtime}
        navOpen={navOpen}
        onToggleNav={() => setNavOpen((v) => !v)}
      />

      <div className="console-main">
        <ConsoleSidebar
          activeNav={activeNav}
          onNavChange={setActiveNav}
          optimizationState={optimizationState}
          lastTabByGroup={lastTabByGroup}
          open={navOpen}
          onClose={() => setNavOpen(false)}
        />

        <main id="console-workspace" className="cx-workspace" role="main" aria-label={`${group.label} view`} tabIndex={-1}>
          <SubTabs group={group} activeTab={activeNav} onSelect={setActiveNav} />
          <ViewBoundary key={activeNav} label={navItems.find((n) => n.id === activeNav)?.label || group.label}>
            <Suspense fallback={<ViewSkeleton label={group.label} />}>
              {runtime == null && !runtimeFailed && RUN_TABS.has(activeNav) ? <ViewSkeleton label="the run" /> : renderMain()}
            </Suspense>
          </ViewBoundary>
        </main>
      </div>

      <SystemRail maritimeOverview={maritimeOverview} runtime={runtime} />
      <CommandPalette runtime={runtime} onNavigate={setActiveNav} />
      <Toaster />
    </div>
  );
}
