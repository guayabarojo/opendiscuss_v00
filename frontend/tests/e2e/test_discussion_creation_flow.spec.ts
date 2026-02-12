/**
 * E2E Test: Full Discussion Creation and Live Page Flow
 *
 * Tests the complete user journey:
 * 1. Navigate to /discussions/create
 * 2. Fill form with valid data (community, rounds, constitutional questions)
 * 3. Submit form
 * 4. Verify redirect to /discussions/:id/live
 * 5. Click "Start Discussion" button
 * 6. Verify Round 1 status displays without errors
 * 7. Take screenshots at each step
 *
 * Uses constitutionally valid questions (What/How, no ranking, exploratory)
 */

import { test, expect } from '@playwright/test';

test.describe('Discussion Creation and Live Page Flow', () => {
  test('should create discussion and navigate to live page successfully', async ({ page }) => {
    // Capture console logs and errors
    const consoleLogs: string[] = [];
    const consoleErrors: string[] = [];

    page.on('console', msg => {
      const text = `[${msg.type()}] ${msg.text()}`;
      consoleLogs.push(text);
      if (msg.type() === 'error') {
        consoleErrors.push(text);
        console.error('Browser console error:', text);
      }
    });

    page.on('pageerror', error => {
      consoleErrors.push(error.message);
      console.error('Page error:', error.message);
    });

    // Step 1: Navigate to create page
    console.log('Step 1: Navigating to /discussions/create');
    await page.goto('http://localhost:3000/discussions/create');

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/01-create-page-loaded.png',
      fullPage: true
    });

    // Verify we're on the create page
    await expect(page.locator('.discussion-create-title')).toContainText('Create New Discussion');
    console.log('✓ Create page loaded');

    // Step 2: Fill in the form
    console.log('\nStep 2: Filling in form...');

    // Select community
    await page.selectOption('#community_id', '00000000-0000-0000-0000-000000000001'); // General Discussion
    console.log('✓ Selected "General Discussion" community');

    // Total rounds is already defaulted to 3, but let's verify
    const roundsInput = page.locator('#total_rounds');
    await expect(roundsInput).toHaveValue('3');
    console.log('✓ Total rounds set to 3');

    // Add 3 constitutionally valid questions
    // Question 1 is already in the form by default
    const question1 = page.locator('textarea[name="questions.0.text"]');
    await question1.fill('What perspectives do community members have on local transportation needs?');
    console.log('✓ Added question 1');

    // Add question 2
    await page.click('button:has-text("Add Another Question")');
    const question2 = page.locator('textarea[name="questions.1.text"]');
    await question2.fill('How could we improve communication between different community groups?');
    console.log('✓ Added question 2');

    // Add question 3
    await page.click('button:has-text("Add Another Question")');
    const question3 = page.locator('textarea[name="questions.2.text"]');
    await question3.fill('What approaches might help address environmental concerns in our neighborhood?');
    console.log('✓ Added question 3');

    // Take screenshot of filled form
    await page.screenshot({
      path: 'screenshots/02-form-filled.png',
      fullPage: true
    });

    // Step 3: Submit the form
    console.log('\nStep 3: Submitting form...');
    await page.click('button[type="submit"]:has-text("Create Discussion")');

    // Wait for navigation or error
    try {
      // Wait for either success (navigation) or error message
      await Promise.race([
        page.waitForURL(/\/discussions\/[^/]+\/live/, { timeout: 10000 }),
        page.waitForSelector('.alert-error', { timeout: 10000 }).then(() => {
          throw new Error('Form submission failed with error');
        })
      ]);
    } catch (error) {
      // Take screenshot of error if submission failed
      await page.screenshot({
        path: 'screenshots/03-submission-error.png',
        fullPage: true
      });

      // Check for error messages
      const errorAlert = page.locator('.alert-error');
      if (await errorAlert.isVisible()) {
        const errorText = await errorAlert.textContent();
        console.error('❌ Form submission error:', errorText);
      }

      // Check console logs
      const consoleLogs: string[] = [];
      page.on('console', msg => consoleLogs.push(`${msg.type()}: ${msg.text()}`));
      console.error('Console logs:', consoleLogs);

      throw error;
    }

    // Step 4: Verify redirect to live page
    console.log('\nStep 4: Verifying redirect to live page...');
    await expect(page).toHaveURL(/\/discussions\/[^/]+\/live/);
    const currentUrl = page.url();
    console.log('✓ Redirected to:', currentUrl);

    // Extract discussion ID from URL
    const discussionId = currentUrl.match(/\/discussions\/([^/]+)\/live/)?.[1];
    console.log('✓ Discussion ID:', discussionId);

    // Wait for page content to load
    await page.waitForLoadState('networkidle');

    // Take screenshot
    await page.screenshot({
      path: 'screenshots/04-live-page-loaded.png',
      fullPage: true
    });

    // Verify live page elements
    await expect(page.locator('.discussion-title')).toContainText('Live Discussion');
    console.log('✓ Live page title found');

    // Verify status badge shows CREATED
    const statusBadge = page.locator('.status-badge');
    await expect(statusBadge).toContainText('CREATED');
    console.log('✓ Status shows CREATED');

    // Verify "Not Started" state
    await expect(page.locator('.not-started-section')).toBeVisible();
    console.log('✓ Not started section visible');

    // Step 5: Click "Start Discussion" button
    console.log('\nStep 5: Starting discussion...');

    // Find and verify Start Discussion button exists
    const startButton = page.locator('button:has-text("Start Discussion")');
    await expect(startButton).toBeVisible();
    await expect(startButton).toBeEnabled();

    // Click the button (will trigger confirmation dialog)
    page.once('dialog', async dialog => {
      console.log('✓ Confirmation dialog appeared:', dialog.message());
      await dialog.accept();
    });

    await startButton.click();
    console.log('✓ Clicked Start Discussion button');

    // Wait a bit for the API call to complete and page to update
    await page.waitForTimeout(10000);

    // Take screenshot to see what happened
    await page.screenshot({
      path: 'screenshots/05-after-start-clicked.png',
      fullPage: true
    });

    // Check if there's an error message
    const errorElement = page.locator('.alert-error');
    if (await errorElement.isVisible()) {
      const errorText = await errorElement.textContent();
      console.error('Error message displayed:', errorText);
    }

    // Try to find the status badge again
    const statusAfterStart = page.locator('.status-badge').first();
    const statusText = await statusAfterStart.textContent().catch(() => 'NOT FOUND');
    console.log('Status after start:', statusText);

    // Wait for status to change to ACTIVE (may take up to 10 seconds due to 5s polling interval)
    await page.waitForSelector('.status-badge:has-text("ACTIVE")', { timeout: 10000 }).catch(async (error) => {
      console.error('Status never changed to ACTIVE');
      await page.screenshot({
        path: 'screenshots/debug-status-not-active.png',
        fullPage: true
      });
      throw error;
    });

    // Take screenshot after starting
    await page.screenshot({
      path: 'screenshots/05-discussion-started.png',
      fullPage: true
    });

    // Step 6: Verify Round 1 status without errors
    console.log('\nStep 6: Verifying Round 1 status...');

    // Verify status changed to ACTIVE
    await expect(statusBadge).toContainText('ACTIVE');
    console.log('✓ Status changed to ACTIVE');

    // Verify current round shows 1
    const currentRoundLabel = page.locator('.status-item:has-text("Current Round")');
    await expect(currentRoundLabel).toContainText('1 / 3');
    console.log('✓ Current round shows 1 / 3');

    // Verify Round 1 content section is visible
    const roundSection = page.locator('.current-question-section');
    await expect(roundSection).toBeVisible();
    console.log('✓ Current question section visible');

    // Verify round badge
    const roundBadge = page.locator('.round-badge:has-text("Round 1")');
    await expect(roundBadge).toBeVisible();
    console.log('✓ Round 1 badge visible');

    // Verify window status information is displayed
    const windowStatus = page.locator('.window-status');
    await expect(windowStatus).toBeVisible();
    console.log('✓ Window status visible');

    // Check for window being open
    await expect(windowStatus).toContainText('Window Status:');
    const isOpen = await windowStatus.textContent();
    console.log('  Window status:', isOpen);

    // Verify participant stats are visible
    const participantStats = page.locator('.participant-stats');
    await expect(participantStats).toBeVisible();
    console.log('✓ Participant stats visible');

    // Take final screenshot
    await page.screenshot({
      path: 'screenshots/06-round1-active.png',
      fullPage: true
    });

    // Step 7: Check for errors in console
    console.log('\nStep 7: Checking for errors...');

    const errors: string[] = [];
    page.on('pageerror', error => {
      errors.push(error.message);
    });

    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    // Wait a bit to catch any delayed errors
    await page.waitForTimeout(2000);

    if (errors.length > 0) {
      console.error('❌ Console errors detected:');
      errors.forEach(err => console.error('  -', err));

      // Take error screenshot
      await page.screenshot({
        path: 'screenshots/07-console-errors.png',
        fullPage: true
      });

      throw new Error(`Console errors detected: ${errors.join('; ')}`);
    }

    console.log('✓ No console errors detected');
    console.log('\n✅ All steps completed successfully!');
  });

  test('should handle form validation errors', async ({ page }) => {
    console.log('Testing form validation...');

    await page.goto('http://localhost:3000/discussions/create');
    await page.waitForLoadState('networkidle');

    // Try to submit without selecting community
    await page.click('button[type="submit"]:has-text("Create Discussion")');

    // Should show validation error for community
    const communityError = page.locator('.error-message').first();
    await expect(communityError).toBeVisible({ timeout: 2000 });

    await page.screenshot({
      path: 'screenshots/validation-error-community.png',
      fullPage: true
    });

    console.log('✓ Community validation error displayed correctly');
  });

  test('should handle API errors gracefully', async ({ page }) => {
    console.log('Testing API error handling...');

    await page.goto('http://localhost:3000/discussions/create');
    await page.waitForLoadState('networkidle');

    // Fill in data that will cause backend validation error
    // (Only 1 question but 3 rounds - backend will reject)
    await page.selectOption('#community_id', '00000000-0000-0000-0000-000000000001');
    await page.fill('textarea[name="questions.0.text"]', 'What are your thoughts on community engagement?');
    // Keep total_rounds as 3 (default) but only provide 1 question

    // Submit form
    await page.click('button[type="submit"]:has-text("Create Discussion")');

    // Should show API error about mismatched questions/rounds
    const apiError = page.locator('.alert-error');
    await expect(apiError).toBeVisible({ timeout: 5000 });
    await expect(apiError).toContainText('questions');

    await page.screenshot({
      path: 'screenshots/api-error-displayed.png',
      fullPage: true
    });

    console.log('✓ API error displayed correctly');
  });
});
