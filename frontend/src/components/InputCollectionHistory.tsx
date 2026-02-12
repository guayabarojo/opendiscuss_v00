import React, { useEffect, useState } from 'react';
import { getParticipantSubmissions, SubmissionListResponse, SubmissionResponse } from '../services/submissionApi';

interface InputCollectionHistoryProps {
  participantId: string;
  roundId: string;
  onEdit?: (submission: SubmissionResponse) => void;
}

/**
 * InputCollectionHistory Component (T050-T052)
 *
 * Displays submission history for Input Collection Protocol (Spec 002).
 * Shows all submissions with visual indicator for "counted" submission.
 * Allows editing (resubmitting) if under rate limit.
 *
 * Features:
 * - Shows all submissions ordered by timestamp DESC
 * - Visual indicator (checkmark) for counted submission
 * - Edit button for each submission (loads text for resubmission)
 * - Rate limit display
 * - Responsive layout
 */
export const InputCollectionHistory: React.FC<InputCollectionHistoryProps> = ({
  participantId,
  roundId,
  onEdit: _onEdit
}) => {
  const [history, setHistory] = useState<SubmissionListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getParticipantSubmissions(participantId, roundId);
      setHistory(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load submission history');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
    // Poll every 5 seconds for updates
    const interval = setInterval(fetchHistory, 5000);
    return () => clearInterval(interval);
  }, [participantId, roundId]);

  const formatTimestamp = (isoString: string): string => {
    const date = new Date(isoString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
  };

  if (loading && !history) {
    return (
      <div className="submission-history loading">
        <h3>Submission History</h3>
        <p>Loading...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="submission-history error">
        <h3>Submission History</h3>
        <div className="error-message">
          <p>{error}</p>
          <button onClick={fetchHistory} className="retry-button">
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!history) {
    return null;
  }

  return (
    <div className="submission-history">
      <div className="history-header">
        <h3>Your Submissions</h3>
        <div className="rate-limit-indicator">
          <span className={`badge ${history.can_submit_more ? 'badge-success' : 'badge-warning'}`}>
            {history.total_count} / {history.max_allowed} submissions
          </span>
        </div>
      </div>

      {history.submissions.length === 0 ? (
        <div className="empty-state">
          <p>No submissions yet for this round.</p>
        </div>
      ) : (
        <div className="submissions-list">
          {history.submissions.map((submission, index) => (
            <div
              key={submission.submission_id}
              className={`submission-item ${submission.counted ? 'counted' : ''}`}
            >
              <div className="submission-header">
                <div className="submission-meta">
                  <span className="submission-number">#{history.total_count - index}</span>
                  <span className="submission-timestamp">
                    {formatTimestamp(submission.timestamp)}
                  </span>
                  {submission.modality === 'VOICE' && (
                    <span className="modality-badge">🎤 Voice</span>
                  )}
                </div>
                <div className="submission-actions">
                  {submission.counted && (
                    <span className="counted-indicator" title="This submission is counted">
                      ✓ Counted
                    </span>
                  )}
                </div>
              </div>

              {submission.counted && (
                <div className="counted-message">
                  This submission will be used for clustering and analysis.
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {history.can_submit_more ? (
        <div className="resubmit-info">
          <p>
            You can submit {history.max_allowed - history.total_count} more time
            {history.max_allowed - history.total_count !== 1 ? 's' : ''} this round.
          </p>
        </div>
      ) : (
        <div className="rate-limit-reached">
          <p>⚠️ You have reached the maximum of {history.max_allowed} submissions for this round.</p>
        </div>
      )}
    </div>
  );
};
