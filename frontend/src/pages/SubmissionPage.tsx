import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { discussionApi } from '../services/discussionApi';
import { SubmissionForm } from '../components/SubmissionForm';
import { SubmissionHistory } from '../components/SubmissionHistory';
import { CountdownTimer } from '../components/CountdownTimer';
import type { Discussion, RoundStatusResponse, ApiError } from '../types/api';
import './SubmissionPage.css';

/**
 * SubmissionPage Component
 *
 * Dedicated page for participants to submit and manage their responses.
 * Displays the submission form and history for the current round.
 *
 * Features:
 * - Shows current question and round information
 * - Submission form with rate limiting (SubmissionForm component)
 * - Submission history with approval status (SubmissionHistory component)
 * - Navigation back to live discussion view
 */
export const SubmissionPage: React.FC = () => {
  const { discussionId } = useParams<{ discussionId: string }>();
  const navigate = useNavigate();

  // Track if window is open (controlled by countdown timer)
  const [isWindowOpen, setIsWindowOpen] = useState(true);

  // Mock participant ID - in production, get from auth context
  const participantId = localStorage.getItem('participant_id') || 'mock-participant-001';

  // Ensure participant ID is persisted
  useEffect(() => {
    if (!localStorage.getItem('participant_id')) {
      localStorage.setItem('participant_id', participantId);
    }
  }, [participantId]);

  // Fetch discussion details
  const {
    data: discussion,
    isLoading,
    error,
  } = useQuery<Discussion, ApiError>({
    queryKey: ['discussion', discussionId],
    queryFn: () => discussionApi.getDiscussion(discussionId!),
    enabled: !!discussionId,
  });

  // Calculate current round ID
  const getCurrentRoundId = (): string | null => {
    if (!discussion || discussion.current_round_num === 0) {
      return null;
    }
    // In production, fetch the actual round_id from discussion rounds
    // For now, use a mock round ID based on discussion and round number
    return `round-${discussion.discussion_id}-${discussion.current_round_num}`;
  };

  const currentRoundId = getCurrentRoundId();

  // Fetch round status to get question text and timing info
  const {
    data: roundStatus,
    isLoading: roundLoading,
  } = useQuery<RoundStatusResponse, ApiError>({
    queryKey: ['roundStatus', currentRoundId],
    queryFn: () => discussionApi.getRoundStatus(currentRoundId!),
    enabled: !!currentRoundId && discussion?.status === 'ACTIVE',
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  // Loading state
  if (isLoading || roundLoading) {
    return (
      <div className="submission-page-container">
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>Loading submission page...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !discussion) {
    return (
      <div className="submission-page-container">
        <div className="error-container">
          <h2>Error Loading Discussion</h2>
          <p>{error?.message || 'Discussion not found'}</p>
          <button onClick={() => navigate('/')} className="btn btn-primary">
            Back to Home
          </button>
        </div>
      </div>
    );
  }

  // Check if submissions are allowed
  const canSubmit = discussion.status === 'ACTIVE' && currentRoundId;

  if (!canSubmit) {
    return (
      <div className="submission-page-container">
        <div className="info-container">
          <h2>Submissions Not Available</h2>
          <p>
            {discussion.status === 'CREATED'
              ? 'Discussion has not started yet.'
              : discussion.status === 'COMPLETED'
              ? 'Discussion has been completed.'
              : 'Submissions are currently closed.'}
          </p>
          <button
            onClick={() => navigate(`/discussions/${discussionId}/live`)}
            className="btn btn-primary"
          >
            Back to Discussion
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="submission-page-container">
      <div className="submission-page-header">
        <button
          onClick={() => navigate(`/discussions/${discussionId}/live`)}
          className="back-button"
        >
          ← Back to Discussion
        </button>
        <h1>Submit Your Response</h1>
      </div>

      <div className="submission-page-content">
        {/* Countdown Timer */}
        <CountdownTimer
          roundId={currentRoundId}
          onWindowClose={() => {
            setIsWindowOpen(false);
          }}
        />

        {/* Question Display */}
        <div className="question-display">
          <div className="question-meta">
            <span className="round-badge">
              Round {discussion.current_round_num} of {discussion.total_rounds}
            </span>
            <span className="status-badge status-active">
              {roundStatus?.status?.replace(/_/g, ' ') || 'LOADING'}
            </span>
          </div>
          <div className="question-text">
            <h2>Current Question</h2>
            <p>
              {roundStatus?.question_text || 'Loading question...'}
            </p>
          </div>
        </div>

        {/* Window Closed Message */}
        {!isWindowOpen && (
          <div className="window-closed-message">
            <h3>⏱️ Submission Window Closed</h3>
            <p>The submission window for this round has ended. Please wait for the next round.</p>
          </div>
        )}

        {/* Submission Form */}
        <div className="submission-section">
          <SubmissionForm
            participantId={participantId}
            roundId={currentRoundId}
            roundStatus={roundStatus?.status || 'SUBMISSION_CLOSED'}
            remainingSubmissions={3} // Will be updated by backend response
            disabled={!isWindowOpen}
            onSubmitSuccess={() => {
              // Submission was successful, history will auto-refresh
              console.log('Submission successful');
            }}
          />
        </div>

        {/* Submission History */}
        <div className="history-section">
          <SubmissionHistory
            participantId={participantId}
            roundId={currentRoundId}
            onResubmit={() => {
              // Scroll to submission form
              window.scrollTo({ top: 0, behavior: 'smooth' });
            }}
          />
        </div>
      </div>
    </div>
  );
};

export default SubmissionPage;
