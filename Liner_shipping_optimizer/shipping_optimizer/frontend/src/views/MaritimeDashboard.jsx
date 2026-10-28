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
 * Each view is loaded on first use (React.lazy) to keep the first download small; hovering a tab preloads it.
 *
 * Tab switching (2026-10-24 motion round): only the main pane crossfades (view transition named "main-pane");
 * sub-tabs slide in from their side; each tab keeps its scroll position; keys 1–8 pick a group and [ / ] step
 * sub-tabs; presentation mode steps through the main views on a timer.
 */

import { useCallback, useEffect, useLayoutEffect, useRef, useState, lazy, Suspense } from "react";
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
import ViewSkeleton, { Reveal } from '../components/console/ViewSkeleton.jsx';
import PresentationHud from '../components/console/PresentationHud.jsx';
import Toaster from '../components/common/Toaster.jsx';
import { toast } from '../services/toastStore.js';
import '../services/prefsStore.js'; // applies the saved theme / density / motion before first paint
import { withViewTransition } from '../utils/motion.js';

import navItems, { navGroups, groupOfTab } from '../components/layout/navItems.js';
import { tabLoaders } from './console/tabLoaders.js';

// Command console views, one chunk each (tabLoaders also serves hover preloading)
const CommandCenter = lazy(tabLoaders.command_center);
const NetworkIntelligence = lazy(tabLoaders.network_intel);
const FleetIntelligence = lazy(tabLoaders.fleet_intel);
const DemandIntelligence = lazy(tabLoaders.demand_intel);
const PortIntelligence = lazy(tabLoaders.port_intel);
const MaritimeSituation = lazy(tabLoaders.maritime_situation);
const PipelineOps = lazy(tabLoaders.pipeline_ops);
const RegionalAgents = lazy(tabLoaders.regional_agents);
const GaMilp = lazy(tabLoaders.ga_milp);
const FeedbackLoop = lazy(tabLoaders.feedback_loop);
const DecisionCenter = lazy(tabLoaders.decision_center);
const ScenarioAnalysis = lazy(tabLoaders.scenario_analysis);
const Benchmarks = lazy(tabLoaders.benchmarks);
const RunDiff = lazy(tabLoaders.run_diff);
const WhatIf = lazy(tabLoaders.whatif);
const Telemetry = lazy(tabLoaders.telemetry);
const DataSources = lazy(tabLoaders.data_sources);
const SystemHealth = lazy(tabLoaders.system_health);

// Presentation mode: the main views in story order, each shown for PRESENT_DWELL_MS.
const PRESENT_TABS = ['command_center', 'network_intel', 'demand_intel', 'port_intel', 'fleet_intel', 'decision_center', 'benchmarks', 'scenario_analysis'];
const PRESENT_DWELL_MS = 12000;

const isTyping = (el) => /^(INPUT|TEXTAREA|SELECT)$/.test(el?.tagName || '') || el?.isContentEditable;

