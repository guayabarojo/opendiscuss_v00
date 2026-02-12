/**
 * CountdownTimer Component
 *
 * Displays real-time countdown for submission window.
 * Connects to WebSocket for sub-second accuracy updates.
 * Shows visual warnings when time is running out.
 */

import React, { useEffect, useState, useCallback } from 'react';
import { WebSocketTimerClient, TimerUpdate } from '../services/websocketClient';
import './CountdownTimer.css';

interface CountdownTimerProps {
  roundId: string;
  onWindowClose?: () => void;
}

export const CountdownTimer: React.FC<CountdownTimerProps> = ({
  roundId,
  onWindowClose
}) => {
  const [timerUpdate, setTimerUpdate] = useState<TimerUpdate | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Handle timer updates from WebSocket
  const handleTimerUpdate = useCallback((update: TimerUpdate) => {
    setTimerUpdate(update);
    setError(null);

    // Notify parent when window closes
    if (update.remaining_seconds === 0 && update.status === 'CLOSED' && onWindowClose) {
      onWindowClose();
    }
  }, [onWindowClose]);

  // Handle WebSocket errors
  const handleError = useCallback((err: Error) => {
    console.error('WebSocket error:', err);
    setError(err.message);
    setIsConnected(false);
  }, []);

  // Handle WebSocket close
  const handleClose = useCallback(() => {
    setIsConnected(false);
  }, []);

  // Initialize WebSocket connection
  useEffect(() => {
    const client = new WebSocketTimerClient(
      roundId,
      (update) => {
        handleTimerUpdate(update);
        setIsConnected(true);
      },
      handleError,
      handleClose
    );

    client.connect();

    // Cleanup on unmount
    return () => {
      client.disconnect();
    };
  }, [roundId, handleTimerUpdate, handleError, handleClose]);

  // Format seconds as MM:SS
  const formatTime = (seconds: number | null): string => {
    if (seconds === null) return '--:--';
    if (seconds < 0) return '00:00';

    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Determine color based on remaining time
  const getTimerColor = (seconds: number | null, isOpen: boolean): string => {
    if (!isOpen || seconds === null) return 'gray';
    if (seconds <= 30) return 'red';
    if (seconds <= 60) return 'yellow';
    return 'green';
  };

  // Get status message
  const getStatusMessage = (): string => {
    if (!timerUpdate) return 'Connecting...';

    switch (timerUpdate.status) {
      case 'NOT_OPEN':
        return 'Submission window not yet configured';
      case 'BEFORE_WINDOW':
        return 'Submission window will open soon';
      case 'OPEN':
        return 'Submission window is open';
      case 'CLOSED':
        return 'Submission window has closed';
      default:
        return 'Unknown status';
    }
  };

  if (!timerUpdate) {
    return (
      <div className="countdown-timer loading">
        <div className="timer-spinner">⏳</div>
        <div className="timer-status">Connecting to server...</div>
        {error && <div className="timer-error">{error}</div>}
      </div>
    );
  }

  const color = getTimerColor(timerUpdate.remaining_seconds, timerUpdate.is_open);
  const formattedTime = formatTime(timerUpdate.remaining_seconds);

  return (
    <div className={`countdown-timer ${color}`}>
      <div className="timer-header">
        <div className="timer-connection-status">
          <span className={`status-indicator ${isConnected ? 'connected' : 'disconnected'}`}>
            {isConnected ? '●' : '○'}
          </span>
          <span className="status-text">
            {isConnected ? 'Connected' : 'Reconnecting...'}
          </span>
        </div>
      </div>

      <div className="timer-display">
        <div className={`timer-value ${color}`}>
          {formattedTime}
        </div>
        <div className="timer-label">
          {timerUpdate.is_open ? 'Time Remaining' : 'Window Status'}
        </div>
      </div>

      <div className="timer-status">
        {getStatusMessage()}
      </div>

      {timerUpdate.is_open && timerUpdate.remaining_seconds !== null && timerUpdate.remaining_seconds <= 60 && (
        <div className="timer-warning">
          ⚠️ Less than 1 minute remaining!
        </div>
      )}

      {error && (
        <div className="timer-error">
          ⚠️ Connection issue: {error}
        </div>
      )}
    </div>
  );
};
