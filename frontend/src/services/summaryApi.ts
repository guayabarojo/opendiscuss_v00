/**
 * Summary API client for Spec 003 Summarization & Approval Protocol.
 *
 * Task T028: API calls for generate, approve, get summary.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface Summary {
  summary_id: string;
  submission_id: string;
  participant_id: string;
  round_id: string;
  summary_text: string;
  status: 'pending_review' | 'approved' | 'rejected' | 'rejected_final' | 'disallowed_content' | 'approval_timeout' | 'superseded';
  regen_count: number;
  safety_flags?: string[] | null;
  created_at: string;  // ISO 8601 timestamp
  approved_at?: string | null;  // ISO 8601 timestamp
}

export interface GenerateSummaryRequest {
  submission_id: string;
  use_fallback_model?: boolean;
}

export interface ApprovalResponse {
  summary_id: string;
  status: string;
  message: string;
  approved_at?: string | null;
}

export interface RejectResponse {
  rejected_summary_id: string;
  rejected_status: string;
  new_summary?: Summary | null;
  message: string;
  needs_correction_signal: boolean;
}

export type ReasonTag =
  | 'wrong_crux'
  | 'too_vague'
  | 'misrepresents_me'
  | 'missed_constraint'
  | 'missed_solution'
  | 'other';

export interface CorrectionSignalRequest {
  reason_tag: ReasonTag;
  feedback_text?: string;
}

export interface CorrectionSignalResponse {
  signal_id: string;
  summary_id: string;
  reason_tag: string;
  feedback_text?: string | null;
  created_at: string;
  new_summary_id: string;
  new_summary_text: string;
  regen_count: number;
  message: string;
}

/**
 * Generate summary from submission.
 *
 * POST /api/v1/summaries/generate
 *
 * @param request - Generation request with submission_id
 * @returns Created summary with status=PENDING_REVIEW
 * @throws Error if generation fails
 */
export async function generateSummary(
  request: GenerateSummaryRequest
): Promise<Summary> {
  const response = await fetch(`${API_BASE_URL}/api/v1/summaries/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to generate summary');
  }

  return response.json();
}

/**
 * Approve a summary.
 *
 * POST /api/v1/summaries/{summary_id}/approve
 *
 * @param summaryId - UUID of summary to approve
 * @returns Approval response with updated status
 * @throws Error if approval fails
 */
export async function approveSummary(summaryId: string): Promise<ApprovalResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/summaries/${summaryId}/approve`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to approve summary');
  }

  return response.json();
}

/**
 * Reject a summary and automatically regenerate (User Story 2, Task T042).
 *
 * POST /api/v1/summaries/{summary_id}/reject
 *
 * Workflow:
 * - If regen_count < 2: Returns new summary automatically generated
 * - If regen_count >= 2: Returns needs_correction_signal=true
 *
 * @param summaryId - UUID of summary to reject
 * @returns Rejection response with optional new summary
 * @throws Error if rejection fails
 */
export async function rejectSummary(summaryId: string): Promise<RejectResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/summaries/${summaryId}/reject`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to reject summary');
  }

  return response.json();
}

/**
 * Get summary by ID.
 *
 * GET /api/v1/summaries/{summary_id}
 *
 * @param summaryId - UUID of summary to retrieve
 * @returns Summary details
 * @throws Error if summary not found or request fails
 */
export async function getSummary(summaryId: string): Promise<Summary> {
  const response = await fetch(`${API_BASE_URL}/api/v1/summaries/${summaryId}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to get summary');
  }

  return response.json();
}

/**
 * Get all summaries for a submission (including regenerations).
 *
 * GET /api/v1/summaries/submission/{submission_id}
 *
 * @param submissionId - UUID of submission
 * @returns List of summaries for submission
 * @throws Error if request fails
 */
export async function getSummariesForSubmission(
  submissionId: string
): Promise<Summary[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/summaries/submission/${submissionId}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to get summaries');
  }

  return response.json();
}

/**
 * Get all summaries for a participant in a round (T083-T084).
 *
 * Supports User Story 5 - Multiple Submissions with Last-Approved-Wins.
 * Returns summaries ordered by approved_at DESC (latest first).
 *
 * GET /api/v1/summaries/participant/{participant_id}/round/{round_id}
 *
 * @param participantId - UUID of participant
 * @param roundId - UUID of round
 * @returns List of summaries for participant in round
 * @throws Error if request fails
 */
export async function getSummariesForParticipantRound(
  participantId: string,
  roundId: string
): Promise<Summary[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/summaries/participant/${participantId}/round/${roundId}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to get summaries for participant');
  }

  return response.json();
}

/**
 * Submit correction signal and trigger final regeneration (User Story 3, Task T057).
 *
 * POST /api/v1/summaries/{summary_id}/correction
 *
 * Should only be called after 2 rejections (regen_count=2).
 * Triggers final regeneration attempt (regen_count=3) using correction signal.
 *
 * @param summaryId - UUID of rejected summary (must have regen_count=2)
 * @param request - Correction signal with reason_tag and optional feedback_text
 * @returns Correction signal response with new summary
 * @throws Error if submission fails or summary not eligible for correction
 */
export async function submitCorrectionSignal(
  summaryId: string,
  request: CorrectionSignalRequest
): Promise<CorrectionSignalResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/summaries/${summaryId}/correction`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to submit correction signal');
  }

  return response.json();
}
