import React, { useState } from 'react';

interface TextInputFormProps {
  participantId: string;
  roundId: string;
  onSubmit: (text: string) => Promise<void>;
  disabled?: boolean;
  initialText?: string; // T053-T054: Support loading previous submission text
  remainingSubmissions?: number; // T051: Display remaining count
}

const MAX_CHARS = 5000;

export const TextInputForm: React.FC<TextInputFormProps> = ({
  participantId: _participantId,
  roundId: _roundId,
  onSubmit,
  disabled = false,
  initialText = '',
  remainingSubmissions
}) => {
  const [text, setText] = useState(initialText);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Update text when initialText changes (T053-T054: edit support)
  React.useEffect(() => {
    if (initialText) {
      setText(initialText);
    }
  }, [initialText]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await onSubmit(text);
      setText(''); // Clear form on success
    } catch (err: any) {
      setError(err.response?.data?.detail?.message || 'Submission failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const isValid = text.trim().length > 0 && text.length <= MAX_CHARS;
  const charCount = text.length;
  const remaining = MAX_CHARS - charCount;

  const canSubmit = remainingSubmissions === undefined || remainingSubmissions > 0;

  return (
    <form onSubmit={handleSubmit} className="text-input-form">
      {/* T051: Display remaining submissions */}
      {remainingSubmissions !== undefined && (
        <div className="remaining-submissions">
          <span className={`badge ${canSubmit ? 'badge-info' : 'badge-warning'}`}>
            {remainingSubmissions} submission{remainingSubmissions !== 1 ? 's' : ''} remaining
          </span>
        </div>
      )}

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Enter your response..."
        disabled={disabled || isSubmitting || !canSubmit}
        rows={6}
        className="form-textarea"
      />

      <div className="form-footer">
        <div className={`char-count ${remaining < 100 ? 'warning' : ''}`}>
          {charCount} / {MAX_CHARS} characters
        </div>

        <button
          type="submit"
          disabled={!isValid || disabled || isSubmitting || !canSubmit}
          className="submit-button"
        >
          {isSubmitting ? 'Submitting...' : 'Submit'}
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {!isValid && text.length > 0 && (
        <div className="validation-message">
          {text.trim().length === 0 && 'Text cannot be empty or whitespace only'}
          {text.length > MAX_CHARS && 'Text exceeds maximum length'}
        </div>
      )}

      {/* T052: Rate limit warning */}
      {!canSubmit && (
        <div className="rate-limit-warning">
          ⚠️ You have reached the maximum number of submissions for this round.
        </div>
      )}
    </form>
  );
};
