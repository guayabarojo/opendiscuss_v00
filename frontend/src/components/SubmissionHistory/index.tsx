import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { discussionApi } from '../../services/discussionApi';
import './styles.css';

interface SubmissionHistoryProps {
  participantId: string;
  roundId: string;
  onResubmit?: () => void;
}

interface SubmissionHistoryItem {
  submission_id: string;
  submission_text: string;
  modality: string;
  submitted_at: string;
  summary_status: string;
  is_currently_approved: boolean;
}

interface SubmissionHistoryResponse {
  participant_id: string;
  round_id: string;
  submissions: SubmissionHistoryItem[];
  total_submissions: number;
  remaining_submissions: number;
}

/**
 * SubmissionHistory Component (T072)
 *
 * Displays participant's submission history for the current round.
 * Shows which submission is currently approved with visual indicators.
 * Allows resubmission if remaining submissions > 0.
 *
 * Features:
 * - Shows submission text, timestamp, and status
 * - Highlights approved submission with checkmark
 * - Displays status badges (APPROVED, SUPERSEDED, PENDING)
 * - Shows remaining submission count
 * - Enables "Submit Again" button when under limit
 * - Orders by submitted_at DESC (newest first)
 *
 * Props:
 * - participantId: UUID of the participant
 * - roundId: UUID of the round
 * - onResubmit: Optional callback when "Submit Again" is clicked
 */
export const SubmissionHistory: React.FC<SubmissionHistoryProps> = ({
  participantId,
  roundId,
  onResubmit,
}) => {
  // Fetch submission history
  const {
    data: history,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery<SubmissionHistoryResponse>({
    queryKey: ['submission-history', participantId, roundId],
    queryFn: async () => {
      return await discussionApi.getSubmissionHistory(participantId, roundId);
    },
    refetchInterval: 5000, // Refresh every 5 seconds for real-time updates
  });

  // Format timestamp to readable format
  const formatTimestamp = (isoString: string): string => {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);

    // Show relative time if within last hour
    if (diffMins < 1) return 'Just now';
    if (diffMins === 1) return '1 minute ago';
    if (diffMins < 60) return `${diffMins} minutes ago`;
    if (diffHours === 1) return '1 hour ago';
    if (diffHours < 24) return `${diffHours} hours ago`;

    // Otherwise show formatted date/time
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  };

  // Get status badge color class
  const getStatusClass = (status: string): string => {
    switch (status) {
      case 'APPROVED':
        return 'status-approved';
      case 'SUPERSEDED':
        return 'status-superseded';
      case 'PENDING':
        return 'status-pending';
      case 'REJECTED':
        return 'status-rejected';
      case 'APPROVAL_TIMEOUT':
        return 'status-timeout';
      default:
        return 'status-unknown';
    }
  };

  // Get status display text
  const getStatusText = (status: string): string => {
    switch (status) {
      case 'APPROVED':
        return 'Approved';
      case 'SUPERSEDED':
        return 'Superseded';
      case 'PENDING':
        return 'Pending';
      case 'REJECTED':
        return 'Rejected';
      case 'APPROVAL_TIMEOUT':
        return 'Approval Timeout';
      default:
        return status;
    }
  };

  // Handle resubmit click
  const handleResubmit = () => {
    if (onResubmit) {
      onResubmit();
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="submission-history submission-history-loading">
        <div className="history-header">
          <h3>Submission History</h3>
        </div>
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>Loading submission history...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="submission-history submission-history-error">
        <div className="history-header">
          <h3>Submission History</h3>
        </div>
        <div className="error-message">
          <span className="error-icon">⚠️</span>
          <p>{error instanceof Error ? error.message : 'Failed to load history'}</p>
          <button onClick={() => refetch()} className="retry-button">
            Retry
          </button>
        </div>
      </div>
    );
  }

  // No data state (shouldn't happen, but handle gracefully)
  if (!history) {
    return null;
  }

  const canResubmit = history.remaining_submissions > 0;

  return (
    <div className="submission-history">
      {/* Header with remaining count */}
      <div className="history-header">
        <h3>Submission History</h3>
        <div className="remaining-count">
          <span className={`remaining-badge ${canResubmit ? 'remaining-active' : 'remaining-depleted'}`}>
            {history.remaining_submissions} submission{history.remaining_submissions !== 1 ? 's' : ''} remaining
          </span>
        </div>
      </div>

      {/* Empty state */}
      {history.submissions.length === 0 && (
        <div className="empty-state">
          <p>No submissions yet for this round.</p>
          {canResubmit && onResubmit && (
            <button onClick={handleResubmit} className="submit-button primary">
              Submit Your First Response
            </button>
          )}
        </div>
      )}

      {/* Submissions list */}
      {history.submissions.length > 0 && (
        <div className="submissions-list">
          {history.submissions.map((submission, index) => (
            <div
              key={submission.submission_id}
              className={`submission-item ${
                submission.is_currently_approved ? 'submission-approved' : ''
              }`}
            >
              {/* Submission header with status and timestamp */}
              <div className="submission-header">
                <div className="submission-meta">
                  <span className="submission-number">#{history.total_submissions - index}</span>
                  <span className="submission-timestamp">
                    {formatTimestamp(submission.submitted_at)}
                  </span>
                  {submission.modality === 'voice' && (
                    <span className="modality-badge">🎤 Voice</span>
                  )}
                </div>
                <div className="submission-status-container">
                  {submission.is_currently_approved && (
                    <span className="approved-indicator" title="Currently Approved">
                      ✓
                    </span>
                  )}
                  <span className={`status-badge ${getStatusClass(submission.summary_status)}`}>
                    {getStatusText(submission.summary_status)}
                  </span>
                </div>
              </div>

              {/* Submission text */}
              <div className="submission-text">
                <p>{submission.submission_text}</p>
              </div>

              {/* Approved indicator message */}
              {submission.is_currently_approved && (
                <div className="approved-message">
                  This submission is currently approved and will be used for clustering.
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Resubmit button */}
      {canResubmit && onResubmit && history.submissions.length > 0 && (
        <div className="resubmit-section">
          <button onClick={handleResubmit} className="submit-button secondary">
            Submit Again ({history.remaining_submissions} left)
          </button>
          <p className="resubmit-note">
            You can submit up to {history.remaining_submissions} more time{history.remaining_submissions !== 1 ? 's' : ''} this round.
            Your last approved submission will be used.
          </p>
        </div>
      )}

      {/* Rate limit reached message */}
      {!canResubmit && (
        <div className="rate-limit-message">
          <span className="info-icon">ℹ️</span>
          <p>You have reached the maximum of 3 submissions for this round.</p>
        </div>
      )}
    </div>
  );
};

export default SubmissionHistory;
