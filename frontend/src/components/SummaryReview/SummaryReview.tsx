/**
 * SummaryReview component for Spec 003.
 *
 * Task T027: Approve/reject buttons for summary review.
 *
 * Displays generated summary and allows participant to:
 * - Approve summary (Intent Fidelity gate)
 * - Reject summary (triggers regeneration in User Story 2)
 */

import React from 'react';
import './SummaryReview.css';
import type { Summary } from '../../services/summaryApi';

export interface SummaryReviewProps {
  /** Summary to review */
  summary: Summary;
  /** Callback when approve button clicked */
  onApprove: (summaryId: string) => void;
  /** Callback when reject button clicked */
  onReject: (summaryId: string) => void;
  /** Loading state for approve/reject actions */
  isLoading?: boolean;
  /** Show rejection button (for User Story 2) */
  showReject?: boolean;
}

export const SummaryReview: React.FC<SummaryReviewProps> = ({
  summary,
  onApprove,
  onReject,
  isLoading = false,
  showReject = false,
}) => {
  const handleApprove = () => {
    if (!isLoading) {
      onApprove(summary.summary_id);
    }
  };

  const handleReject = () => {
    if (!isLoading && showReject) {
      onReject(summary.summary_id);
    }
  };

  // Format timestamp for display
  const formatTimestamp = (isoString: string) => {
    try {
      return new Date(isoString).toLocaleString();
    } catch {
      return isoString;
    }
  };

  // Show attempt count if regenerated
  const attemptText =
    summary.regen_count > 0
      ? ` (Attempt ${summary.regen_count + 1}/3)`
      : '';

  // Check if this is the last approved (for User Story 5)
  const isSuperseded = summary.status === 'superseded';
  const isApproved = summary.status === 'approved';

  return (
    <div className={`summary-review ${isSuperseded ? 'superseded' : ''}`}>
      <div className="summary-header">
        <h3>Review Your Summary{attemptText}</h3>
        <span className={`summary-status status-${summary.status}`}>
          {summary.status}
        </span>
      </div>

      {/* T083-T084: Visual indicator for superseded summaries */}
      {isSuperseded && (
        <div className="superseded-notice">
          <strong>Note:</strong> This summary has been superseded by a newer approval.
          Only the most recently approved summary will be forwarded to clustering.
        </div>
      )}

      <div className="summary-content">
        <p className="summary-text">{summary.summary_text}</p>
        <div className="summary-meta">
          <span className="char-count">
            {summary.summary_text.length}/500 characters
          </span>
          <span className="created-at">
            Generated: {formatTimestamp(summary.created_at)}
          </span>
          {summary.approved_at && (
            <span className="approved-at">
              Approved: {formatTimestamp(summary.approved_at)}
            </span>
          )}
        </div>
      </div>

      {/* Safety flags (User Story 4) */}
      {summary.safety_flags && summary.safety_flags.length > 0 && (
        <div className="safety-flags">
          <strong>Safety Note:</strong>
          <ul>
            {summary.safety_flags.map((flag, idx) => (
              <li key={idx}>{flag}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Action buttons */}
      {summary.status === 'pending_review' && (
        <div className="summary-actions">
          <button
            className="btn btn-approve"
            onClick={handleApprove}
            disabled={isLoading}
          >
            {isLoading ? 'Processing...' : 'Approve Summary'}
          </button>

          {showReject && (
            <button
              className="btn btn-reject"
              onClick={handleReject}
              disabled={isLoading}
            >
              Reject & Regenerate
            </button>
          )}
        </div>
      )}

      {/* Approved state - T083-T084: Highlight last approved */}
      {isApproved && summary.approved_at && (
        <div className="summary-approved">
          <p className="success-message">
            ✓ Summary approved and will be forwarded to clustering
          </p>
          <span className="approved-at">
            Approved: {formatTimestamp(summary.approved_at)}
          </span>
        </div>
      )}

      {/* Help text */}
      <div className="summary-help">
        <p>
          <strong>Intent Fidelity:</strong> Your approval ensures this summary
          accurately represents your input before it's used in discussion
          analysis.
        </p>
      </div>
    </div>
  );
};

export default SummaryReview;
