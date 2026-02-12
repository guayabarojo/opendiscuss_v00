import './AsyncRoundControls.css';

interface AsyncRoundControlsProps {
  roundId: string;
  isHost: boolean;
  status: string;
  submissionCount: number;
  minSubmissions?: number;
  roundDurationHours?: number;
  startTime: Date;
  onCloseRound: () => void;
}

function formatDeadline(startTime: Date, durationHours: number): string {
  const deadline = new Date(startTime);
  deadline.setHours(deadline.getHours() + durationHours);
  return deadline.toLocaleString();
}

export function AsyncRoundControls({
  roundId: _roundId,
  isHost,
  status,
  submissionCount,
  minSubmissions,
  roundDurationHours,
  startTime,
  onCloseRound,
}: AsyncRoundControlsProps) {
  const handleCloseRound = () => {
    if (
      window.confirm(
        'Close this round? No more submissions will be accepted.'
      )
    ) {
      onCloseRound();
    }
  };

  return (
    <div className="async-round-controls">
      <div className="async-status-section">
        <div className="status-badge accepting">✅ Accepting Submissions</div>

        <div className="submission-stats">
          <p className="submission-count">
            <strong>Submissions:</strong> {submissionCount}
            {minSubmissions && ` / ${minSubmissions}`}
          </p>
        </div>

        {roundDurationHours && (
          <p className="soft-deadline">
            <strong>Soft deadline:</strong>{' '}
            {formatDeadline(startTime, roundDurationHours)}
          </p>
        )}
      </div>

      {isHost && status === 'SUBMISSION_OPEN' && (
        <div className="host-controls">
          <button
            onClick={handleCloseRound}
            className="btn btn-danger close-round-btn"
          >
            Close Round
          </button>
          <p className="help-text">
            Close the submission window to proceed with summarization
          </p>
        </div>
      )}

      {!isHost && (
        <div className="participant-info">
          <p className="info-text">
            This is an asynchronous discussion. Submit your response whenever ready.
          </p>
        </div>
      )}
    </div>
  );
}