/** Restores the workspace scroll position saved for a tab once its view has rendered. */
function ScrollRestore({ tab, positions }) {
  useLayoutEffect(() => {
    const ws = document.getElementById('console-workspace');
    if (ws) ws.scrollTop = positions[tab] || 0;
  }, [tab]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

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

  // Refs mirror the state for the window-level key handlers and the transition direction.
  const activeRef = useRef(activeNav);
  const lastTabRef = useRef(lastTabByGroup);
  const scrollByTab = useRef({});
  useEffect(() => { activeRef.current = activeNav; }, [activeNav]);
  useEffect(() => { lastTabRef.current = lastTabByGroup; }, [lastTabByGroup]);

  const setActiveNav = useCallback((tab) => {
    if (!TAB_IDS.has(tab)) return;
    const prev = activeRef.current;
    const g = groupOfTab(tab);
    const hash = `#/${g.id}/${tab}`;
    if (window.location.hash !== hash) window.history.replaceState(null, '', hash);
    if (tab === prev) return;
    // Sub-tabs of the same group slide in from the side they sit on; a group change only crossfades.
    const pg = groupOfTab(prev);
    let dir = null;
    if (pg.id === g.id) {
      const ids = g.tabs.map((t) => t.id);
      dir = ids.indexOf(tab) > ids.indexOf(prev) ? 'next' : 'prev';
    }
    const ws = document.getElementById('console-workspace');
    if (ws) scrollByTab.current[prev] = ws.scrollTop;
    activeRef.current = tab;
    withViewTransition(() => {
      setActiveNavState(tab);
      setLastTabByGroup((m) => ({ ...m, [g.id]: tab }));
    }, dir);
  }, []);

  // Back/forward and hand-edited hashes.
  useEffect(() => {
    const onHash = () => setActiveNav(tabFromHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, [setActiveNav]);

  // Presentation mode: { index, paused } while presenting, null otherwise.
  const [presenting, setPresenting] = useState(null);
  const enteredFullscreen = useRef(false);
  const stopPresenting = useCallback(() => {
    setPresenting(null);
    if (enteredFullscreen.current && document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
    enteredFullscreen.current = false;
  }, []);
  const stepPresentation = useCallback((delta) => {
    setPresenting((p) => (p ? { ...p, index: (p.index + delta + PRESENT_TABS.length) % PRESENT_TABS.length } : p));
  }, []);
  useEffect(() => {
    const start = () => {
      const at = PRESENT_TABS.indexOf(activeRef.current);
      setPresenting({ index: at >= 0 ? at : 0, paused: false });
      if (!document.fullscreenElement && document.documentElement.requestFullscreen) {
        document.documentElement.requestFullscreen().then(() => { enteredFullscreen.current = true; }).catch(() => {});
      }
    };
    window.addEventListener('vr:present', start);
    return () => window.removeEventListener('vr:present', start);
  }, []);
  // Follow the presented view, and advance after the dwell time unless paused.
  useEffect(() => {
    if (!presenting) return undefined;
    setActiveNav(PRESENT_TABS[presenting.index]);
    if (presenting.paused) return undefined;
    const t = setTimeout(() => stepPresentation(1), PRESENT_DWELL_MS);
    return () => clearTimeout(t);
  }, [presenting, setActiveNav, stepPresentation]);

  // Keys: 1–8 open a group (its last-used tab), [ and ] step through the group's sub-tabs.
  // While presenting: Space pauses, ← / → step, Esc stops. Nothing fires while typing or inside a dialog.
  useEffect(() => {
    const onKey = (e) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented) return;
      if (isTyping(e.target) || e.target?.closest?.('[role="dialog"]')) return;
      if (presenting) {
        if (e.key === 'Escape') { e.preventDefault(); stopPresenting(); return; }
        if (e.key === ' ') { e.preventDefault(); setPresenting((p) => p && { ...p, paused: !p.paused }); return; }
        if (e.key === 'ArrowRight') { e.preventDefault(); stepPresentation(1); return; }
        if (e.key === 'ArrowLeft') { e.preventDefault(); stepPresentation(-1); return; }
      }
      if (/^[1-8]$/.test(e.key)) {
        const g = navGroups[Number(e.key) - 1];
        if (!g) return;
        e.preventDefault();
        setActiveNav(lastTabRef.current[g.id] || g.tabs[0].id);
      } else if (e.key === '[' || e.key === ']') {
        const g = groupOfTab(activeRef.current);
        if (g.tabs.length < 2) return;
        e.preventDefault();
        const i = g.tabs.findIndex((t) => t.id === activeRef.current);
        const n = (i + (e.key === ']' ? 1 : -1) + g.tabs.length) % g.tabs.length;
        setActiveNav(g.tabs[n].id);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [presenting, setActiveNav, stepPresentation, stopPresenting]);

  // Close the drawer with Escape.
  useEffect(() => {
    if (!navOpen) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') setNavOpen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [navOpen]);

  useEffect(() => {
    const handleFSChange = () => {
      setPresentationMode(!!document.fullscreenElement);
      // Esc in fullscreen is taken by the browser: leaving the fullscreen we entered also ends the presentation.
      if (!document.fullscreenElement && enteredFullscreen.current) stopPresenting();
    };
    document.addEventListener('fullscreenchange', handleFSChange);
    return () => document.removeEventListener('fullscreenchange', handleFSChange);
  }, [stopPresenting]);

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
      case 'run_diff':           return <RunDiff />;
      case 'whatif':             return <WhatIf />;
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
              {runtime == null && !runtimeFailed && RUN_TABS.has(activeNav) ? <ViewSkeleton label="the run" /> : (
                <Reveal>
                  {renderMain()}
                  <ScrollRestore tab={activeNav} positions={scrollByTab.current} />
                </Reveal>
              )}
            </Suspense>
          </ViewBoundary>
        </main>
      </div>

      <SystemRail maritimeOverview={maritimeOverview} runtime={runtime} />
      <CommandPalette runtime={runtime} onNavigate={setActiveNav} />
      {presenting && (
        <PresentationHud
          label={navItems.find((n) => n.id === PRESENT_TABS[presenting.index])?.label || ''}
          index={presenting.index}
          total={PRESENT_TABS.length}
          dwellMs={PRESENT_DWELL_MS}
          paused={presenting.paused}
          onPrev={() => stepPresentation(-1)}
          onNext={() => stepPresentation(1)}
          onTogglePause={() => setPresenting((p) => p && { ...p, paused: !p.paused })}
          onStop={stopPresenting}
        />
      )}
      <Toaster />
    </div>
  );
}
