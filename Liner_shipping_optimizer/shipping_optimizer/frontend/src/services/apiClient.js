/**
 * Production API client — single HTTP layer for backend communication.
 */

import { RUNTIME_TRUTH_URL, normalizeRuntime } from '../runtime/runtimeAdapter.js';
import { getSelectedRun, runOutputUrl, runLabel } from './runSelection.js';
import { rawFilesFor } from './rawDatasetService.js';
import { ensurePortData } from '../utils/portRegistry.js';

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

  // Run catalog + frozen benchmark (backend/run_catalog.py). Read-only.
  async getRuns() {
    return this.get('/runs');
  }

  async getBenchmarkSummary() {
    return this.get('/benchmark/summary');
  }

  async getBenchmarkSeeds(dataset) {
    return this.get(`/benchmark/${encodeURIComponent(dataset)}/seeds`);
  }

  /**
   * Load the selected run's pipeline_output.json.
   * Conditional (ETag / Last-Modified): an unchanged file returns the SAME normalized object without
   * re-downloading, so pollers can skip re-rendering. Concurrent callers share one request.
   */
  async loadRuntimeTruth() {
    const run = getSelectedRun();
    const url = runOutputUrl(run) || RUNTIME_TRUTH_URL;
    if (this._inflight && this._inflight.url === url) return this._inflight.promise;
    const promise = this._fetchRuntime(run, url).finally(() => {
      if (this._inflight && this._inflight.promise === promise) this._inflight = null;
    });
    this._inflight = { url, promise };
    return promise;
  }

  async _fetchRuntime(run, url) {
    const cached = this._runtimeCache && this._runtimeCache.url === url ? this._runtimeCache : null;
    try {
      const headers = {};
      if (cached?.etag) headers['If-None-Match'] = cached.etag;
      if (cached?.lastModified) headers['If-Modified-Since'] = cached.lastModified;
      const response = await fetch(url, { cache: 'no-store', headers });
      if (response.status === 304 && cached) return cached.normalized;
      if (response.ok) {
        const lastModified = response.headers.get('last-modified');
        const etag = response.headers.get('etag');
        if (cached && lastModified && lastModified === cached.lastModified && etag === cached.etag) {
          return cached.normalized;            // server ignored the validators but the file is the same
        }
        const runtime = JSON.parse(await response.text());
        // Atomic validation: ensure required contract structure is present
        if (runtime && (runtime.summary_metrics || runtime.selected_services || runtime.iteration_results || runtime.regional_results)) {
          const dataset = runtime.dataset_run?.dataset || null;
          // Register the dataset's ports (names, coordinates, countries) first: normalizing assigns each
          // service a geographic region, which needs them for synthetic port codes.
          await ensurePortData(rawFilesFor(dataset || (run.kind === 'benchmark' ? run.dataset : 'worldsmall'))?.dir);
          const normalized = normalizeRuntime(runtime);
          const modifiedIso = lastModified && !Number.isNaN(Date.parse(lastModified))
            ? new Date(lastModified).toISOString() : null;
          normalized.source = { run, url, dataset, label: runLabel(run, dataset), lastModified, modifiedIso, etag };
          // Identify the run by what it is (dataset + seed), never by an invented id.
          normalized.global.run_id = normalized.global.run_id_from_file || normalized.source.label;
          normalized.global.evaluated_at = normalized.global.evaluated_at || modifiedIso;
          this._runtimeCache = { url, lastModified, etag, normalized };
          return normalized;
        }
      }
    } catch (_) { /* fall through to API fallback */ }
    if (run.kind === 'benchmark') throw new Error('benchmark run unavailable');

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
