/**
 * CorrectionSignalForm component for Spec 003 (User Story 3).
 *
 * Displays after 2 rejections to collect correction signal from participant.
 * Tasks T055-T056.
 */

import React, { useState } from 'react';
import './CorrectionSignalForm.css';

export type ReasonTag =
  | 'wrong_crux'
  | 'too_vague'
  | 'misrepresents_me'
  | 'missed_constraint'
  | 'missed_solution'
  | 'other';

interface ReasonTagOption {
  value: ReasonTag;
  label: string;
  description: string;
}

const REASON_TAG_OPTIONS: ReasonTagOption[] = [
  {
    value: 'wrong_crux',
    label: 'Wrong crux - summary missed my main point',
    description:
      'The summary identified the wrong core point. Your main argument or perspective was not accurately captured.',
  },
  {
    value: 'too_vague',
    label: 'Too vague - summary needs more specificity',
    description:
      'The summary was too general or abstract. It needs more specific details to accurately represent your position.',
  },
  {
    value: 'misrepresents_me',
    label: 'Misrepresents me - summary changes my stance',
    description:
      "The summary changed or misrepresented your stance. The way it's phrased makes it sound like you said something different than you intended.",
  },
  {
    value: 'missed_constraint',
    label: 'Missed constraint - summary omitted key condition',
    description:
      "The summary omitted an important condition or qualifier from your input. Your position has specific constraints that weren't captured.",
  },
  {
    value: 'missed_solution',
    label: 'Missed solution - summary omitted my proposal',
    description:
      'The summary missed your proposed solution or recommendation. It focused on the problem but not what you think should be done.',
  },
  {
    value: 'other',
    label: 'Other (see feedback)',
    description:
      "The issue doesn't fit the above categories. Please provide specific feedback in the text box below.",
  },
];

interface CorrectionSignalFormProps {
  summaryId: string;
  onSubmit: (reasonTag: ReasonTag, feedbackText: string) => void | Promise<void>;
  onCancel?: () => void;
  disabled?: boolean;
}

export const CorrectionSignalForm: React.FC<CorrectionSignalFormProps> = ({
  summaryId: _summaryId,
  onSubmit,
  onCancel,
  disabled = false,
}) => {
  const [selectedReasonTag, setSelectedReasonTag] = useState<ReasonTag | null>(null);
  const [feedbackText, setFeedbackText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const remainingChars = 240 - feedbackText.length;
  const isValid = selectedReasonTag !== null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!isValid) {
      setError('Please select a reason for rejection');
      return;
    }

    if (feedbackText.length > 240) {
      setError('Feedback must be 240 characters or less');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await onSubmit(selectedReasonTag!, feedbackText.trim() || '');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit correction signal');
      setIsSubmitting(false);
    }
  };

  const handleReasonTagChange = (reasonTag: ReasonTag) => {
    setSelectedReasonTag(reasonTag);
    setError(null);
  };

  const selectedOption = REASON_TAG_OPTIONS.find((opt) => opt.value === selectedReasonTag);

  return (
    <div className="correction-signal-form">
      <div className="correction-signal-form__header">
        <h3>Help Improve Your Summary</h3>
        <p className="correction-signal-form__subtitle">
          This is your final regeneration attempt (3/3). Tell us what's wrong so we can better
          capture your intent.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="correction-signal-form__form">
        {/* Reason Tags */}
        <div className="correction-signal-form__section">
          <label className="correction-signal-form__label">
            What's the main issue with the summary? <span className="required">*</span>
          </label>

          <div className="correction-signal-form__options">
            {REASON_TAG_OPTIONS.map((option) => (
              <div key={option.value} className="correction-signal-form__option">
                <label className="correction-signal-form__radio-label">
                  <input
                    type="radio"
                    name="reason_tag"
                    value={option.value}
                    checked={selectedReasonTag === option.value}
                    onChange={() => handleReasonTagChange(option.value)}
                    disabled={disabled || isSubmitting}
                    className="correction-signal-form__radio"
                  />
                  <span className="correction-signal-form__radio-text">
                    <span className="correction-signal-form__radio-label-text">{option.label}</span>
                    <span className="correction-signal-form__radio-description">
                      {option.description}
                    </span>
                  </span>
                </label>
              </div>
            ))}
          </div>

          {selectedOption && (
            <div className="correction-signal-form__selected-info">
              <strong>Selected:</strong> {selectedOption.label}
            </div>
          )}
        </div>

        {/* Feedback Text */}
        <div className="correction-signal-form__section">
          <label htmlFor="feedback_text" className="correction-signal-form__label">
            Additional feedback (optional)
          </label>
          <p className="correction-signal-form__help-text">
            Provide specific details about what needs to change. This helps us generate a better
            summary.
          </p>
          <textarea
            id="feedback_text"
            name="feedback_text"
            value={feedbackText}
            onChange={(e) => setFeedbackText(e.target.value)}
            disabled={disabled || isSubmitting}
            maxLength={240}
            rows={4}
            placeholder="Example: 'The summary should focus on my proposed timeline, not just the general idea.'"
            className="correction-signal-form__textarea"
          />
          <div
            className={`correction-signal-form__char-count ${
              remainingChars < 20 ? 'correction-signal-form__char-count--warning' : ''
            }`}
          >
            {remainingChars} characters remaining
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="correction-signal-form__error" role="alert">
            {error}
          </div>
        )}

        {/* Actions */}
        <div className="correction-signal-form__actions">
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              disabled={disabled || isSubmitting}
              className="correction-signal-form__button correction-signal-form__button--cancel"
            >
              Cancel
            </button>
          )}
          <button
            type="submit"
            disabled={!isValid || disabled || isSubmitting}
            className="correction-signal-form__button correction-signal-form__button--submit"
          >
            {isSubmitting ? 'Submitting...' : 'Submit & Regenerate'}
          </button>
        </div>
      </form>

      <div className="correction-signal-form__footer">
        <p className="correction-signal-form__note">
          <strong>Note:</strong> If you reject the final summary, you'll have the option to
          resubmit your input (if time allows in the current round).
        </p>
      </div>
    </div>
  );
};
