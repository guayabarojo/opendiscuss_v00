import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { discussionApi } from '../services/discussionApi';
import { RoundTimer } from '../components/RoundTimer';
import { HostControls } from '../components/HostControls';
import { AsyncRoundControls } from '../components/AsyncRoundControls';
import { useAuth } from '../contexts/AuthContext';
import type { Discussion, RoundStatusResponse, ApiError } from '../types/api';
import './DiscussionLive.css';

/**
 * DiscussionLive Component
 *
 * Real-time discussion status display showing:
 * - Current question and round number
 * - Participant count and statistics
 * - Round timer countdown (via RoundTimer component)
 * - Host controls (Start Discussion, Advance Round buttons)
 * - Participant view (Submit Input button)
 *
 * Polls GET /rounds/{id}/status every 5 seconds for updates.
 * Uses React Query for data fetching and caching.
 */
export const DiscussionLive: React.FC = () => {
  const { discussionId } = useParams<{ discussionId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [currentRoundId, setCurrentRoundId] = useState<string | null>(null);
  const { isHost } = useAuth();

  // Fetch discussion details
  const {
    data: discussion,
    isLoading: discussionLoading,
    error: discussionError,
  } = useQuery<Discussion, ApiError>({
    queryKey: ['discussion', discussionId],
    queryFn: () => discussionApi.getDiscussion(discussionId!),
    enabled: !!discussionId,
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  // Update current round ID when discussion data changes
  useEffect(() => {
    if (discussion && discussion.current_round_num > 0 && discussion.rounds) {
      // Find the current round in the rounds array
      const currentRound = discussion.rounds.find(
        (r) => r.round_num === discussion.current_round_num
      );
      if (currentRound) {
        setCurrentRoundId(currentRound.round_id);
      }
    }
  }, [discussion]);

  // Fetch round status (only when discussion is active)
  const {
    data: roundStatus,
    error: roundError,
  } = useQuery<RoundStatusResponse, ApiError>({
    queryKey: ['roundStatus', currentRoundId],
    queryFn: () => discussionApi.getRoundStatus(currentRoundId!),
    enabled: !!currentRoundId && discussion?.status === 'ACTIVE',
    refetchInterval: 5000, // Poll every 5 seconds
  });

  // Start discussion mutation
  const startMutation = useMutation({
    mutationFn: () => discussionApi.startDiscussion(discussionId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['discussion', discussionId] });
    },
  });

  const handleStartDiscussion = () => {
    if (window.confirm('Start the discussion? This will open Round 1 for submissions.')) {
      startMutation.mutate();
    }
  };

  const handleSubmitInput = () => {
    // Redirect to submission form
    navigate(`/discussions/${discussionId}/submit`);
  };

  // Loading state
  if (discussionLoading) {
    return (
      <div className="discussion-live-container">
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>Loading discussion...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (discussionError || !discussion) {
    return (
      <div className="discussion-live-container">
        <div className="error-container">
          <h2>Error Loading Discussion</h2>
          <p>{discussionError?.message || 'Discussion not found'}</p>
          <button onClick={() => navigate('/discussions')} className="btn btn-primary">
            Back to Discussions
          </button>
        </div>
      </div>
    );
  }

  // Get status badge styling
  const getStatusBadgeClass = (status: string): string => {
    switch (status) {
      case 'CREATED':
        return 'status-badge status-created';
      case 'ACTIVE':
        return 'status-badge status-active';
      case 'COMPLETED':
        return 'status-badge status-completed';
      case 'TERMINATED':
        return 'status-badge status-terminated';
      default:
        return 'status-badge';
    }
  };

  const isDiscussionHost = discussion ? isHost(discussion) : false;
  const canStartDiscussion = discussion.status === 'CREATED' && isDiscussionHost;

  return (
    <div className="discussion-live-container">
      <div className="discussion-live-card">
        {/* Header */}
        <div className="discussion-header">
          <div>
            <h1 className="discussion-title">Live Discussion</h1>
            <p className="discussion-id">ID: {discussion.discussion_id}</p>
          </div>
          <span className={getStatusBadgeClass(discussion.status)}>
            {discussion.status}
          </span>
        </div>

        {/* Status Info */}
        <div className="status-grid">
          <div className="status-item">
            <span className="status-label">Current Round</span>
            <span className="status-value">
              {discussion.current_round_num === 0
                ? 'Not Started'
                : `${discussion.current_round_num} / ${discussion.total_rounds}`}
            </span>
          </div>
          <div className="status-item">
            <span className="status-label">Participants</span>
            <span className="status-value">
              {roundStatus?.participant_stats?.submitted_count ?? 0} submitted
            </span>
          </div>
          <div className="status-item">
            <span className="status-label">Mode</span>
            <span className="status-value">{discussion.mode}</span>
          </div>
        </div>

        {/* Current Question */}
        {discussion.status === 'ACTIVE' && roundStatus && (
          <div className="current-question-section">
            <h2 className="section-title">Round {discussion.current_round_num} / {discussion.total_rounds}</h2>
            <div className="question-card">
              <div className="question-header">
                <span className="round-badge">Round {discussion.current_round_num}</span>
                <span className={`round-status-badge ${(roundStatus?.round_status || roundStatus?.status || 'unknown').toLowerCase()}`}>
                  {(roundStatus?.round_status || roundStatus?.status || 'Unknown').replace(/_/g, ' ')}
                </span>
              </div>

              {/* Window Status */}
              <div className="window-status">
                <p><strong>Window Status:</strong> {roundStatus?.is_open ? '✅ Open' : '🔒 Closed'}</p>
                {roundStatus?.window_start && (
                  <p><strong>Started:</strong> {new Date(roundStatus.window_start).toLocaleTimeString()}</p>
                )}
                {roundStatus?.window_end && (
                  <p><strong>Closes:</strong> {new Date(roundStatus.window_end).toLocaleTimeString()}</p>
                )}
                {roundStatus?.time_remaining_seconds != null && roundStatus.time_remaining_seconds > 0 && (
                  <p><strong>Time Remaining:</strong> {Math.floor(roundStatus.time_remaining_seconds / 60)}m {roundStatus.time_remaining_seconds % 60}s</p>
                )}
              </div>
            </div>

            {/* Round Timer or Async Controls - based on timing mode */}
            {roundStatus?.is_open && roundStatus?.window_end && (
              discussion.timing_mode === 'ASYNCHRONOUS' ? (
                <AsyncRoundControls
                  roundId={currentRoundId || ''}
                  isHost={isDiscussionHost}
                  status={roundStatus.status || roundStatus.round_status || 'UNKNOWN'}
                  submissionCount={roundStatus.participant_stats?.submitted_count ?? 0}
                  minSubmissions={discussion.min_submissions_for_advance}
                  roundDurationHours={discussion.round_duration_hours}
                  startTime={roundStatus.window_start ? new Date(roundStatus.window_start) : new Date()}
                  onCloseRound={async () => {
                    if (currentRoundId) {
                      try {
                        await discussionApi.closeRound(currentRoundId);
                        queryClient.invalidateQueries({ queryKey: ['discussion', discussionId] });
                        queryClient.invalidateQueries({ queryKey: ['roundStatus', currentRoundId] });
                      } catch (error) {
                        console.error('Failed to close round:', error);
                        alert('Failed to close round. Please try again.');
                      }
                    }
                  }}
                />
              ) : (
                <RoundTimer windowEnd={roundStatus.window_end} />
              )
            )}

            {/* Participant Stats - only if available */}
            {roundStatus?.participant_stats && (
              <div className="participant-stats">
                <div className="stat-item">
                  <span className="stat-number">
                    {roundStatus.participant_stats?.submitted_count ?? 0}
                  </span>
                  <span className="stat-label">Submitted</span>
                </div>
                <div className="stat-item">
                  <span className="stat-number">
                    {roundStatus.participant_stats?.approved_count ?? 0}
                  </span>
                  <span className="stat-label">Approved</span>
                </div>
                <div className="stat-item">
                  <span className="stat-number">
                    {roundStatus.participant_stats?.pending_approval_count ?? 0}
                  </span>
                  <span className="stat-label">Pending</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Not Started State */}
        {discussion.status === 'CREATED' && (
          <div className="not-started-section">
            <div className="info-card">
              <h2>Discussion Ready to Start</h2>
              <p>
                This discussion has {discussion.total_rounds} rounds prepared.
                {isDiscussionHost
                  ? ' Click the button below to begin.'
                  : ' Waiting for the host to start...'}
              </p>
            </div>
          </div>
        )}

        {/* Completed State */}
        {discussion.status === 'COMPLETED' && (
          <div className="completed-section">
            <div className="info-card success">
              <h2>Discussion Completed</h2>
              <p>All rounds have been completed. View the final report to see results.</p>
              <button
                onClick={() => navigate(`/discussions/${discussionId}/report`)}
                className="btn btn-primary"
              >
                View Report
              </button>
            </div>
          </div>
        )}

        {/* Host Controls - Advance Round */}
        {isDiscussionHost && discussion.status === 'ACTIVE' && (
          <HostControls
            discussion={discussion}
            currentRoundStatus={roundStatus?.status}
          />
        )}

        {/* Error Display */}
        {(startMutation.isError || roundError) && (
          <div className="alert alert-error">
            {startMutation.error?.message || roundError?.message}
          </div>
        )}

        {/* Action Buttons */}
        <div className="action-buttons">
          {isDiscussionHost && canStartDiscussion && (
            <button
              onClick={handleStartDiscussion}
              disabled={startMutation.isPending}
              className="btn btn-primary btn-large"
            >
              {startMutation.isPending ? 'Starting...' : 'Start Discussion'}
            </button>
          )}

          {!isDiscussionHost &&
           discussion.status === 'ACTIVE' &&
           roundStatus?.status === 'SUBMISSION_OPEN' && (
            <button
              onClick={handleSubmitInput}
              className="btn btn-success btn-large"
            >
              Submit Your Input
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default DiscussionLive;
