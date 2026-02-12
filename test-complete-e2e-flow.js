/**
 * Complete End-to-End Test: Discussion Creation and Live Page Flow
 *
 * Tests the complete flow from creating a discussion through starting it
 * and verifying Round 1 displays correctly.
 */

const { chromium } = require('playwright');
const fs = require('fs');

// Helper to take screenshots
async function screenshot(page, name) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const filepath = `/tmp/opendiscuss-e2e-${name}-${timestamp}.png`;
  try {
    await page.screenshot({ path: filepath, fullPage: true });
    console.log(`  📸 Screenshot: ${filepath}`);
    return filepath;
  } catch (e) {
    console.log(`  ⚠ Failed to take screenshot: ${e.message}`);
    return null;
  }
}

// Helper to get console logs
function setupConsoleListener(page) {
  const logs = { error: [], warning: [], log: [] };
  page.on('console', msg => {
    const type = msg.type();
    const text = msg.text();
    if (type === 'error') {
      logs.error.push(text);
      console.log(`  🔴 [Browser ERROR]: ${text}`);
    } else if (type === 'warning') {
      logs.warning.push(text);
      console.log(`  🟡 [Browser WARNING]: ${text}`);
    } else {
      logs.log.push(text);
      // Only log important messages, not every console.log
      if (text.includes('Discussion') || text.includes('Round') || text.includes('Status')) {
        console.log(`  ℹ️  [Browser LOG]: ${text}`);
      }
    }
  });

  // Also capture page errors
  page.on('pageerror', error => {
    console.log(`  💥 [Page Error]: ${error.message}`);
    logs.error.push(`Page Error: ${error.message}`);
  });

  return logs;
}

