/**
 * MaritimeDashboard — Phase 12 REVISION
 * -------------------------------------
 * Unified Crucix-style command console shell.
 * Clean, headerless layout with persistent fixed sidebar and scrollable workspace.
 *
 * Data contracts are UNCHANGED. useOptimizationState remains the
 * single source of truth. The /api/maritime/overview poll is preserved.
 */

import { useEffect, useState, useCallback } from "react";
import { useOptimizationState } from '../hooks/useOptimizationState.js';
import { apiClient } from '../services/apiClient.js';

// Console navigation and persistent top/bottom rails
import TopHeaderBar from '../components/console/TopHeaderBar.jsx';
import ConsoleSidebar from '../components/console/ConsoleSidebar.jsx';
import SystemRail from '../components/console/SystemRail.jsx';

// Maritime views (legacy, kept for fallback only)
import MaritimeStatusView from './MaritimeStatusView.jsx';
import MaritimeOpsView from './MaritimeOpsView.jsx';
import MaritimeResilienceView from './MaritimeResilienceView.jsx';
import MaritimeLiveView from './MaritimeLiveView.jsx';
import MaritimeWeatherView from './MaritimeWeatherView.jsx';
import MaritimeCongestionView from './MaritimeCongestionView.jsx';
import MaritimeOverviewView from './MaritimeOverviewView.jsx';
import MaritimeRoutingImpactView from './MaritimeRoutingImpactView.jsx';

// Phase 11/12 — command console views
import CommandCenter from './console/CommandCenter.jsx';
import NetworkIntelligence from './console/NetworkIntelligence.jsx';
import FleetIntelligence from './console/FleetIntelligence.jsx';
import DemandIntelligence from './console/DemandIntelligence.jsx';
import PortIntelligence from './console/PortIntelligence.jsx';
import MaritimeSituation from './console/MaritimeSituation.jsx';
import PipelineOps from './console/PipelineOps.jsx';
import RegionalAgents from './console/RegionalAgents.jsx';
import GaMilp from './console/GaMilp.jsx';
import FeedbackLoop from './console/FeedbackLoop.jsx';
import DecisionCenter from './console/DecisionCenter.jsx';
import ScenarioAnalysis from './console/ScenarioAnalysis.jsx';
import Telemetry from './console/Telemetry.jsx';
import DataSources from './console/DataSources.jsx';
import SystemHealth from './console/SystemHealth.jsx';

import navItems from '../components/layout/navItems.js';

export default function App() {
  const optimizationState = useOptimizationState();
  const [activeNav, setActiveNav] = useState('command_center');
  const [presentationMode, setPresentationMode] = useState(false);
  const [demoMode, setDemoMode] = useState(false);
  const [maritimeOverview, setMaritimeOverview] = useState(null);
  const [runtime, setRuntime] = useState(null);

  useEffect(() => {
    const handleFSChange = () => setPresentationMode(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', handleFSChange);
    return () => document.removeEventListener('fullscreenchange', handleFSChange);
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer = null;
    const load = async () => {
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
    const load = async () => {
      try {
        const norm = await apiClient.loadRuntimeTruth().catch(() => null);
        if (!cancelled && norm) setRuntime(norm);
      } catch (_) { /* noop */ }
    };
    load();
    timer = setInterval(load, 5000);
    return () => { cancelled = true; if (timer) clearInterval(timer); };
  }, []);

  useEffect(() => {
    if (!demoMode) return;
    const tabs = navItems.map((n) => n.id);
    const interval = setInterval(() => {
      setActiveNav((prev) => {
        const idx = tabs.indexOf(prev);
        return tabs[(idx + 1) % tabs.length];
      });
    }, 8000);
    return () => clearInterval(interval);
  }, [demoMode]);

  const renderMain = () => {
    switch (activeNav) {
      // COMMAND
      case 'command_center':
        return (
          <CommandCenter
            optimizationState={optimizationState}
            maritimeOverview={maritimeOverview}
            runtime={runtime}
          />
        );

      // INTELLIGENCE
      case 'network_intel':
        return <NetworkIntelligence optimizationState={optimizationState} maritimeOverview={maritimeOverview} runtime={runtime} />;
      case 'fleet_intel':
        return <FleetIntelligence optimizationState={optimizationState} maritimeOverview={maritimeOverview} runtime={runtime} />;
      case 'demand_intel':
        return <DemandIntelligence optimizationState={optimizationState} maritimeOverview={maritimeOverview} runtime={runtime} />;
      case 'port_intel':
        return <PortIntelligence optimizationState={optimizationState} maritimeOverview={maritimeOverview} runtime={runtime} />;
      case 'maritime_situation':
        return <MaritimeSituation maritimeOverview={maritimeOverview} />;

      // AI OPERATIONS
      case 'pipeline_ops':
        return <PipelineOps optimizationState={optimizationState} maritimeOverview={maritimeOverview} runtime={runtime} />;
      case 'regional_agents':
        return <RegionalAgents optimizationState={optimizationState} maritimeOverview={maritimeOverview} runtime={runtime} />;
      case 'ga_milp':
        return <GaMilp optimizationState={optimizationState} runtime={runtime} />;
      case 'feedback_loop':
        return <FeedbackLoop optimizationState={optimizationState} maritimeOverview={maritimeOverview} runtime={runtime} />;
      case 'decision_center':
        return <DecisionCenter optimizationState={optimizationState} maritimeOverview={maritimeOverview} runtime={runtime} />;
      case 'scenario_analysis':
        return <ScenarioAnalysis optimizationState={optimizationState} maritimeOverview={maritimeOverview} runtime={runtime} />;

      // SYSTEM
      case 'telemetry':
        return <Telemetry maritimeOverview={maritimeOverview} />;
      case 'data_sources':
        return <DataSources maritimeOverview={maritimeOverview} />;
      case 'system_health':
        return <SystemHealth maritimeOverview={maritimeOverview} />;

      // Legacy fallback
      case 'legacy_status': return <MaritimeStatusView />;
      case 'legacy_ops': return <MaritimeOpsView />;
      case 'legacy_resilience': return <MaritimeResilienceView />;
      case 'legacy_live': return <MaritimeLiveView />;
      case 'legacy_weather': return <MaritimeWeatherView />;
      case 'legacy_congestion': return <MaritimeCongestionView />;
      case 'legacy_overview': return <MaritimeOverviewView />;
      case 'legacy_routing_impact': return <MaritimeRoutingImpactView />;

      default:
        return null;
    }
  };

  const isCommandCenter = activeNav === 'command_center';

  return (
    <div
      className={`console-shell ${presentationMode ? 'presentation-mode' : ''} ${isCommandCenter ? 'console-shell--command' : ''}`}
      style={{ color: 'var(--cx-text)', fontFamily: 'var(--cx-sans)' }}
    >
      <TopHeaderBar optimizationState={optimizationState} runtime={runtime} />

      <div className="console-main">
        <ConsoleSidebar
          activeNav={activeNav}
          onNavChange={setActiveNav}
          optimizationState={optimizationState}
        />

        <main className="cx-workspace" role="main" aria-label="Active console view">
          {renderMain()}
        </main>
      </div>

      <SystemRail maritimeOverview={maritimeOverview} runtime={runtime} />
    </div>
  );
}
