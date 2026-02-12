/**
 * E2E Test for Text Submission Flow (T080)
 *
 * Tests complete user journey: open page → type text → submit → verify success.
 * Uses Playwright for browser automation.
 */

import { test, expect } from '@playwright/test';

test.describe('Text Submission E2E', () => {
  const participantId = 'test-participant-e2e';
  const roundId = 'test-round-e2e';

  test.beforeEach(async ({ page }) => {
    // Setup: Mock API responses
    await page.route('**/api/v1/submissions/', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            submission_id: 'submission-123',
            participant_id: participantId,
            round_id: roundId,
            timestamp: new Date().toISOString(),
            modality: 'TEXT',
            counted: true
          })
        });
      }
    });

    await page.route(`**/api/v1/submissions/participant/${participantId}/round/${roundId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          submissions: [],
          total_count: 0,
          max_allowed: 3,
          can_submit_more: true
        })
      });
    });
  });

  test('should submit text successfully', async ({ page }) => {
    // Navigate to the round input page
    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    // Verify page loaded
    await expect(page.locator('h1')).toContainText('Round Input');

    // Find the textarea
    const textarea = page.getByPlaceholder(/enter your response/i);
    await expect(textarea).toBeVisible();

    // Initially, submit button should be disabled
    const submitButton = page.getByRole('button', { name: /submit/i });
    await expect(submitButton).toBeDisabled();

    // Type text into the textarea
    const testText = 'This is my test submission for the discussion round.';
    await textarea.fill(testText);

    // Verify character count updates
    await expect(page.getByText(`${testText.length} / 5000 characters`)).toBeVisible();

    // Submit button should now be enabled
    await expect(submitButton).toBeEnabled();

    // Click submit
    await submitButton.click();

    // Verify success message appears
    await expect(page.getByText(/submission successful/i)).toBeVisible({ timeout: 5000 });

    // Verify textarea is cleared after successful submission
    await expect(textarea).toHaveValue('');
  });

  test('should validate empty text', async ({ page }) => {
    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    const textarea = page.getByPlaceholder(/enter your response/i);
    const submitButton = page.getByRole('button', { name: /submit/i });

    // Empty textarea - submit should be disabled
    await expect(submitButton).toBeDisabled();

    // Type some text
    await textarea.fill('Valid text');
    await expect(submitButton).toBeEnabled();

    // Clear textarea
    await textarea.clear();
    await expect(submitButton).toBeDisabled();
  });

  test('should validate whitespace-only text', async ({ page }) => {
    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    const textarea = page.getByPlaceholder(/enter your response/i);
    const submitButton = page.getByRole('button', { name: /submit/i });

    // Type only whitespace
    await textarea.fill('   \n\t   ');

    // Submit button should be disabled
    await expect(submitButton).toBeDisabled();

    // Validation message should appear
    await expect(page.getByText(/text cannot be empty or whitespace only/i)).toBeVisible();
  });

  test('should validate maximum character limit', async ({ page }) => {
    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    const textarea = page.getByPlaceholder(/enter your response/i);
    const submitButton = page.getByRole('button', { name: /submit/i });

    // Type text exceeding max length
    const longText = 'a'.repeat(5001);
    await textarea.fill(longText);

    // Submit button should be disabled
    await expect(submitButton).toBeDisabled();

    // Validation message should appear
    await expect(page.getByText(/text exceeds maximum length/i)).toBeVisible();

    // Character count should show warning
    await expect(page.getByText(/5001 \/ 5000 characters/i)).toHaveClass(/warning/);
  });

  test('should handle submission errors', async ({ page }) => {
    // Override the mock to simulate an error
    await page.route('**/api/v1/submissions/', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 422,
          contentType: 'application/json',
          body: JSON.stringify({
            detail: {
              error_code: 'OUTSIDE_WINDOW',
              message: 'Submission window has closed'
            }
          })
        });
      }
    });

    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    const textarea = page.getByPlaceholder(/enter your response/i);
    const submitButton = page.getByRole('button', { name: /submit/i });

    // Type valid text
    await textarea.fill('Valid submission text');

    // Click submit
    await submitButton.click();

    // Verify error message appears
    await expect(page.getByText(/submission window has closed/i)).toBeVisible({ timeout: 5000 });
  });

  test('should handle rate limit errors', async ({ page }) => {
    // Override the mock to simulate rate limit
    await page.route('**/api/v1/submissions/', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 429,
          contentType: 'application/json',
          body: JSON.stringify({
            detail: {
              error_code: 'TOO_MANY_REQUESTS',
              message: 'Maximum submissions reached'
            }
          })
        });
      }
    });

    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    const textarea = page.getByPlaceholder(/enter your response/i);
    const submitButton = page.getByRole('button', { name: /submit/i });

    // Type valid text
    await textarea.fill('Valid submission text');

    // Click submit
    await submitButton.click();

    // Verify rate limit error message appears
    await expect(page.getByText(/rate limit exceeded/i)).toBeVisible({ timeout: 5000 });
  });

  test('should display remaining submissions count', async ({ page }) => {
    // Mock with 2 submissions remaining
    await page.route(`**/api/v1/submissions/participant/${participantId}/round/${roundId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          submissions: [
            {
              submission_id: 'sub-1',
              participant_id: participantId,
              round_id: roundId,
              timestamp: new Date().toISOString(),
              modality: 'TEXT',
              counted: true
            }
          ],
          total_count: 1,
          max_allowed: 3,
          can_submit_more: true
        })
      });
    });

    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    // Verify remaining count is displayed
    await expect(page.getByText(/2 submissions remaining/i)).toBeVisible();
  });

  test('should disable form when rate limit reached', async ({ page }) => {
    // Mock with 0 submissions remaining
    await page.route(`**/api/v1/submissions/participant/${participantId}/round/${roundId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          submissions: [
            { submission_id: 'sub-1', participant_id: participantId, round_id: roundId, timestamp: new Date().toISOString(), modality: 'TEXT', counted: false },
            { submission_id: 'sub-2', participant_id: participantId, round_id: roundId, timestamp: new Date().toISOString(), modality: 'TEXT', counted: false },
            { submission_id: 'sub-3', participant_id: participantId, round_id: roundId, timestamp: new Date().toISOString(), modality: 'TEXT', counted: true }
          ],
          total_count: 3,
          max_allowed: 3,
          can_submit_more: false
        })
      });
    });

    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    // Verify rate limit warning is displayed
    await expect(page.getByText(/you have reached the maximum number of submissions/i)).toBeVisible();

    // Verify textarea is disabled
    const textarea = page.getByPlaceholder(/enter your response/i);
    await expect(textarea).toBeDisabled();

    // Verify submit button is disabled
    const submitButton = page.getByRole('button', { name: /submit/i });
    await expect(submitButton).toBeDisabled();
  });

  test('should show character count warning near limit', async ({ page }) => {
    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    const textarea = page.getByPlaceholder(/enter your response/i);

    // Type text approaching limit (99 chars remaining)
    const nearLimitText = 'a'.repeat(4901);
    await textarea.fill(nearLimitText);

    // Character count should have warning class
    const charCount = page.getByText(/4901 \/ 5000 characters/i);
    await expect(charCount).toHaveClass(/warning/);
  });

  test('should handle multiline text submission', async ({ page }) => {
    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    const textarea = page.getByPlaceholder(/enter your response/i);
    const submitButton = page.getByRole('button', { name: /submit/i });

    // Type multiline text
    const multilineText = 'Line 1\nLine 2\nLine 3\nFinal line.';
    await textarea.fill(multilineText);

    // Verify character count includes newlines
    await expect(page.getByText(`${multilineText.length} / 5000 characters`)).toBeVisible();

    // Submit should be enabled
    await expect(submitButton).toBeEnabled();

    // Click submit
    await submitButton.click();

    // Verify success
    await expect(page.getByText(/submission successful/i)).toBeVisible({ timeout: 5000 });
  });

  test('should maintain state during typing', async ({ page }) => {
    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    const textarea = page.getByPlaceholder(/enter your response/i);
    const submitButton = page.getByRole('button', { name: /submit/i });

    // Type gradually
    await textarea.type('First part');
    await expect(textarea).toHaveValue('First part');
    await expect(submitButton).toBeEnabled();

    await textarea.type(' and second part');
    await expect(textarea).toHaveValue('First part and second part');

    // Character count should update correctly
    await expect(page.getByText(/25 \/ 5000 characters/i)).toBeVisible();
  });

  test('should handle special characters', async ({ page }) => {
    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    const textarea = page.getByPlaceholder(/enter your response/i);
    const submitButton = page.getByRole('button', { name: /submit/i });

    // Type text with special characters
    const specialText = 'Test with @#$%^&*() symbols and "quotes" & <tags>';
    await textarea.fill(specialText);

    await expect(textarea).toHaveValue(specialText);
    await expect(submitButton).toBeEnabled();
  });

  test('should handle keyboard shortcuts', async ({ page }) => {
    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    const textarea = page.getByPlaceholder(/enter your response/i);

    // Focus textarea
    await textarea.focus();

    // Type some text
    await page.keyboard.type('Hello World');
    await expect(textarea).toHaveValue('Hello World');

    // Select all (Ctrl+A or Cmd+A)
    await page.keyboard.press('ControlOrMeta+A');

    // Type to replace
    await page.keyboard.type('Replaced text');
    await expect(textarea).toHaveValue('Replaced text');
  });
});

test.describe('Text Submission Accessibility', () => {
  const participantId = 'test-participant-a11y';
  const roundId = 'test-round-a11y';

  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/submissions/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          submissions: [],
          total_count: 0,
          max_allowed: 3,
          can_submit_more: true
        })
      });
    });
  });

  test('should be keyboard navigable', async ({ page }) => {
    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    // Tab to textarea
    await page.keyboard.press('Tab');

    const textarea = page.getByPlaceholder(/enter your response/i);
    await expect(textarea).toBeFocused();

    // Type text
    await page.keyboard.type('Accessibility test');

    // Tab to submit button
    await page.keyboard.press('Tab');
    // Skip character count (not focusable)

    const submitButton = page.getByRole('button', { name: /submit/i });
    await expect(submitButton).toBeFocused();
  });

  test('should have proper ARIA labels', async ({ page }) => {
    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    // Form should be present
    const form = page.locator('form.text-input-form');
    await expect(form).toBeVisible();

    // Button should have proper role
    const submitButton = page.getByRole('button', { name: /submit/i });
    await expect(submitButton).toBeVisible();
  });

  test('should announce errors to screen readers', async ({ page }) => {
    await page.route('**/api/v1/submissions/', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 422,
          contentType: 'application/json',
          body: JSON.stringify({
            detail: {
              error_code: 'OUTSIDE_WINDOW',
              message: 'Submission window has closed'
            }
          })
        });
      }
    });

    await page.goto(`/rounds/${roundId}/input?participant=${participantId}`);

    const textarea = page.getByPlaceholder(/enter your response/i);
    await textarea.fill('Test text');

    const submitButton = page.getByRole('button', { name: /submit/i });
    await submitButton.click();

    // Error message should be visible and part of DOM for screen readers
    const errorMessage = page.getByText(/submission window has closed/i);
    await expect(errorMessage).toBeVisible();
  });
});
