import React, { useState, useEffect } from 'react';
import './styles.css';

interface RoundTimerProps {
  windowEnd: string; // ISO timestamp
}

/**
 * RoundTimer Component
 *
 * Displays a countdown timer showing remaining time in submission window.
 * Updates every second with visual progress bar that changes color as time runs out.
 *
 * Props:
 * - windowEnd: ISO 8601 timestamp for when submission window closes
 *
 * Visual States:
 * - Green: > 60 seconds remaining
 * - Yellow: 30-60 seconds remaining
 * - Red: < 30 seconds remaining
 * - Gray: Window closed
 */
export const RoundTimer: React.FC<RoundTimerProps> = ({ windowEnd }) => {
  const [remainingTime, setRemainingTime] = useState<number>(0);
  const [totalDuration, setTotalDuration] = useState<number>(0);

  useEffect(() => {
    // Calculate initial remaining time
    const calculateRemainingTime = (): number => {
      const now = new Date().getTime();
      const end = new Date(windowEnd).getTime();
      const diff = Math.max(0, Math.floor((end - now) / 1000));
      return diff;
    };

    // Set initial values
    const initial = calculateRemainingTime();
    setRemainingTime(initial);

    // Estimate total duration (used for progress bar calculation)
    // This is an approximation; ideally would be passed as a prop
    if (totalDuration === 0 && initial > 0) {
      setTotalDuration(initial);
    }

    // Update every second
    const interval = setInterval(() => {
      const remaining = calculateRemainingTime();
      setRemainingTime(remaining);

      if (remaining === 0) {
        clearInterval(interval);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [windowEnd, totalDuration]);

  // Format time as MM:SS
  const formatTime = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  // Determine color based on remaining time
  const getColorClass = (): string => {
    if (remainingTime === 0) return 'timer-closed';
    if (remainingTime < 30) return 'timer-critical';
    if (remainingTime < 60) return 'timer-warning';
    return 'timer-good';
  };

  // Calculate progress percentage (inverse - starts at 100% and decreases)
  const getProgressPercentage = (): number => {
    if (totalDuration === 0) return 0;
    return Math.max(0, Math.min(100, (remainingTime / totalDuration) * 100));
  };

  if (remainingTime === 0) {
    return (
      <div className="round-timer timer-closed">
        <div className="timer-display">
          <div className="timer-icon">🔒</div>
          <div className="timer-text">
            <div className="timer-label">Submission Window</div>
            <div className="timer-value">Closed</div>
          </div>
        </div>
        <div className="timer-progress-bar">
          <div
            className="timer-progress-fill timer-closed"
            style={{ width: '0%' }}
          />
        </div>
      </div>
    );
  }

  const colorClass = getColorClass();
  const progressPercentage = getProgressPercentage();

  return (
    <div className={`round-timer ${colorClass}`}>
      <div className="timer-display">
        <div className="timer-icon">⏱️</div>
        <div className="timer-text">
          <div className="timer-label">Time Remaining</div>
          <div className="timer-value">{formatTime(remainingTime)}</div>
        </div>
      </div>
      <div className="timer-progress-bar">
        <div
          className={`timer-progress-fill ${colorClass}`}
          style={{ width: `${progressPercentage}%` }}
        />
      </div>
      {remainingTime < 60 && (
        <div className="timer-warning-message">
          Submission window closing soon!
        </div>
      )}
    </div>
  );
};

export default RoundTimer;
