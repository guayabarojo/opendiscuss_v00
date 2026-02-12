/**
 * ApprovalInterface page for Spec 003.
 *
 * Task T029: Show summary and handle approval workflow.
 * Task T030: Integrate SummaryReview component.
 *
 * Main interface for participants to review and approve their summaries.
 */

import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import SummaryReview from '../../components/SummaryReview/SummaryReview';
import SafetyNotice from '../../components/SafetyNotice/SafetyNotice';
import { CorrectionSignalForm, type ReasonTag } from '../../components/CorrectionSignalForm';
import {
  getSummary,
  getSummariesForParticipantRound,
  approveSummary,
  rejectSummary,
  submitCorrectionSignal,
  type Summary,
  type RejectResponse,
} from '../../services/summaryApi';
import './ApprovalInterface.css';

export const ApprovalInterface: React.FC = () => {
  const [searchParams] = useSearchParams();
  const summaryId = searchParams.get('summaryId');
  const participantId = searchParams.get('participantId');
  const roundId = searchParams.get('roundId');

  const [summary, setSummary] = useState<Summary | null>(null);
  const [allSummaries, setAllSummaries] = useState<Summary[]>([]);
  const [showAllSubmissions, setShowAllSubmissions] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [showCorrectionForm, setShowCorrectionForm] = useState(false);
  const [rejectedSummaryId, setRejectedSummaryId] = useState<string | null>(null);

  // Fetch summary on mount
  useEffect(() => {
    if (!summaryId) {
      setError('No summary ID provided');
      setLoading(false);
      return;
    }

    fetchSummary(summaryId);

    // T083-T084: Also fetch all summaries for participant if IDs provided
    if (participantId && roundId) {
      fetchAllSummaries(participantId, roundId);
    }
  }, [summaryId, participantId, roundId]);

  const fetchSummary = async (id: string) => {
    try {
      setLoading(true);
      setError(null);
      const data = await getSummary(id);
      setSummary(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load summary');
    } finally {
      setLoading(false);
    }
  };

  const fetchAllSummaries = async (pId: string, rId: string) => {
    try {
      const summaries = await getSummariesForParticipantRound(pId, rId);
      setAllSummaries(summaries);
    } catch (err) {
      console.error('Failed to load all summaries:', err);
      // Don't set error state, just log it
    }
  };

  const handleApprove = async (id: string) => {
    try {
      setActionLoading(true);
      setError(null);

      await approveSummary(id);

      // Refresh summary to show updated status
      await fetchSummary(id);

      // Show success message
      alert('Summary approved successfully! ✓');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve summary');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async (id: string) => {
    try {
      setActionLoading(true);
      setError(null);

      // User Story 2 (T043): Automatic regeneration workflow
      const rejectResponse: RejectResponse = await rejectSummary(id);

      if (rejectResponse.new_summary) {
        // Automatic regeneration successful (regen_count < 2)
        setSummary(rejectResponse.new_summary);
        alert(
          `Summary rejected. ${rejectResponse.message}\n\nPlease review the new summary below.`
        );
      } else if (rejectResponse.needs_correction_signal) {
        // Max automatic regenerations reached (regen_count >= 2)
        // User Story 3 (T057-T058): Show CorrectionSignalForm
        setRejectedSummaryId(id);
        setShowCorrectionForm(true);
        await fetchSummary(id);
      } else {
        // Fallback: just refresh
        alert('Summary rejected. Please wait while a new summary is generated...');
        await fetchSummary(id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reject summary');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCorrectionSubmit = async (reasonTag: ReasonTag, feedbackText: string) => {
    if (!rejectedSummaryId) {
      setError('No rejected summary to correct');
      return;
    }

    try {
      setActionLoading(true);
      setError(null);

      // User Story 3 (T057): Submit correction signal and get final regeneration
      const correctionResponse = await submitCorrectionSignal(rejectedSummaryId, {
        reason_tag: reasonTag,
        feedback_text: feedbackText || undefined,
      });

      // Hide correction form
      setShowCorrectionForm(false);
      setRejectedSummaryId(null);

      // Fetch the new summary
      await fetchSummary(correctionResponse.new_summary_id);

      // Show message
      alert(
        `${correctionResponse.message}\n\nPlease review the final summary below (Attempt ${correctionResponse.regen_count}/3).`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit correction signal');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCorrectionCancel = () => {
    setShowCorrectionForm(false);
    setRejectedSummaryId(null);
  };

  // Loading state
  if (loading) {
    return (
      <div className="approval-interface">
        <div className="loading">
          <div className="spinner"></div>
          <p>Loading summary...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="approval-interface">
        <div className="error-container">
          <h2>Error</h2>
          <p className="error-message">{error}</p>
          <button
            className="btn btn-retry"
            onClick={() => summaryId && fetchSummary(summaryId)}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // No summary state
  if (!summary) {
    return (
      <div className="approval-interface">
        <div className="error-container">
          <h2>No Summary Found</h2>
          <p>The requested summary could not be found.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="approval-interface">
      <header className="approval-header">
        <h1>Summary Approval</h1>
        <p className="subtitle">
          Review the AI-generated summary of your input and approve it if it
          accurately represents your intent.
        </p>
      </header>

      <main className="approval-content">
        {/* T083-T084: Show multiple submissions toggle if available */}
        {allSummaries.length > 1 && (
          <div className="multiple-submissions-notice">
            <p>
              You have {allSummaries.length} submissions for this round.{' '}
              {allSummaries.filter(s => s.status === 'approved').length > 0 && (
                <span>
                  The most recently approved submission will be used for clustering.
                </span>
              )}
            </p>
            <button
              className="btn btn-secondary"
              onClick={() => setShowAllSubmissions(!showAllSubmissions)}
            >
              {showAllSubmissions ? 'Hide' : 'Show'} All Submissions
            </button>
          </div>
        )}

        {/* Task T072: Show SafetyNotice if safety_flags present */}
        {summary.safety_flags && summary.safety_flags.length > 0 && (
          <SafetyNotice
            safetyFlags={summary.safety_flags as any}
            summaryStatus={summary.status}
            variant={
              summary.status === 'disallowed_content'
                ? 'error'
                : summary.safety_flags.includes('profanity_neutralized')
                ? 'warning'
                : 'info'
            }
          />
        )}

        {/* Task T073: Display block message for DISALLOWED_CONTENT */}
        {summary.status === 'disallowed_content' ? (
          <div className="disallowed-content-notice">
            <h2>Content Review Required</h2>
            <p>
              Your submission cannot be approved due to safety violations.
              Please return to the discussion and submit content that:
            </p>
            <ul>
              <li>Focuses on the discussion topic</li>
              <li>Does not contain threats or illegal content</li>
              <li>Does not contain hate speech or harassment</li>
              <li>Respects community safety guidelines</li>
            </ul>
            <button
              className="btn btn-primary"
              onClick={() => window.location.href = '/discussion'}
            >
              Return to Discussion
            </button>
          </div>
        ) : (
          <>
            {/* T058: Display REJECTED_FINAL notification */}
            {summary.status === 'rejected_final' && (
              <div className="rejected-final-notice">
                <h2>Summary Could Not Be Approved</h2>
                <p>
                  After 3 regeneration attempts, we were unable to create a summary that accurately
                  represents your input. You may:
                </p>
                <ul>
                  <li>
                    <strong>Resubmit your input</strong> with different wording (if time allows in
                    the current round)
                  </li>
                  <li>
                    <strong>Participate in the next round</strong> to contribute your perspective
                  </li>
                </ul>
                <div className="rejected-final-actions">
                  <button
                    className="btn btn-primary"
                    onClick={() => (window.location.href = '/discussion')}
                  >
                    Return to Discussion
                  </button>
                </div>
                <p className="rejected-final-help">
                  <strong>Why did this happen?</strong> The summarization AI may have had difficulty
                  identifying the core point of your input. Try rephrasing your position more
                  clearly in your next submission.
                </p>
              </div>
            )}

            {/* T056-T057: Show CorrectionSignalForm after 2 rejections */}
            {showCorrectionForm && rejectedSummaryId && summary.regen_count === 2 && (
              <CorrectionSignalForm
                summaryId={rejectedSummaryId}
                onSubmit={handleCorrectionSubmit}
                onCancel={handleCorrectionCancel}
                disabled={actionLoading}
              />
            )}

            {/* T083-T084: Show all submissions if toggled */}
            {showAllSubmissions && allSummaries.length > 1 ? (
              <div className="all-submissions-view">
                <h2>All Your Submissions (Latest First)</h2>
                {allSummaries.map((s) => (
                  <SummaryReview
                    key={s.summary_id}
                    summary={s}
                    onApprove={handleApprove}
                    onReject={handleReject}
                    isLoading={actionLoading}
                    showReject={s.status === 'pending_review'}
                  />
                ))}
              </div>
            ) : (
              <>
                {/* T030: Integrate SummaryReview component */}
                <SummaryReview
                  summary={summary}
                  onApprove={handleApprove}
                  onReject={handleReject}
                  isLoading={actionLoading}
                  showReject={true}  // Enable rejection for User Story 2
                />
              </>
            )}
          </>
        )}

        {/* Constitutional Principle Explanation */}
        <div className="constitutional-notice">
          <h3>Why Approval Matters</h3>
          <p>
            <strong>Intent Fidelity:</strong> Your explicit approval ensures
            that only accurate summaries enter the discussion analysis. This is
            a critical trust gate that prevents misrepresentation of your views.
          </p>
          <p>
            <strong>Parallel-First Architecture:</strong> Your summary was
            generated independently without cross-participant influence,
            preserving the integrity of your original input.
          </p>
        </div>

        {/* Navigation hint */}
        <div className="navigation-hint">
          <p>
            Once approved, your summary will be forwarded to clustering and
            contribute to identifying thought spaces in the discussion.
          </p>
        </div>
      </main>
    </div>
  );
};

export default ApprovalInterface;
