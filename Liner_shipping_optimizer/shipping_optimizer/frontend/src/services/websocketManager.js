/**
 * Production WebSocket manager — single connection layer for pipeline events.
 */

// Same host as the page, so the Vite dev proxy (and a production reverse proxy) carry the socket.
// VITE_WS_URL overrides it for split deployments.
function defaultWsUrl() {
  const override = import.meta.env?.VITE_WS_URL;
  if (override) return override;
  if (typeof window === 'undefined' || !window.location) return 'ws://localhost:8000/ws/pipeline';
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/ws/pipeline`;
}
const DEFAULT_WS_URL = defaultWsUrl();
const MAX_RETRIES = 5;

class WebSocketManager {
  constructor(url = DEFAULT_WS_URL) {
    this.url = url;
    this.ws = null;
    this.reconnectTimeout = null;
    this.retryCount = 0;
    this.listeners = new Map();
    this.maxRetries = MAX_RETRIES;
    this.connectionCount = 0;
    // 'idle' | 'connecting' | 'open' | 'retrying' | 'offline' — the one status every panel reads
    this.status = 'idle';
  }

  setStatus(status) {
    if (this.status === status) return;
    this.status = status;
    this.emit('status', status);
  }

  getStatus() {
    return this.status;
  }

  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event).add(callback);
    return () => this.off(event, callback);
  }

  off(event, callback) {
    const handlers = this.listeners.get(event);
    if (handlers) {
      handlers.delete(callback);
    }
  }

  emit(event, data) {
    const handlers = this.listeners.get(event);
    if (handlers) {
      handlers.forEach((callback) => {
        try {
          callback(data);
        } catch (error) {
          console.error(`WebSocket handler error (${event}):`, error);
        }
      });
    }
  }

  connect() {
    this.connectionCount++;
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      this.setStatus(this.retryCount > 0 ? 'retrying' : 'connecting');
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.retryCount = 0;
        this.setStatus('open');
        this.emit('connected');
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          this.emit('message', message);
          if (message.type) {
            this.emit(message.type, message);
          }
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      this.ws.onclose = () => {
        this.emit('disconnected');
        if (this.connectionCount === 0) {
          this.setStatus('idle');
          return;
        }

        if (this.retryCount < this.maxRetries) {
          const delay = Math.min(1000 * Math.pow(2, this.retryCount), 30000);
          this.retryCount++;
          this.setStatus('retrying');
          this.reconnectTimeout = setTimeout(() => this.connect(), delay);
        } else {
          // The dashboard works from files without the socket; say so once instead of logging every retry.
          console.info('Live pipeline socket unavailable; showing results from disk.');
          this.setStatus('offline');
        }
      };

      this.ws.onerror = (error) => {
        this.emit('error', error);
      };
    } catch (error) {
      console.warn('Failed to open WebSocket:', error);
      this.setStatus('offline');
    }
  }

  disconnect() {
    this.connectionCount = Math.max(0, this.connectionCount - 1);
    if (this.connectionCount > 0) return;

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.retryCount = 0;
    this.setStatus('idle');
  }

  send(type, data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, data }));
    } else {
      console.warn('WebSocket not connected');
    }
  }

  startPipeline(config = {}) {
    this.send('start_pipeline', {
      dataset_path: 'data/datasets/worldsmall_shipping_problem.json',
      ...config,
    });
  }

  isConnected() {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

export const websocketManager = new WebSocketManager();
export { WebSocketManager };
