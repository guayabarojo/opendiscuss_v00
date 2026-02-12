/**
 * WebSocket client for real-time countdown timer.
 * Connects to backend WebSocket endpoint and receives timer updates.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface TimerUpdate {
  round_id: string;
  remaining_seconds: number | null;
  is_open: boolean;
  status: 'NOT_OPEN' | 'BEFORE_WINDOW' | 'OPEN' | 'CLOSED';
  current_time: string;
}

export type TimerCallback = (update: TimerUpdate) => void;
export type ErrorCallback = (error: Error) => void;
export type CloseCallback = () => void;

export class WebSocketTimerClient {
  private ws: WebSocket | null = null;
  private roundId: string;
  private onTimerUpdate: TimerCallback;
  private onError: ErrorCallback;
  private onClose: CloseCallback;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000; // Start with 1 second
  private reconnectTimer: number | null = null;
  private isIntentionallyClosed = false;
  private pingInterval: number | null = null;

  constructor(
    roundId: string,
    onTimerUpdate: TimerCallback,
    onError: ErrorCallback,
    onClose: CloseCallback
  ) {
    this.roundId = roundId;
    this.onTimerUpdate = onTimerUpdate;
    this.onError = onError;
    this.onClose = onClose;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      console.warn('WebSocket already connected');
      return;
    }

    this.isIntentionallyClosed = false;

    // Convert HTTP URL to WebSocket URL
    const wsUrl = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://');
    const url = `${wsUrl}/ws/rounds/${this.roundId}/timer`;

    console.log(`Connecting to WebSocket: ${url}`);

    try {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000; // Reset delay on successful connection

        // Start sending ping messages every 30 seconds to keep connection alive
        this.pingInterval = window.setInterval(() => {
          if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send('ping');
          }
        }, 30000);
      };

      this.ws.onmessage = (event) => {
        try {
          // Handle pong responses (keep-alive)
          if (event.data === 'pong') {
            return;
          }

          const data: TimerUpdate = JSON.parse(event.data);
          this.onTimerUpdate(data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      this.ws.onerror = (event) => {
        console.error('WebSocket error:', event);
        this.onError(new Error('WebSocket connection error'));
      };

      this.ws.onclose = () => {
        console.log('WebSocket closed');

        // Clear ping interval
        if (this.pingInterval !== null) {
          clearInterval(this.pingInterval);
          this.pingInterval = null;
        }

        this.onClose();

        // Attempt to reconnect if not intentionally closed
        if (!this.isIntentionallyClosed) {
          this.scheduleReconnect();
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      this.onError(error as Error);
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      this.onError(new Error('Failed to reconnect after multiple attempts'));
      return;
    }

    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
    }

    this.reconnectAttempts++;

    // Exponential backoff: 1s, 2s, 4s, 8s, 16s
    const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 16000);

    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

    this.reconnectTimer = window.setTimeout(() => {
      this.connect();
    }, delay);
  }

  disconnect(): void {
    this.isIntentionallyClosed = true;

    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.pingInterval !== null) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  getConnectionStatus(): 'connecting' | 'open' | 'closing' | 'closed' {
    if (!this.ws) return 'closed';

    switch (this.ws.readyState) {
      case WebSocket.CONNECTING:
        return 'connecting';
      case WebSocket.OPEN:
        return 'open';
      case WebSocket.CLOSING:
        return 'closing';
      case WebSocket.CLOSED:
        return 'closed';
      default:
        return 'closed';
    }
  }
}
