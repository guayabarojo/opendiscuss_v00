/**
 * End-to-End Cypress Tests for OpenDiscuss Discussion Protocol
 *
 * Tests complete user journey from discussion creation to final report viewing.
 * Validates:
 * - Discussion creation and start
 * - Countdown timer functionality
 * - Multi-round advancement
 * - Sankey diagram rendering
 *
 * Constitutional Compliance:
 * - Principle I: Parallel input (no replies)
 * - Principle VI: Synchronous deliberation (timing constraints)
 * - Principle VII: Representation via Sankey (no voting)
 *
 * Task: T094 - End-to-end Cypress tests
 */

describe('Complete Discussion Flow', () => {
  const TEST_COMMUNITY_ID = '550e8400-e29b-41d4-a716-446655440000';
  let discussionId: string;

  beforeEach(() => {
    // Reset state and clear storage
    cy.clearLocalStorage();
    cy.clearCookies();

    // Mock authentication (replace with actual auth if needed)
    cy.window().then((win) => {
      win.localStorage.setItem('auth_token', 'test-token-123');
    });

    // Intercept API calls for stability
    cy.intercept('POST', '/api/v1/discussions').as('createDiscussion');
    cy.intercept('POST', '/api/v1/discussions/*/start').as('startDiscussion');
    cy.intercept('GET', '/api/v1/rounds/*/status').as('getRoundStatus');
    cy.intercept('POST', '/api/v1/discussions/*/advance').as('advanceRound');
    cy.intercept('GET', '/api/v1/discussions/*/report').as('getReport');
  });

  describe('User Story 1: Single-Round Discussion', () => {
    it('should create, start, and complete a single-round discussion', () => {
      // Step 1: Navigate to discussion creation page
      cy.visit('/discussions/create');
      cy.url().should('include', '/discussions/create');

      // Step 2: Fill out discussion creation form
      cy.get('[data-testid="community-select"]').select(TEST_COMMUNITY_ID);
      cy.get('[data-testid="total-rounds"]').clear().type('1');

      // Add a single question
      cy.get('[data-testid="question-input-0"]')
        .clear()
        .type('What are the most important features for OpenDiscuss MVP?');

      // Submit form
      cy.get('[data-testid="create-discussion-button"]').click();

      // Wait for API response
      cy.wait('@createDiscussion').then((interception) => {
        expect(interception.response?.statusCode).to.equal(201);
        discussionId = interception.response?.body.discussion_id;
        expect(discussionId).to.be.a('string');
      });

      // Step 3: Verify redirect to live discussion page
      cy.url().should('include', `/discussions/${discussionId}/live`);
      cy.get('[data-testid="discussion-status"]').should('contain', 'Created');

      // Step 4: Start discussion
      cy.get('[data-testid="start-discussion-button"]').click();
      cy.wait('@startDiscussion').its('response.statusCode').should('equal', 200);

      // Step 5: Verify submission window opens
      cy.get('[data-testid="discussion-status"]').should('contain', 'Active');
      cy.get('[data-testid="round-status"]').should('contain', 'Submission Open');

      // Step 6: Verify countdown timer is visible
      cy.get('[data-testid="countdown-timer"]').should('be.visible');
      cy.get('[data-testid="countdown-timer"]').should('match', /[0-5]:[0-5][0-9]/);

      // Step 7: Mock submission and approval (simulated via backend)
      // In real test, would submit via participant UI
      // For E2E, we assume backend sub-protocols handle this

      // Wait for round completion (polling status)
      cy.intercept('GET', `/api/v1/rounds/*/status`, {
        statusCode: 200,
        body: {
          round_id: 'round-uuid',
          status: 'COMPLETE',
          current_time: new Date().toISOString(),
          remaining_time_sec: null,
        },
      }).as('roundComplete');

      // Poll until round complete
      cy.wait('@roundComplete', { timeout: 60000 });

      // Step 8: Verify discussion completed
      cy.get('[data-testid="discussion-status"]').should('contain', 'Completed');

      // Step 9: Navigate to report
      cy.get('[data-testid="view-report-button"]').click();
      cy.url().should('include', `/discussions/${discussionId}/report`);

      // Step 10: Verify Sankey diagram renders
      cy.wait('@getReport').its('response.statusCode').should('equal', 200);
      cy.get('[data-testid="sankey-diagram"]').should('be.visible');

      // Verify single column (Round 1)
      cy.get('[data-testid="sankey-column"]').should('have.length', 1);
      cy.get('[data-testid="sankey-column-0"]').should('contain', 'Round 1');

      // Verify thought spaces exist
      cy.get('[data-testid^="thought-space-"]').should('have.length.at.least', 1);

      // Verify no flows (single round)
      cy.get('[data-testid^="sankey-flow-"]').should('not.exist');
    });
  });

  describe('User Story 2: Multi-Round Discussion with Movement', () => {
    it('should advance through 3 rounds and display participant movement', () => {
      // Step 1: Create 3-round discussion
      cy.visit('/discussions/create');
      cy.get('[data-testid="community-select"]').select(TEST_COMMUNITY_ID);
      cy.get('[data-testid="total-rounds"]').clear().type('3');

      // Add 3 questions
      ['Round 1 question', 'Round 2 question', 'Round 3 question'].forEach((q, i) => {
        if (i > 0) {
          cy.get('[data-testid="add-question-button"]').click();
        }
        cy.get(`[data-testid="question-input-${i}"]`).clear().type(q);
      });

      cy.get('[data-testid="create-discussion-button"]').click();
      cy.wait('@createDiscussion').then((interception) => {
        discussionId = interception.response?.body.discussion_id;
      });

      // Step 2: Start discussion and complete Round 1
      cy.visit(`/discussions/${discussionId}/live`);
      cy.get('[data-testid="start-discussion-button"]').click();
      cy.wait('@startDiscussion');

      // Wait for Round 1 to complete (mocked)
      cy.intercept('GET', `/api/v1/discussions/${discussionId}`, {
        statusCode: 200,
        body: {
          discussion_id: discussionId,
          current_round_num: 1,
          status: 'ACTIVE',
        },
      });

      // Step 3: Advance to Round 2
      cy.get('[data-testid="advance-round-button"]', { timeout: 60000 }).should('be.enabled');
      cy.get('[data-testid="advance-round-button"]').click();

      // Confirm advance
      cy.get('[data-testid="confirm-advance-button"]').click();
      cy.wait('@advanceRound').its('response.statusCode').should('equal', 200);

      // Verify Round 2 started
      cy.get('[data-testid="current-round"]').should('contain', '2');
      cy.get('[data-testid="countdown-timer"]').should('be.visible');

      // Step 4: Wait for Round 2 completion and advance to Round 3
      cy.get('[data-testid="advance-round-button"]', { timeout: 60000 }).should('be.enabled');
      cy.get('[data-testid="advance-round-button"]').click();
      cy.get('[data-testid="confirm-advance-button"]').click();
      cy.wait('@advanceRound');

      // Verify Round 3 started
      cy.get('[data-testid="current-round"]').should('contain', '3');

      // Step 5: Wait for Round 3 completion
      cy.get('[data-testid="view-report-button"]', { timeout: 60000 }).should('be.visible');

      // Step 6: View final report
      cy.get('[data-testid="view-report-button"]').click();
      cy.wait('@getReport');

      // Step 7: Verify multi-column Sankey diagram
      cy.get('[data-testid="sankey-diagram"]').should('be.visible');

      // Should have 3 columns (one per round)
      cy.get('[data-testid="sankey-column"]').should('have.length', 3);

      // Verify columns labeled correctly
      cy.get('[data-testid="sankey-column-0"]').should('contain', 'Round 1');
      cy.get('[data-testid="sankey-column-1"]').should('contain', 'Round 2');
      cy.get('[data-testid="sankey-column-2"]').should('contain', 'Round 3');

      // Step 8: Verify flows between rounds exist
      cy.get('[data-testid^="sankey-flow-"]').should('have.length.at.least', 2);

      // Step 9: Test flow hover interaction
      cy.get('[data-testid^="sankey-flow-"]').first().trigger('mouseover');
      cy.get('[data-testid="flow-tooltip"]').should('be.visible');
      cy.get('[data-testid="flow-tooltip"]').should('contain', 'participants');

      // Step 10: Verify temporal transparency (Constitutional Principle IV)
      // Flow widths should represent actual participant movement
      cy.get('[data-testid="sankey-flow-0"]').should('have.attr', 'data-participant-count');
    });
  });

  describe('Countdown Timer Functionality (Principle VI)', () => {
    it('should display accurate countdown timer during submission window', () => {
      // Create and start discussion
      cy.visit('/discussions/create');
      cy.get('[data-testid="community-select"]').select(TEST_COMMUNITY_ID);
      cy.get('[data-testid="total-rounds"]').clear().type('1');
      cy.get('[data-testid="question-input-0"]').type('Test question');
      cy.get('[data-testid="create-discussion-button"]').click();
      cy.wait('@createDiscussion').then((interception) => {
        discussionId = interception.response?.body.discussion_id;
      });

      cy.visit(`/discussions/${discussionId}/live`);
      cy.get('[data-testid="start-discussion-button"]').click();
      cy.wait('@startDiscussion');

      // Verify timer exists
      cy.get('[data-testid="countdown-timer"]').should('be.visible');

      // Capture initial time
      let initialTime: string;
      cy.get('[data-testid="countdown-timer"]').invoke('text').then((text) => {
        initialTime = text;
        expect(initialTime).to.match(/[0-5]:[0-5][0-9]/);
      });

      // Wait 2 seconds and verify timer decreased
      cy.wait(2000);
      cy.get('[data-testid="countdown-timer"]').invoke('text').should((currentTime) => {
        // Timer should have decreased by ~2 seconds
        const [initialMin, initialSec] = initialTime.split(':').map(Number);
        const [currentMin, currentSec] = currentTime.split(':').map(Number);

        const initialTotal = initialMin * 60 + initialSec;
        const currentTotal = currentMin * 60 + currentSec;

        expect(initialTotal - currentTotal).to.be.within(1, 3);
      });

      // Verify timer visual indicator
      cy.get('[data-testid="timer-progress-bar"]').should('be.visible');
      cy.get('[data-testid="timer-progress-bar"]').should('have.attr', 'aria-valuenow');

      // Verify submission window end time displayed
      cy.get('[data-testid="window-end-time"]').should('be.visible');
    });

    it('should enforce submission window closure (Constitutional Principle VI)', () => {
      // Mock submission window closed state
      cy.intercept('GET', '/api/v1/rounds/*/status', {
        statusCode: 200,
        body: {
          round_id: 'round-uuid',
          status: 'SUBMISSION_CLOSED',
          current_time: new Date().toISOString(),
          remaining_time_sec: 0,
        },
      });

      // Try to submit after window closed
      cy.visit(`/discussions/${discussionId}/live`);
      cy.get('[data-testid="submit-button"]').should('be.disabled');
      cy.get('[data-testid="submission-closed-message"]').should('be.visible');
      cy.get('[data-testid="submission-closed-message"]').should(
        'contain',
        'Submission window has closed'
      );
    });
  });

  describe('Sankey Diagram Rendering', () => {
    it('should render Sankey diagram with correct proportions', () => {
      // Mock report data
      cy.intercept('GET', '/api/v1/discussions/*/report', {
        statusCode: 200,
        body: {
          discussion_id: discussionId,
          sankey_diagram: {
            columns: [
              {
                round_num: 1,
                thought_spaces: [
                  {
                    cluster_id: 'cluster-1',
                    label: 'Thought Space A',
                    member_count: 6,
                    member_pct: 0.6,
                  },
                  {
                    cluster_id: 'cluster-2',
                    label: 'Thought Space B',
                    member_count: 4,
                    member_pct: 0.4,
                  },
                ],
              },
            ],
            flows: [],
          },
          metadata: {
            total_rounds: 1,
            total_participants: 10,
            duration_minutes: 8,
            questions: ['Test question'],
          },
        },
      }).as('mockReport');

      cy.visit(`/discussions/${discussionId}/report`);
      cy.wait('@mockReport');

      // Verify diagram structure
      cy.get('[data-testid="sankey-diagram"]').should('be.visible');
      cy.get('[data-testid="thought-space-cluster-1"]').should('be.visible');
      cy.get('[data-testid="thought-space-cluster-2"]').should('be.visible');

      // Verify thought space labels
      cy.get('[data-testid="thought-space-cluster-1"]').should('contain', 'Thought Space A');
      cy.get('[data-testid="thought-space-cluster-2"]').should('contain', 'Thought Space B');

      // Verify member counts
      cy.get('[data-testid="thought-space-cluster-1"]').should('contain', '6 participants');
      cy.get('[data-testid="thought-space-cluster-2"]').should('contain', '4 participants');

      // Verify proportions (60% vs 40%)
      // Height should reflect member_pct
      cy.get('[data-testid="thought-space-cluster-1"]')
        .invoke('height')
        .then((height1) => {
          cy.get('[data-testid="thought-space-cluster-2"]')
            .invoke('height')
            .then((height2) => {
              const ratio = height1! / height2!;
              expect(ratio).to.be.closeTo(1.5, 0.2); // 60/40 = 1.5
            });
        });
    });

    it('should highlight participant paths on hover', () => {
      // Mock multi-round report with flows
      cy.intercept('GET', '/api/v1/discussions/*/report', {
        statusCode: 200,
        body: {
          discussion_id: discussionId,
          sankey_diagram: {
            columns: [
              {
                round_num: 1,
                thought_spaces: [
                  { cluster_id: 'c1-r1', label: 'Space A', member_count: 5, member_pct: 1.0 },
                ],
              },
              {
                round_num: 2,
                thought_spaces: [
                  { cluster_id: 'c1-r2', label: 'Space B', member_count: 3, member_pct: 1.0 },
                ],
              },
            ],
            flows: [
              {
                flow_id: 'flow-1',
                source_cluster_id: 'c1-r1',
                target_cluster_id: 'c1-r2',
                participant_count: 3,
              },
            ],
          },
          metadata: { total_rounds: 2, total_participants: 5 },
        },
      });

      cy.visit(`/discussions/${discussionId}/report`);

      // Hover over flow
      cy.get('[data-testid="sankey-flow-flow-1"]').trigger('mouseover');

      // Verify highlight
      cy.get('[data-testid="sankey-flow-flow-1"]').should('have.class', 'flow-highlighted');

      // Verify tooltip
      cy.get('[data-testid="flow-tooltip"]').should('be.visible');
      cy.get('[data-testid="flow-tooltip"]').should('contain', '3 participants');
      cy.get('[data-testid="flow-tooltip"]').should('contain', 'Space A → Space B');

      // Remove hover
      cy.get('[data-testid="sankey-flow-flow-1"]').trigger('mouseout');
      cy.get('[data-testid="flow-tooltip"]').should('not.be.visible');
    });
  });

  describe('Error Handling', () => {
    it('should handle API errors gracefully', () => {
      // Mock API error
      cy.intercept('POST', '/api/v1/discussions', {
        statusCode: 500,
        body: {
          error: 'internal_server_error',
          message: 'Database connection failed',
        },
      }).as('createError');

      cy.visit('/discussions/create');
      cy.get('[data-testid="community-select"]').select(TEST_COMMUNITY_ID);
      cy.get('[data-testid="question-input-0"]').type('Test question');
      cy.get('[data-testid="create-discussion-button"]').click();

      cy.wait('@createError');

      // Verify error message displayed
      cy.get('[data-testid="error-message"]').should('be.visible');
      cy.get('[data-testid="error-message"]').should('contain', 'failed');
    });

    it('should handle network errors with retry', () => {
      // Simulate network failure
      cy.intercept('GET', '/api/v1/discussions/*/report', { forceNetworkError: true }).as(
        'networkError'
      );

      cy.visit(`/discussions/${discussionId}/report`);
      cy.wait('@networkError');

      // Verify error boundary
      cy.get('[data-testid="error-boundary"]').should('be.visible');
      cy.get('[data-testid="retry-button"]').should('be.visible');

      // Click retry (mock success)
      cy.intercept('GET', '/api/v1/discussions/*/report', {
        statusCode: 200,
        body: { discussion_id: discussionId, sankey_diagram: { columns: [], flows: [] } },
      });
      cy.get('[data-testid="retry-button"]').click();

      // Verify recovery
      cy.get('[data-testid="sankey-diagram"]').should('be.visible');
    });
  });

  describe('Constitutional Compliance Validation', () => {
    it('should enforce Principle I: Parallel-First (no reply mechanism)', () => {
      cy.visit(`/discussions/${discussionId}/live`);

      // Verify no reply buttons exist
      cy.get('[data-testid="reply-button"]').should('not.exist');
      cy.get('[data-testid="thread-view"]').should('not.exist');

      // Verify submission form is independent
      cy.get('[data-testid="submission-form"]').should('be.visible');
      cy.get('[data-testid="submission-form"]').should('not.contain', 'replying to');
    });

    it('should enforce Principle VII: No voting/ranking mechanisms', () => {
      cy.visit(`/discussions/${discussionId}/report`);

      // Verify no voting UI elements
      cy.get('[data-testid="vote-button"]').should('not.exist');
      cy.get('[data-testid="upvote"]').should('not.exist');
      cy.get('[data-testid="ranking"]').should('not.exist');
      cy.get('[data-testid="winning-idea"]').should('not.exist');

      // Verify Sankey is primary output
      cy.get('[data-testid="sankey-diagram"]').should('be.visible');
      cy.get('[data-testid="sankey-diagram"]').should('be.the.first.descendant');
    });
  });
});

describe('Accessibility Tests', () => {
  it('should be keyboard navigable', () => {
    cy.visit('/discussions/create');

    // Tab through form
    cy.get('body').tab();
    cy.focused().should('have.attr', 'data-testid', 'community-select');

    cy.focused().tab();
    cy.focused().should('have.attr', 'data-testid', 'total-rounds');

    cy.focused().tab();
    cy.focused().should('have.attr', 'data-testid', 'question-input-0');
  });

  it('should have proper ARIA labels', () => {
    cy.visit('/discussions/create');

    cy.get('[data-testid="community-select"]').should('have.attr', 'aria-label');
    cy.get('[data-testid="total-rounds"]').should('have.attr', 'aria-label');
    cy.get('[data-testid="countdown-timer"]').should('have.attr', 'role', 'timer');
  });
});
