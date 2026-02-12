import React, { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { discussionApi } from '../../services/discussionApi'
import type { Discussion, RoundStatus, ApiError } from '../../types/api'
import './styles.css'

interface HostControlsProps {
  discussion: Discussion
  currentRoundStatus?: RoundStatus
  disabled?: boolean
}

/**
 * HostControls Component
 *
 * Provides host-only controls for discussion management:
 * - Advance Round button (visible only when current round is COMPLETE)
 * - Confirmation dialog before advancing
 * - Loading state during API call
 * - Error handling with user-friendly messages
 *
 * Props:
 * - discussion: Current discussion object
 * - currentRoundStatus: Status of the current round
 * - disabled: Override to disable controls
 */
export const HostControls: React.FC<HostControlsProps> = ({
  discussion,
  currentRoundStatus,
  disabled = false,
}) => {
  const queryClient = useQueryClient()
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [confirmError, setConfirmError] = useState<string | null>(null)

  // Advance round mutation
  const advanceMutation = useMutation<Discussion, ApiError>({
    mutationFn: () => discussionApi.advanceRound(discussion.discussion_id),
    onSuccess: () => {
      // Update discussion cache
      queryClient.invalidateQueries({
        queryKey: ['discussion', discussion.discussion_id],
      })
      // Close confirmation dialog
      setShowConfirmDialog(false)
      setConfirmError(null)
    },
    onError: (error: ApiError) => {
      setConfirmError(
        error.message || 'Failed to advance round. Please try again.'
      )
    },
  })

  // Determine if advance button should be enabled
  const canAdvanceRound =
    !disabled &&
    discussion.status === 'ACTIVE' &&
    currentRoundStatus === 'COMPLETE' &&
    discussion.current_round_num < discussion.total_rounds

  const isLastRound = discussion.current_round_num === discussion.total_rounds

  const handleAdvanceClick = () => {
    setShowConfirmDialog(true)
    setConfirmError(null)
  }

  const handleConfirmAdvance = () => {
    advanceMutation.mutate()
  }

  const handleCancelAdvance = () => {
    setShowConfirmDialog(false)
    setConfirmError(null)
  }

  const nextRoundNum = discussion.current_round_num + 1

  // Don't render if discussion is not active or already completed
  if (discussion.status !== 'ACTIVE') {
    return null
  }

  return (
    <div className="host-controls">
      <div className="host-controls-content">
        {/* Advance Round Button */}
        <button
          onClick={handleAdvanceClick}
          disabled={!canAdvanceRound || advanceMutation.isPending}
          className={`btn btn-advance ${!canAdvanceRound ? 'btn-disabled' : ''}`}
          aria-label={`Advance to Round ${nextRoundNum}`}
          title={
            !canAdvanceRound && currentRoundStatus !== 'COMPLETE'
              ? 'Current round must be complete before advancing'
              : `Advance to Round ${nextRoundNum}`
          }
        >
          {advanceMutation.isPending ? (
            <>
              <span className="spinner-small" aria-hidden="true"></span>
              Advancing...
            </>
          ) : (
            <>
              {isLastRound
                ? 'Complete Discussion'
                : `Advance to Round ${nextRoundNum}`}
            </>
          )}
        </button>

        {/* Status Message */}
        {!canAdvanceRound && currentRoundStatus !== 'COMPLETE' && (
          <p className="host-controls-message">
            Waiting for Round {discussion.current_round_num} to complete...
          </p>
        )}
      </div>

      {/* Confirmation Dialog */}
      {showConfirmDialog && (
        <div
          className="confirmation-dialog-overlay"
          onClick={handleCancelAdvance}
          role="dialog"
          aria-labelledby="confirm-dialog-title"
          aria-describedby="confirm-dialog-desc"
          aria-modal="true"
        >
          <div
            className="confirmation-dialog"
            onClick={e => e.stopPropagation()}
          >
            <div className="confirmation-dialog-header">
              <h3 id="confirm-dialog-title">Confirm Round Advancement</h3>
            </div>

            <div className="confirmation-dialog-body">
              <p id="confirm-dialog-desc">
                {isLastRound ? (
                  <>
                    Are you sure you want to complete the discussion? This will
                    finalize Round {discussion.current_round_num} and mark the
                    discussion as complete.
                  </>
                ) : (
                  <>
                    Are you sure you want to advance to Round {nextRoundNum}?
                    This will close Round {discussion.current_round_num} and
                    open the submission window for the next round.
                  </>
                )}
              </p>

              {confirmError && (
                <div className="alert alert-error" role="alert">
                  {confirmError}
                </div>
              )}
            </div>

            <div className="confirmation-dialog-footer">
              <button
                onClick={handleCancelAdvance}
                className="btn btn-secondary"
                disabled={advanceMutation.isPending}
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmAdvance}
                className="btn btn-primary"
                disabled={advanceMutation.isPending}
                autoFocus
              >
                {advanceMutation.isPending ? (
                  <>
                    <span className="spinner-small"></span>
                    Advancing...
                  </>
                ) : (
                  'Confirm'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default HostControls
