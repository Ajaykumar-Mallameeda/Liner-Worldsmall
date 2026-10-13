/**
 * Production WebSocket manager — single connection layer for pipeline events.
 */

const DEFAULT_WS_URL = 'ws://localhost:8000/ws/pipeline';
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
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.retryCount = 0;
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
        console.log('WebSocket disconnected');
        this.emit('disconnected');

        if (this.retryCount < this.maxRetries) {
          const delay = Math.min(1000 * Math.pow(2, this.retryCount), 30000);
          this.retryCount++;
          console.log(`Reconnecting in ${delay}ms (attempt ${this.retryCount}/${this.maxRetries})...`);
          this.reconnectTimeout = setTimeout(() => this.connect(), delay);
        } else {
          console.log('Max reconnect attempts reached. Giving up.');
        }
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.emit('error', error);
      };
    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
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
