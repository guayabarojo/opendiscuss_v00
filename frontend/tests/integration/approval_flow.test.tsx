/**
 * Frontend Integration Tests: Approval Flow
 *
 * Tests end-to-end approval workflow in the React UI.
 *
 * Spec Reference: Spec 003 - Summarization & Approval Protocol (T109)
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { rest } from 'msw';
import { setupServer } from 'msw/node';
import ApprovalInterface from '../../src/pages/ApprovalInterface/ApprovalInterface';
import SummaryReview from '../../src/components/SummaryReview/SummaryReview';

// Mock API server
const server = setupServer(
  // Mock GET /summaries/{id}
  rest.get('/api/v1/summaries/:summaryId', (req, res, ctx) => {
    return res(
      ctx.json({
        summary_id: '123e4567-e89b-12d3-a456-426614174000',
        submission_id: '123e4567-e89b-12d3-a456-426614174001',
        participant_id: '123e4567-e89b-12d3-a456-426614174002',
        round_id: '123e4567-e89b-12d3-a456-426614174003',
        summary_text: 'We should invest in renewable energy infrastructure.',
        status: 'pending_review',
        regen_count: 0,
        safety_flags: [],
        created_at: '2026-02-01T12:00:00Z',
        approved_at: null,
      })
    );
  }),

  // Mock POST /summaries/{id}/approve
  rest.post('/api/v1/summaries/:summaryId/approve', (req, res, ctx) => {
    return res(
      ctx.json({
        summary_id: '123e4567-e89b-12d3-a456-426614174000',
        status: 'approved',
        message: 'Summary approved successfully',
        approved_at: '2026-02-01T12:05:00Z',
      })
    );
  }),

  // Mock POST /summaries/{id}/reject
  rest.post('/api/v1/summaries/:summaryId/reject', (req, res, ctx) => {
    return res(
      ctx.json({
        rejected_summary_id: '123e4567-e89b-12d3-a456-426614174000',
        rejected_status: 'rejected',
        new_summary: {
          summary_id: '123e4567-e89b-12d3-a456-426614174004',
          submission_id: '123e4567-e89b-12d3-a456-426614174001',
          participant_id: '123e4567-e89b-12d3-a456-426614174002',
          round_id: '123e4567-e89b-12d3-a456-426614174003',
          summary_text: 'Renewable energy investment is crucial for climate goals.',
          status: 'pending_review',
          regen_count: 1,
          safety_flags: [],
          created_at: '2026-02-01T12:01:00Z',
          approved_at: null,
        },
        message: 'Summary rejected. New summary generated (Attempt 2/3).',
        needs_correction_signal: false,
      })
    );
  })
);

// Enable API mocking
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('Approval Flow Integration Tests', () => {
  test('renders summary for approval', async () => {
    render(<SummaryReview summaryId="123e4567-e89b-12d3-a456-426614174000" />);

    // Wait for summary to load
    await waitFor(() => {
      expect(screen.getByText(/renewable energy infrastructure/i)).toBeInTheDocument();
    });

    // Check approve and reject buttons exist
    expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reject/i })).toBeInTheDocument();
  });

  test('approves summary successfully', async () => {
    render(<SummaryReview summaryId="123e4567-e89b-12d3-a456-426614174000" />);

    // Wait for summary to load
    await waitFor(() => {
      expect(screen.getByText(/renewable energy infrastructure/i)).toBeInTheDocument();
    });

    // Click approve button
    const approveButton = screen.getByRole('button', { name: /approve/i });
    fireEvent.click(approveButton);

    // Wait for success message
    await waitFor(() => {
      expect(screen.getByText(/approved successfully/i)).toBeInTheDocument();
    });
  });

  test('rejects summary and shows regenerated version', async () => {
    render(<SummaryReview summaryId="123e4567-e89b-12d3-a456-426614174000" />);

    // Wait for summary to load
    await waitFor(() => {
      expect(screen.getByText(/renewable energy infrastructure/i)).toBeInTheDocument();
    });

    // Click reject button
    const rejectButton = screen.getByRole('button', { name: /reject/i });
    fireEvent.click(rejectButton);

    // Wait for new summary to appear
    await waitFor(() => {
      expect(screen.getByText(/Renewable energy investment is crucial/i)).toBeInTheDocument();
      expect(screen.getByText(/Attempt 2\/3/i)).toBeInTheDocument();
    });
  });

  test('shows correction signal form after 2 rejections', async () => {
    // Mock response for 2nd rejection
    server.use(
      rest.post('/api/v1/summaries/:summaryId/reject', (req, res, ctx) => {
        return res(
          ctx.json({
            rejected_summary_id: '123e4567-e89b-12d3-a456-426614174004',
            rejected_status: 'rejected',
            new_summary: null,
            message: 'Summary rejected (Attempt 3/3). Please provide correction signal to regenerate once more.',
            needs_correction_signal: true,
          })
        );
      })
    );

    render(<SummaryReview summaryId="123e4567-e89b-12d3-a456-426614174004" />);

    // Wait for summary to load
    await waitFor(() => {
      expect(screen.getByText(/Renewable energy investment/i)).toBeInTheDocument();
    });

    // Click reject button
    const rejectButton = screen.getByRole('button', { name: /reject/i });
    fireEvent.click(rejectButton);

    // Wait for correction signal form to appear
    await waitFor(() => {
      expect(screen.getByText(/correction signal/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/reason/i)).toBeInTheDocument();
    });
  });

  test('displays safety flags if present', async () => {
    server.use(
      rest.get('/api/v1/summaries/:summaryId', (req, res, ctx) => {
        return res(
          ctx.json({
            summary_id: '123e4567-e89b-12d3-a456-426614174000',
            submission_id: '123e4567-e89b-12d3-a456-426614174001',
            participant_id: '123e4567-e89b-12d3-a456-426614174002',
            round_id: '123e4567-e89b-12d3-a456-426614174003',
            summary_text: 'Policy needs improvement.',
            status: 'pending_review',
            regen_count: 0,
            safety_flags: ['profanity_neutralized'],
            created_at: '2026-02-01T12:00:00Z',
            approved_at: null,
          })
        );
      })
    );

    render(<SummaryReview summaryId="123e4567-e89b-12d3-a456-426614174000" />);

    // Wait for summary and safety notice
    await waitFor(() => {
      expect(screen.getByText(/profanity/i)).toBeInTheDocument();
    });
  });

  test('shows last-approved indicator for multiple submissions', async () => {
    // Mock multiple summaries
    server.use(
      rest.get('/api/v1/summaries/participant/:participantId/round/:roundId', (req, res, ctx) => {
        return res(
          ctx.json([
            {
              summary_id: '123e4567-e89b-12d3-a456-426614174005',
              summary_text: 'First submission.',
              status: 'approved',
              approved_at: '2026-02-01T12:00:00Z',
              regen_count: 0,
            },
            {
              summary_id: '123e4567-e89b-12d3-a456-426614174006',
              summary_text: 'Second submission.',
              status: 'approved',
              approved_at: '2026-02-01T12:10:00Z',
              regen_count: 0,
            },
          ])
        );
      })
    );

    render(
      <ApprovalInterface
        participantId="123e4567-e89b-12d3-a456-426614174002"
        roundId="123e4567-e89b-12d3-a456-426614174003"
      />
    );

    // Wait for summaries to load
    await waitFor(() => {
      expect(screen.getByText(/Second submission/i)).toBeInTheDocument();
      expect(screen.getByText(/Latest Approved/i)).toBeInTheDocument();
    });
  });
});

describe('Approval Interface Error Handling', () => {
  test('displays error message on API failure', async () => {
    server.use(
      rest.get('/api/v1/summaries/:summaryId', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ detail: 'Internal server error' }));
      })
    );

    render(<SummaryReview summaryId="123e4567-e89b-12d3-a456-426614174000" />);

    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });
  });

  test('disables buttons during loading', async () => {
    render(<SummaryReview summaryId="123e4567-e89b-12d3-a456-426614174000" />);

    // Initially buttons should be disabled
    const approveButton = screen.queryByRole('button', { name: /approve/i });
    if (approveButton) {
      expect(approveButton).toBeDisabled();
    }

    // Wait for loading to complete
    await waitFor(() => {
      const loadedApproveButton = screen.getByRole('button', { name: /approve/i });
      expect(loadedApproveButton).not.toBeDisabled();
    });
  });
});
