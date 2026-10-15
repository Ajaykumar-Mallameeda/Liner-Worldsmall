/**
 * WebSocket integration hook for live optimization data.
 * Uses runtimeAdapter + websocketManager + apiClient.
 */

import { useState, useEffect, useCallback } from 'react';
import {
  normalizeGlobal,
  normalizeIteration,
  normalizeRegion,
  normalizeRegions,
  regionDisplayName,
  getRegionColor,
} from '../runtime/runtimeAdapter.js';
import { apiClient } from '../services/apiClient.js';
import { websocketManager } from '../services/websocketManager.js';

const INITIAL_STATE = {
  global: {
    ports: null,
    lanes: null,
    services: null,
    weeklyDemand: null,
    runtime: 0,
    iterations: 0,
    convergence: 0,
    // economic headline figures start unavailable (null), not 0: 0 would read as a measured result
    weeklyProfit: null,
    annualProfit: null,
    coverage: null,
    totalServices: 0,
    margin: null,
    unserved: 0,
    operatingCost: null,
    selected_services: [],
    executive_summary: '',
    decision_output: {},
    test_scorecard: {},
    llm_runtime_metrics: {},
    revenue: null,
    fuelCost: null,
    portCost: null,
    transshipCost: null,
    satisfiedDemand: null,
  },
  regions: {},
  iterations: [],
  corridors: [],
  isConnected: false,
  isPipelineRunning: false,
  currentStage: null,
  stageProgress: 0,
  currentIteration: 0,
  maxIterations: 3,
  pipelineError: null,
};

function handleInitialState(message, setState) {
  if (!message.data) return;

  const processedRegions = normalizeRegions(
    message.data.regions || message.data.regional_results || {}
  );

  setState((prev) => ({
    ...prev,
    global: {
      ...prev.global,
      ...normalizeGlobal(message.data, prev.global),
    },
    regions: Object.keys(processedRegions).length > 0 ? processedRegions : prev.regions,
    iterations:
      message.data.iteration_audit?.map((d) => normalizeIteration(d)) ||
      message.data.iterations ||
      prev.iterations,
    corridors: message.data.corridors || prev.corridors || [],
  }));
}

function handleRegionUpdate(message, setState) {
  const rData = message.data?.region_data || message.data || message;
  const rId = message.data?.region_id || rData.id || rData.region_id;
  if (!rId) return;

  setState((prev) => ({
    ...prev,
    regions: {
      ...prev.regions,
      [rId]: {
        ...prev.regions[rId],
        ...normalizeRegion(rData),
        id: rId,
        name: regionDisplayName(rId, rData.name),
        color: getRegionColor(rId),
      },
    },
  }));
}

function handlePipelineCompleted(message, setState) {
  const results = message.data?.results || message.results || message.data || {};

  setState((prev) => ({
    ...prev,
    isPipelineRunning: false,
    currentStage: 'Complete',
    stageProgress: 100,
    global: {
      ...prev.global,
      ...normalizeGlobal(results, prev.global),
    },
  }));
}

export const PIPELINE_REFRESH_INTERVAL_MS = 5000; // 5-second polling for live rerun reactivity
 
export function useOptimizationState() {
  const [state, setState] = useState(INITIAL_STATE);
  const [freshness, setFreshness] = useState({
    status: 'initial',
    lastFetchedAt: null,
    error: null,
  });

  const fetchRuntimeTruth = useCallback(() => {
    return apiClient
      .loadRuntimeTruth()
      .then((normalized) => {
      setState((prev) => ({
          ...prev,
          global: { ...prev.global, ...normalized.global },
          regions: normalized.regions,
          iterations: normalized.iterations,
          corridors: normalized.corridors,
          iteration_results: normalized.iteration_results || [],
          iteration_selection: normalized.iteration_selection || {},
          iteration_regions_map: normalized.iteration_regions_map || {},
          scorecards: normalized.scorecards || [],
          llm_runtime_aggregate: normalized.llm_runtime_aggregate || {},
          llm_runtime_metrics: normalized.llm_runtime_metrics || {},
          raw: normalized.raw || null,
        }));
        setFreshness({
          status: 'live',
          lastFetchedAt: Date.now(),
          error: null,
        });
      })
      .catch((err) => {
        console.log('Runtime truth not available from file, waiting for WebSocket/retry:', err.message);
        setFreshness((prev) => ({
          ...prev,
          status: prev.lastFetchedAt ? 'stale' : 'error',
          error: err.message,
        }));
      });
  }, []);

  // Initial fetch + Periodic 60s Polling Loop
  useEffect(() => {
    fetchRuntimeTruth();
    const interval = setInterval(fetchRuntimeTruth, PIPELINE_REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchRuntimeTruth]);

  useEffect(() => {
    const unsubscribers = [
      websocketManager.on('connected', () => {
        setState((prev) => ({ ...prev, isConnected: true }));
      }),
      websocketManager.on('disconnected', () => {
        setState((prev) => ({ ...prev, isConnected: false }));
      }),
      websocketManager.on('error', () => {
        setState((prev) => ({ ...prev, pipelineError: 'Connection error' }));
      }),
      websocketManager.on('initial_state', (message) => handleInitialState(message, setState)),
      websocketManager.on('pipeline_started', () => {
        setState((prev) => ({
          ...prev,
          isPipelineRunning: true,
          currentStage: 'Initializing',
          pipelineError: null,
        }));
      }),
      websocketManager.on('stage_started', (message) => {
        setState((prev) => ({
          ...prev,
          currentStage: message.data?.stage || message.stage,
          stageProgress: 0,
        }));
      }),
      websocketManager.on('stage_progress', (message) => {
        setState((prev) => ({
          ...prev,
          stageProgress: message.data?.progress ?? message.progress ?? 0,
        }));
      }),
      websocketManager.on('region_update', (message) => handleRegionUpdate(message, setState)),
      websocketManager.on('region_updated', (message) => handleRegionUpdate(message, setState)),
      websocketManager.on('iteration_completed', (message) => {
        const itData = message.data?.iteration_data || message.data || message;
        const itNum = message.data?.iteration || itData.iteration || itData.iter;
        setState((prev) => ({
          ...prev,
          iterations: [...prev.iterations, normalizeIteration({ ...itData, iteration: itNum })],
          currentIteration: itNum,
        }));
      }),
      websocketManager.on('map_updated', (message) => {
        setState((prev) => ({
          ...prev,
          corridors: message.data?.corridors || message.corridors || [],
        }));
      }),
      websocketManager.on('pipeline_completed', (message) => handlePipelineCompleted(message, setState)),
      websocketManager.on('pipeline_error', (message) => {
        setState((prev) => ({
          ...prev,
          isPipelineRunning: false,
          pipelineError: message.data?.error || message.error || 'Unknown error',
        }));
      }),
    ];

    websocketManager.connect();

    return () => {
      unsubscribers.forEach((unsub) => unsub());
      websocketManager.disconnect();
    };
  }, []);

  const startOptimization = useCallback(() => {
    if (websocketManager.isConnected()) {
      websocketManager.startPipeline();
    } else {
      console.error('WebSocket not connected');
    }
  }, []);

  return { ...state, freshness, startOptimization, refetchRuntime: fetchRuntimeTruth };
}
