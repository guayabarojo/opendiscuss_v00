import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { discussionApi } from '../../services/discussionApi';
import './styles.css';

interface SubmissionFormProps {
  participantId: string;
  roundId: string;
  roundStatus: string;
  remainingSubmissions?: number;
  disabled?: boolean;
  onSubmitSuccess?: () => void;
}

interface SubmitRequest {
  participant_id: string;
  round_id: string;
  submission_text: string;
  modality: string;
}

interface SubmissionResponse {
  submission_id: string;
  participant_id: string;
  round_id: string;
  submission_text: string;
  modality: string;
  submitted_at: string;
  summary_status: string;
  remaining_submissions: number;
}

interface ApiError {
  error: string;
  message: string;
  details?: Record<string, unknown>;
}

/**
 * SubmissionForm Component (T073)
 *
 * Form for participants to submit responses with rate limiting.
 * Displays remaining submissions count and handles rate limit errors.
 *
 * Features:
 * - Character count with validation (1-2000 chars)
 * - Remaining submissions display
 * - Submit button disabled when limit reached or window closed
 * - Clear error messages for rate limits and timing violations
 * - Real-time validation feedback
 * - Success confirmation with remaining count
 *
 * Props:
 * - participantId: UUID of the participant
 * - roundId: UUID of the round
 * - roundStatus: Current round status (SUBMISSION_OPEN, etc.)
 * - remainingSubmissions: Number of submissions remaining (default 3)
 * - onSubmitSuccess: Optional callback after successful submission
 */
export const SubmissionForm: React.FC<SubmissionFormProps> = ({
  participantId,
  roundId,
  roundStatus,
  remainingSubmissions = 3,
  disabled = false,
  onSubmitSuccess,
}) => {
  const [submissionText, setSubmissionText] = useState('');
  const [modality] = useState('text'); // Future: add voice support
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const queryClient = useQueryClient();

  // Submit mutation
  const submitMutation = useMutation<SubmissionResponse, ApiError, SubmitRequest>({
    mutationFn: async (request: SubmitRequest) => {
      return await discussionApi.submitResponse(request);
    },
    onSuccess: (data) => {
      // Clear form
      setSubmissionText('');

      // Show success message
      setSuccessMessage(
        `Submission successful! ${data.remaining_submissions} submission${
          data.remaining_submissions !== 1 ? 's' : ''
        } remaining.`
      );

      // Clear success message after 5 seconds
      setTimeout(() => setSuccessMessage(null), 5000);

      // Invalidate submission history cache to refresh
      queryClient.invalidateQueries({ queryKey: ['submission-history', participantId, roundId] });

      // Call success callback if provided
      if (onSubmitSuccess) {
        onSubmitSuccess();
      }
    },
  });

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate submission text
    const trimmedText = submissionText.trim();
    if (!trimmedText) {
      submitMutation.reset(); // Clear previous errors
      return;
    }

    if (trimmedText.length < 1 || trimmedText.length > 2000) {
      return; // Validation already shows error
    }

    // Submit
    await submitMutation.mutateAsync({
      participant_id: participantId,
      round_id: roundId,
      submission_text: trimmedText,
      modality,
    });
  };

  // Character count and validation
  const charCount = submissionText.length;
  const isValidLength = charCount >= 1 && charCount <= 2000;
  const isSubmissionOpen = roundStatus === 'SUBMISSION_OPEN';
  const hasRemainingSubmissions = remainingSubmissions > 0;

  // Determine if submit button should be disabled
  const isSubmitDisabled =
    disabled ||
    !isValidLength ||
    !isSubmissionOpen ||
    !hasRemainingSubmissions ||
    submitMutation.isPending ||
    !submissionText.trim();

  // Get error message
  const getErrorMessage = (): string | null => {
    if (submitMutation.isError) {
      const error = submitMutation.error;

      // Rate limit error (429)
      if (error.error === 'Rate Limit Exceeded') {
        return 'Rate limit exceeded. You have reached the maximum of 3 submissions for this round.';
      }

      // Timing violation error (400)
      if (error.error === 'Timing Violation') {
        return error.message || 'Submission window is closed. Please wait for the next round.';
      }

      // Generic error
      return error.message || 'Failed to submit. Please try again.';
    }

    return null;
  };

  const errorMessage = getErrorMessage();

  return (
    <div className="submission-form">
      {/* Form header with remaining count */}
      <div className="form-header">
        <h3>Submit Your Response</h3>
        <div className="remaining-indicator">
          <span
            className={`remaining-badge ${
              hasRemainingSubmissions ? 'remaining-active' : 'remaining-depleted'
            }`}
          >
            {remainingSubmissions} submission{remainingSubmissions !== 1 ? 's' : ''} remaining
          </span>
        </div>
      </div>

      {/* Success message */}
      {successMessage && (
        <div className="success-message">
          <span className="success-icon">✓</span>
          <p>{successMessage}</p>
        </div>
      )}

      {/* Error message */}
      {errorMessage && (
        <div className="error-message">
          <span className="error-icon">⚠️</span>
          <p>{errorMessage}</p>
        </div>
      )}

      {/* Submission form */}
      <form onSubmit={handleSubmit}>
        {/* Textarea */}
        <div className="form-group">
          <label htmlFor="submission-text">
            Your Response
            <span className="required">*</span>
          </label>
          <textarea
            id="submission-text"
            value={submissionText}
            onChange={(e) => setSubmissionText(e.target.value)}
            placeholder="Share your thoughts on the question..."
            rows={6}
            maxLength={2000}
            disabled={disabled || !isSubmissionOpen || !hasRemainingSubmissions || submitMutation.isPending}
            className={!isValidLength && charCount > 0 ? 'input-error' : ''}
          />

          {/* Character count */}
          <div className="char-count">
            <span className={charCount > 2000 ? 'count-exceeded' : ''}>
              {charCount} / 2000 characters
            </span>
            {charCount > 0 && !isValidLength && (
              <span className="validation-error">
                {charCount < 1 ? 'Response cannot be empty' : 'Response exceeds maximum length'}
              </span>
            )}
          </div>
        </div>

        {/* Submit button */}
        <div className="form-actions">
          <button
            type="submit"
            className="submit-button"
            disabled={isSubmitDisabled}
            aria-label={
              isSubmitDisabled
                ? !isSubmissionOpen
                  ? 'Submission window closed'
                  : !hasRemainingSubmissions
                  ? 'Rate limit reached'
                  : 'Submit disabled'
                : 'Submit response'
            }
          >
            {submitMutation.isPending ? (
              <>
                <span className="button-spinner"></span>
                Submitting...
              </>
            ) : (
              <>Submit Response</>
            )}
          </button>

          {/* Status messages */}
          {!isSubmissionOpen && (
            <p className="status-message warning">
              Submission window is closed. Wait for the next round.
            </p>
          )}

          {isSubmissionOpen && !hasRemainingSubmissions && (
            <p className="status-message error">
              You have reached the maximum of 3 submissions for this round.
            </p>
          )}

          {isSubmissionOpen && hasRemainingSubmissions && charCount > 0 && isValidLength && (
            <p className="status-message info">
              You can submit up to {remainingSubmissions} more time
              {remainingSubmissions !== 1 ? 's' : ''}.
            </p>
          )}
        </div>
      </form>

      {/* Help text */}
      <div className="form-help">
        <p>
          <strong>Tip:</strong> Your last approved submission will be used for clustering. You can
          revise your response by submitting again.
        </p>
      </div>
    </div>
  );
};

export default SubmissionForm;
