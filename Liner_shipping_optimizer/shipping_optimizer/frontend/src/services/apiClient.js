/**
 * Production API client — single HTTP layer for backend communication.
 */

import { RUNTIME_TRUTH_URL, normalizeRuntime } from '../runtime/runtimeAdapter.js';

const API_BASE_URL = '/api';

class ApiClient {
  constructor(baseURL = API_BASE_URL) {
    this.baseURL = baseURL;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    const response = await fetch(url, config);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  }

  async get(endpoint) {
    return this.request(endpoint);
  }

  async post(endpoint, data) {
    return this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getPipelineStatus() {
    return this.get('/pipeline/status');
  }

  async startPipeline(config) {
    return this.post('/pipeline/start', config);
  }

  async stopPipeline() {
    return this.post('/pipeline/stop');
  }

  async getMetrics() {
    return this.get('/metrics/summary');
  }

  async getRegions() {
    return this.get('/regions/');
  }

  async healthCheck() {
    return this.get('/health');
  }

  // Phase 8 — Maritime Intelligence Command Center endpoints.
  // Read-only aggregations. The dashboard may call these
  // directly via fetch, but the methods exist so any future
  // caller (or a future React-Query layer) has a single
  // contract surface.
  async getMaritimeOverview() {
    return this.get('/maritime/overview');
  }

  async getMaritimeRoutingImpact() {
    return this.get('/maritime/routing-impact');
  }

  // Phase 9 — Telemetry + diff endpoints. Read-only, safe-empty,
  // no network on the dashboard side, no optimizer imports on
  // the backend side.
  async getMaritimeTelemetry() {
    return this.get('/maritime/telemetry');
  }

  async loadRuntimeTruth() {
    // Dynamic refresh with cache-busting timestamp
    const url = `${RUNTIME_TRUTH_URL}?t=${Date.now()}`;
    try {
      const response = await fetch(url, { cache: 'no-store' });
      if (response.ok) {
        const text = await response.text();
        const runtime = JSON.parse(text);
        // Atomic validation: ensure required contract structure is present
        if (runtime && (runtime.summary_metrics || runtime.selected_services || runtime.iteration_results || runtime.regional_results)) {
          return normalizeRuntime(runtime);
        }
      }
    } catch (_) { /* fall through to API fallback */ }

    // API fallback - assemble the same shape from the backend.
    const [summary, iterations, regions] = await Promise.all([
      this.get('/metrics/summary').catch(() => null),
      fetch('/api/pipeline/iterations').then((r) => (r.ok ? r.json() : null)).catch(() => null),
      this.get('/regions/').catch(() => null),
    ]);
    if (!summary && !iterations && !regions) {
      throw new Error('runtime truth unavailable');
    }
    const runtime = {
      summary_metrics: summary?.metrics || {},
      iterations: iterations?.iterations || [],
      regional_results: Array.isArray(regions?.regions) ? regions.regions : [],
    };
    return normalizeRuntime(runtime);
  }
}

export const apiClient = new ApiClient();
export { ApiClient };