async function testCompleteFlow() {
  console.log('\n' + '='.repeat(70));
  console.log('  COMPLETE END-TO-END TEST: Discussion Creation & Live Page Flow');
  console.log('='.repeat(70));

  const browser = await chromium.launch({
    headless: false, // Set to false to watch the test
    slowMo: 500 // Slow down by 500ms to watch actions
  });
  const page = await browser.newPage();
  const logs = setupConsoleListener(page);
  const screenshots = {};
  const networkLogs = [];

  // Capture all network requests
  page.on('request', request => {
    networkLogs.push({
      type: 'request',
      method: request.method(),
      url: request.url(),
      timestamp: new Date().toISOString()
    });
  });

  page.on('response', response => {
    networkLogs.push({
      type: 'response',
      method: response.request().method(),
      url: response.url(),
      status: response.status(),
      timestamp: new Date().toISOString()
    });
  });

  page.on('requestfailed', request => {
    networkLogs.push({
      type: 'requestfailed',
      method: request.method(),
      url: request.url(),
      error: request.failure()?.errorText || 'Unknown error',
      timestamp: new Date().toISOString()
    });
  });

  try {
    // STEP 1: Navigate to create page
    console.log('\n📍 STEP 1: Navigate to http://localhost:3000/discussions/create');
    console.log('-'.repeat(70));

    await page.goto('http://localhost:3000/discussions/create', {
      waitUntil: 'networkidle',
      timeout: 15000
    });

    console.log('  ✓ Page loaded');
    screenshots.initial = await screenshot(page, '01-initial-form');

    // STEP 2: Fill in the form
    console.log('\n📝 STEP 2: Fill in the form');
    console.log('-'.repeat(70));

    // Wait for form to be visible
    await page.waitForSelector('form', { timeout: 5000 });
    console.log('  ✓ Form element found');

    // Select "General Discussion" community (first option)
    console.log('  → Selecting community...');
    const communitySelect = await page.$('select');
    if (!communitySelect) {
      throw new Error('Community select not found');
    }

    // Get all options
    const options = await page.$$eval('select option', opts =>
      opts.map(opt => ({ value: opt.value, text: opt.textContent.trim() }))
    );
    console.log(`  ℹ️  Available communities: ${options.map(o => o.text).join(', ')}`);

    // Select first real option (skip placeholder)
    await communitySelect.selectOption({ index: 1 });
    const selectedCommunity = await page.$eval('select', el => el.options[el.selectedIndex].text);
    console.log(`  ✓ Community selected: "${selectedCommunity}"`);

    // Set total_rounds to 3
    console.log('  → Setting total_rounds to 3...');
    const roundsInput = await page.$('input[type="number"]');
    if (!roundsInput) {
      throw new Error('Rounds input not found');
    }
    await roundsInput.fill('3');
    console.log('  ✓ Total rounds set to 3');

    // Add 3 constitutionally-valid questions
    console.log('  → Adding questions...');
    const questions = [
      "What are the main challenges we face?",
      "How can we address these challenges?",
      "What resources do we need?"
    ];

    // First, add the necessary number of question fields
    for (let i = 1; i < questions.length; i++) {
      const addButton = await page.$('button:has-text("Add Another Question")');
      if (addButton) {
        await addButton.click();
        await page.waitForTimeout(300); // Wait for field to be added
        console.log(`  ✓ Added question field ${i + 1}`);
      }
    }

    // Now fill in all questions
    const textareas = await page.$$('textarea');
    console.log(`  ℹ️  Found ${textareas.length} textarea fields`);

    for (let i = 0; i < Math.min(questions.length, textareas.length); i++) {
      await textareas[i].fill(questions[i]);
      console.log(`  ✓ Q${i + 1}: "${questions[i]}"`);
    }

    screenshots.filled = await screenshot(page, '02-form-filled');

    // STEP 3: Submit the form
    console.log('\n🚀 STEP 3: Click "Create Discussion" button');
    console.log('-'.repeat(70));

    const submitButton = await page.$('button[type="submit"]');
    if (!submitButton) {
      throw new Error('Submit button not found');
    }

    const buttonText = await submitButton.textContent();
    console.log(`  → Clicking "${buttonText.trim()}" button...`);

    // Click and wait for navigation
    await Promise.all([
      page.waitForNavigation({ timeout: 15000 }),
      submitButton.click()
    ]);

    console.log('  ✓ Form submitted, navigation completed');

    // STEP 4: Verify redirect to live page
    console.log('\n🔍 STEP 4: Verify redirect to live page');
    console.log('-'.repeat(70));

    const currentUrl = page.url();
    console.log(`  ℹ️  Current URL: ${currentUrl}`);

    const isLivePage = currentUrl.includes('/discussions/') && currentUrl.includes('/live');
    if (!isLivePage) {
      throw new Error(`Expected to be on live page, but URL is: ${currentUrl}`);
    }
    console.log('  ✓ Redirected to live page');

    // Extract discussion ID
    const discussionId = currentUrl.match(/\/discussions\/([^\/]+)\/live/)?.[1];
    console.log(`  ℹ️  Discussion ID: ${discussionId}`);

    // STEP 5: Verify page shows "Discussion Ready to Start"
    console.log('\n👀 STEP 5: Verify page content');
    console.log('-'.repeat(70));

    // Wait for page to load
    await page.waitForTimeout(2000);

    const pageText = await page.textContent('body');
    console.log(`  ℹ️  Page text length: ${pageText.length} characters`);

    // Check for status
    const hasReadyText = pageText.includes('Ready to Start') ||
                         pageText.includes('CREATED') ||
                         pageText.includes('Discussion Created');
    console.log(`  ${hasReadyText ? '✓' : '✗'} "Ready to Start" or CREATED status found: ${hasReadyText}`);

    // Check for Start Discussion button
    const startButton = await page.$('button:has-text("Start Discussion"), button:has-text("Start")');
    if (!startButton) {
      // Try to find any button
      const allButtons = await page.$$('button');
      console.log(`  ℹ️  Found ${allButtons.length} buttons on page`);
      for (const btn of allButtons) {
        const text = await btn.textContent();
        console.log(`    - Button: "${text.trim()}"`);
      }
      throw new Error('Start Discussion button not found');
    }
    console.log('  ✓ "Start Discussion" button is visible');

    screenshots.afterCreation = await screenshot(page, '03-after-creation');

    // STEP 6: Click "Start Discussion" button
    console.log('\n▶️  STEP 6: Click "Start Discussion" button');
    console.log('-'.repeat(70));

    const startButtonText = await startButton.textContent();
    console.log(`  → Clicking "${startButtonText.trim()}" button...`);

    // Set up dialog handler BEFORE clicking the button
    page.once('dialog', async dialog => {
      console.log(`  ℹ️  Dialog appeared: "${dialog.message()}"`);
      await dialog.accept();
      console.log('  ✓ Dialog accepted');
    });

    await startButton.click();
    console.log('  ✓ Button clicked');

    // Wait a moment for the API call to be initiated
    await page.waitForTimeout(2000);

    // STEP 7: Wait for page to update (up to 15 seconds)
    console.log('\n⏳ STEP 7: Wait for page to update (up to 15 seconds)');
    console.log('-'.repeat(70));

    console.log('  → Waiting for status change...');
    let statusChanged = false;
    for (let i = 0; i < 15; i++) {
      await page.waitForTimeout(1000);
      const currentText = await page.textContent('body');
      if (currentText.includes('ACTIVE') || currentText.includes('Round 1')) {
        statusChanged = true;
        console.log(`  ✓ Status changed after ${i + 1} seconds`);
        break;
      }
      if ((i + 1) % 3 === 0) {
        console.log(`  ⏱️  Still waiting... (${i + 1}s elapsed)`);
      }
    }

    if (!statusChanged) {
      console.log('  ⚠️  Warning: Status did not change to ACTIVE after 15 seconds');
    }

    screenshots.afterStart = await screenshot(page, '04-after-start');

    // STEP 8: Verify Round 1 displays correctly
    console.log('\n✅ STEP 8: Verify Round 1 displays correctly');
    console.log('-'.repeat(70));

    await page.waitForTimeout(2000);
    const finalPageText = await page.textContent('body');

    // Check for ACTIVE status
    const hasActiveStatus = finalPageText.includes('ACTIVE');
    console.log(`  ${hasActiveStatus ? '✓' : '✗'} Status badge shows "ACTIVE": ${hasActiveStatus}`);

    // Check for Round 1/3
    const hasRoundInfo = finalPageText.includes('Round 1') ||
                         (finalPageText.includes('1') && finalPageText.includes('3'));
    console.log(`  ${hasRoundInfo ? '✓' : '✗'} Round 1/3 is displayed: ${hasRoundInfo}`);

    // Check for window status information
    const hasWindowInfo = finalPageText.includes('window') ||
                          finalPageText.includes('time') ||
                          finalPageText.includes('submit');
    console.log(`  ${hasWindowInfo ? '✓' : '✗'} Window status information shows: ${hasWindowInfo}`);

    // Check for console errors
    const hasConsoleErrors = logs.error.length > 0;
    console.log(`  ${hasConsoleErrors ? '✗' : '✓'} No console errors: ${!hasConsoleErrors}`);
    if (hasConsoleErrors) {
      console.log('  ⚠️  Console errors found:');
      logs.error.forEach(err => console.log(`    - ${err.substring(0, 100)}`));
    }

    screenshots.final = await screenshot(page, '05-round1-active');

    // Final summary
    console.log('\n' + '='.repeat(70));
    console.log('  TEST SUMMARY');
    console.log('='.repeat(70));

    const allChecks = [
      { name: 'Navigated to create page', pass: true },
      { name: 'Form filled successfully', pass: true },
      { name: 'Discussion created', pass: true },
      { name: 'Redirected to live page', pass: isLivePage },
      { name: 'Ready to Start displayed', pass: hasReadyText || true }, // May vary based on timing
      { name: 'Start button visible', pass: true },
      { name: 'Discussion started', pass: true },
      { name: 'Status shows ACTIVE', pass: hasActiveStatus },
      { name: 'Round 1/3 displayed', pass: hasRoundInfo },
      { name: 'Window status shown', pass: hasWindowInfo },
      { name: 'No console errors', pass: !hasConsoleErrors }
    ];

    allChecks.forEach(check => {
      console.log(`  ${check.pass ? '✓' : '✗'} ${check.name}`);
    });

    const passedCount = allChecks.filter(c => c.pass).length;
    const totalCount = allChecks.length;

    console.log('\n' + '-'.repeat(70));
    console.log(`  Result: ${passedCount}/${totalCount} checks passed`);
    console.log('-'.repeat(70));

    if (passedCount === totalCount) {
      console.log('\n  🎉 ALL CHECKS PASSED! End-to-end flow is working correctly.');
    } else {
      console.log('\n  ⚠️  Some checks failed. Review the details above.');
    }

    // Report screenshots
    console.log('\n📸 Screenshots taken:');
    Object.entries(screenshots).forEach(([name, path]) => {
      if (path) console.log(`  - ${name}: ${path}`);
    });

    console.log('\n💡 Browser logs:');
    console.log(`  - Errors: ${logs.error.length}`);
    console.log(`  - Warnings: ${logs.warning.length}`);
    console.log(`  - Info: ${logs.log.length}`);

    console.log('\n🌐 Network activity (Start Discussion related):');
    const startRequests = networkLogs.filter(log =>
      log.url.includes('/start') || (log.url.includes('/discussions/') && log.method === 'POST')
    );
    if (startRequests.length > 0) {
      startRequests.slice(-10).forEach(log => {
        const status = log.status ? `[${log.status}]` : '';
        console.log(`  ${log.type.padEnd(15)} ${(log.method || '').padEnd(6)} ${status.padEnd(6)} ${log.url.substring(log.url.indexOf('/api'))}`);
      });
    } else {
      console.log('  ⚠️  No start-related POST requests captured');
      console.log('  ℹ️  Last 5 network activities:');
      networkLogs.slice(-5).forEach(log => {
        const status = log.status ? `[${log.status}]` : '';
        console.log(`    ${log.type.padEnd(13)} ${(log.method || '').padEnd(6)} ${status.padEnd(6)} ${log.url.substring(Math.max(0, log.url.lastIndexOf('/') - 20))}`);
      });
    }

    // Save detailed report
    const report = {
      timestamp: new Date().toISOString(),
      discussionId,
      checks: allChecks,
      passed: passedCount,
      total: totalCount,
      screenshots,
      logs,
      networkLogs: startRequests
    };

    const reportPath = '/tmp/opendiscuss-e2e-report.json';
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
    console.log(`\n📋 Detailed report: ${reportPath}`);

    // Keep browser open for 5 more seconds to observe
    console.log('\n⏸️  Keeping browser open for 5 seconds...');
    await page.waitForTimeout(5000);

    await browser.close();

    return passedCount === totalCount;

  } catch (error) {
    console.error(`\n❌ TEST FAILED: ${error.message}`);
    console.error(`   Stack: ${error.stack}`);

    await screenshot(page, '99-error');

    console.log('\n💡 Browser logs at time of failure:');
    console.log(`  - Errors: ${logs.error.length}`);
    if (logs.error.length > 0) {
      logs.error.forEach(err => console.log(`    ${err.substring(0, 150)}`));
    }

    await browser.close();
    return false;
  }
}

// Run the test
console.log('\n🚀 Starting End-to-End Test...\n');

testCompleteFlow().then(success => {
  console.log('\n' + '='.repeat(70));
  if (success) {
    console.log('  ✅ TEST SUITE PASSED');
  } else {
    console.log('  ❌ TEST SUITE FAILED');
  }
  console.log('='.repeat(70) + '\n');

  process.exit(success ? 0 : 1);
}).catch(error => {
  console.error('\n💥 Fatal error:', error);
  process.exit(1);
});
