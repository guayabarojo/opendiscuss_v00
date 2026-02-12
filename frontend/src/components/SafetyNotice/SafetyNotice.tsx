/**
 * SafetyNotice component for Spec 003 User Story 4 (T071).
 *
 * Displays safety warnings and notifications for:
 * 1. Profanity Neutralization: Warning that inappropriate language was filtered
 * 2. Disallowed Content: Block message that content violated safety guidelines
 *
 * Constitutional Compliance:
 * - Intent Fidelity: Clearly communicates why content was filtered
 * - Representation Not Adjudication: Neutral messaging without judgment
 * - Community-Bounded Context: Safety standards align with community norms
 */

import React from 'react';
import './SafetyNotice.css';

/**
 * Safety flag types from backend SafetyFilterService
 */
type SafetyFlag =
  | 'profanity_neutralized'
  | 'threat_detected'
  | 'ai_moderation_flagged';

export interface SafetyNoticeProps {
  /** List of safety flags from backend */
  safetyFlags: SafetyFlag[];

  /** Summary status (for checking DISALLOWED_CONTENT) */
  summaryStatus?: string;

  /** Optional custom message */
  customMessage?: string;

  /** Variant for styling */
  variant?: 'warning' | 'error' | 'info';
}

/**
 * SafetyNotice component displays safety-related warnings and notifications.
 *
 * Usage:
 * ```tsx
 * // Profanity neutralization warning
 * <SafetyNotice safetyFlags={['profanity_neutralized']} variant="warning" />
 *
 * // Disallowed content block
 * <SafetyNotice
 *   safetyFlags={['threat_detected']}
 *   summaryStatus="disallowed_content"
 *   variant="error"
 * />
 * ```
 */
export const SafetyNotice: React.FC<SafetyNoticeProps> = ({
  safetyFlags,
  summaryStatus,
  customMessage,
  variant = 'warning',
}) => {
  // Don't render if no safety flags
  if (!safetyFlags || safetyFlags.length === 0) {
    return null;
  }

  const hasProfanityNeutralized = safetyFlags.includes('profanity_neutralized');
  const hasThreatDetected = safetyFlags.includes('threat_detected') ||
                            safetyFlags.includes('ai_moderation_flagged');
  const isDisallowedContent = summaryStatus === 'disallowed_content';

  // Determine message and styling based on flags
  let message: string;
  let icon: string;
  let effectiveVariant = variant;

  if (isDisallowedContent || hasThreatDetected) {
    // Threat detected - error message
    effectiveVariant = 'error';
    icon = '🚫';
    message = customMessage ||
      'Your submission contains content that violates community safety guidelines. ' +
      'Please resubmit with appropriate content that focuses on the discussion topic. ' +
      'Submissions must not contain threats, illegal content, or hate speech.';
  } else if (hasProfanityNeutralized) {
    // Profanity neutralized - warning message
    effectiveVariant = 'warning';
    icon = '⚠️';
    message = customMessage ||
      'We detected and removed inappropriate language from your submission. ' +
      'The summary below reflects your core idea without the profanity. ' +
      'If this doesn\'t accurately represent your intent, you can reject and regenerate.';
  } else {
    // Generic safety notice
    effectiveVariant = 'info';
    icon = 'ℹ️';
    message = customMessage ||
      'Your submission was reviewed for safety compliance.';
  }

  return (
    <div className={`safety-notice safety-notice--${effectiveVariant}`} role="alert">
      <div className="safety-notice__icon">{icon}</div>
      <div className="safety-notice__content">
        <h3 className="safety-notice__title">
          {isDisallowedContent ? 'Content Not Allowed' : 'Safety Notice'}
        </h3>
        <p className="safety-notice__message">{message}</p>

        {/* Action button for disallowed content */}
        {isDisallowedContent && (
          <button
            className="safety-notice__action"
            onClick={() => window.location.reload()}
          >
            Return to Discussion
          </button>
        )}
      </div>
    </div>
  );
};

export default SafetyNotice;
