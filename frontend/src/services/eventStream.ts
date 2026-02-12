import type { RoundStatusResponse } from '../types/api';

/**
 * Event types emitted by the event stream
 */
export type EventType = 'round.status' | 'round.complete' | 'discussion.complete';

export interface StreamEvent<T = unknown> {
  type: EventType;
  data: T;
  timestamp: string;
}

export interface RoundStatusEvent extends StreamEvent<RoundStatusResponse> {
  type: 'round.status';
}

export type EventCallback<T = unknown> = (event: StreamEvent<T>) => void;

/**
 * Event Stream Service
 *
 * Provides real-time updates using Server-Sent Events (SSE).
 * Handles reconnection logic and emits typed events to React components.
 *
 * Usage:
 * ```typescript
 * const stream = eventStream.subscribe('round-123', (event) => {
 *   if (event.type === 'round.status') {
 *     console.log('Round status:', event.data);
 *   }
 * });
 *
 * // Clean up when done
 * stream.close();
 * ```
 */
class EventStreamService {
  private baseURL: string;
  private connections: Map<string, EventSource> = new Map();
  private reconnectAttempts: Map<string, number> = new Map();
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000; // Start with 1 second

  constructor() {
    // Base URL from environment variable with fallback
    this.baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/v1';
  }

  /**
   * Subscribe to round status updates
   * @param roundId UUID of the round to monitor
   * @param callback Function to call when events are received
   * @returns EventSource instance with close method
   */
  subscribe(
    roundId: string,
    callback: EventCallback<RoundStatusResponse>
  ): EventSource {
    // Close existing connection if any
    this.unsubscribe(roundId);

    const url = `${this.baseURL}/rounds/${roundId}/events`;
    const eventSource = new EventSource(url);

    // Handle incoming messages
    eventSource.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        const streamEvent: StreamEvent<RoundStatusResponse> = {
          type: 'round.status',
          data: data,
          timestamp: new Date().toISOString(),
        };
        callback(streamEvent);

        // Reset reconnect attempts on successful message
        this.reconnectAttempts.set(roundId, 0);
      } catch (error) {
        console.error('Failed to parse SSE message:', error);
      }
    };

    // Handle connection open
    eventSource.onopen = () => {
      console.log(`SSE connection opened for round ${roundId}`);
      this.reconnectAttempts.set(roundId, 0);
    };

    // Handle errors and reconnection
    eventSource.onerror = (error) => {
      console.error(`SSE connection error for round ${roundId}:`, error);

      // Close the failed connection
      eventSource.close();
      this.connections.delete(roundId);

      // Attempt reconnection with exponential backoff
      const attempts = this.reconnectAttempts.get(roundId) || 0;

      if (attempts < this.maxReconnectAttempts) {
        const delay = this.reconnectDelay * Math.pow(2, attempts);
        console.log(
          `Reconnecting in ${delay}ms (attempt ${attempts + 1}/${this.maxReconnectAttempts})`
        );

        setTimeout(() => {
          this.reconnectAttempts.set(roundId, attempts + 1);
          this.subscribe(roundId, callback);
        }, delay);
      } else {
        console.error(
          `Max reconnection attempts reached for round ${roundId}`
        );
        // Emit error event to callback
        const errorEvent: StreamEvent = {
          type: 'round.status',
          data: {
            error: 'Connection failed',
            message: 'Unable to establish real-time connection after multiple attempts',
          },
          timestamp: new Date().toISOString(),
        };
        callback(errorEvent as StreamEvent<RoundStatusResponse>);
      }
    };

    // Store connection
    this.connections.set(roundId, eventSource);

    return eventSource;
  }

  /**
   * Unsubscribe from round updates
   * @param roundId UUID of the round
   */
  unsubscribe(roundId: string): void {
    const connection = this.connections.get(roundId);
    if (connection) {
      connection.close();
      this.connections.delete(roundId);
      this.reconnectAttempts.delete(roundId);
      console.log(`Unsubscribed from round ${roundId}`);
    }
  }

  /**
   * Close all active connections
   */
  closeAll(): void {
    this.connections.forEach((connection, roundId) => {
      connection.close();
      console.log(`Closed connection for round ${roundId}`);
    });
    this.connections.clear();
    this.reconnectAttempts.clear();
  }

  /**
   * Get active connection count
   */
  getActiveConnections(): number {
    return this.connections.size;
  }
}

// Export singleton instance
export const eventStream = new EventStreamService();

// Export class for testing
export { EventStreamService };

/**
 * React Hook for using event stream
 *
 * Usage:
 * ```typescript
 * function RoundMonitor({ roundId }: { roundId: string }) {
 *   const [status, setStatus] = useState<RoundStatusResponse | null>(null);
 *
 *   useEffect(() => {
 *     const source = eventStream.subscribe(roundId, (event) => {
 *       if (event.type === 'round.status') {
 *         setStatus(event.data);
 *       }
 *     });
 *
 *     return () => {
 *       source.close();
 *     };
 *   }, [roundId]);
 *
 *   return <div>Status: {status?.status}</div>;
 * }
 * ```
 */
export function useRoundStatus(
  roundId: string,
  onStatusUpdate: (status: RoundStatusResponse) => void
): () => void {
  // This is a helper function that can be used in React components
  // The actual hook implementation would be in a separate hooks file
  const source = eventStream.subscribe(roundId, (event) => {
    if (event.type === 'round.status') {
      onStatusUpdate(event.data);
    }
  });

  // Return cleanup function
  return () => {
    source.close();
  };
}
