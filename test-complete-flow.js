/**
 * Complete Application Test Suite
 * Tests the full OpenDiscuss application flow including form submission
 * Tests both success and failure cases
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

// Helper to take screenshots
async function screenshot(page, name) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const filepath = `/tmp/opendiscuss-${name}-${timestamp}.png`;
  try {
    await page.screenshot({ path: filepath, fullPage: true });
    console.log(`  📸 Screenshot: ${filepath}`);
    return filepath;
  } catch (e) {
    console.log(`  ⚠ Failed to take screenshot: ${e.message}`);
  }
}

// Helper to get console logs
function setupConsoleListener(page) {
  const logs = { error: [], warning: [], log: [] };
  page.on('console', msg => {
    const type = msg.type();
    if (type === 'error') logs.error.push(msg.text());
    else if (type === 'warning') logs.warning.push(msg.text());
    else logs.log.push(msg.text());
    console.log(`  [Browser ${type.toUpperCase()}]: ${msg.text()}`);
  });
  return logs;
}

async function testHomePageLoad() {
  console.log('\n' + '='.repeat(60));
  console.log('TEST 1: Load Homepage');
  console.log('='.repeat(60));

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const logs = setupConsoleListener(page);

  try {
    console.log('  → Navigating to http://localhost:3000');
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle', timeout: 15000 });

    const title = await page.title();
    console.log(`  ✓ Page title: "${title}"`);

    // Check for main content
    const headings = await page.$$eval('h1, h2', els => els.map(e => e.textContent.trim()).slice(0, 3));
    console.log(`  ✓ Page headings: ${headings.join(', ')}`);

    // Look for Create Discussion link
    const createLink = await page.$('a, button, [role="button"]');
    if (createLink) {
      const text = await createLink.textContent();
      console.log(`  ✓ Found interactive element: "${text.trim()}"`);
    }

    await screenshot(page, 'home-loaded');
    await browser.close();

    return {
      test: 'Home Page Load',
      success: true,
      title,
      headings,
      logs
    };
  } catch (error) {
    console.error(`  ✗ Test failed: ${error.message}`);
    await screenshot(page, 'home-error');
    await browser.close();
    return {
      test: 'Home Page Load',
      success: false,
      error: error.message,
      logs
    };
  }
}

async function testCreateDiscussionPage() {
  console.log('\n' + '='.repeat(60));
  console.log('TEST 2: Navigate to Create Discussion');
  console.log('='.repeat(60));

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const logs = setupConsoleListener(page);

  try {
    console.log('  → Navigating to /discussions/create');
    await page.goto('http://localhost:3000/discussions/create', {
      waitUntil: 'networkidle',
      timeout: 15000
    });

    await screenshot(page, 'create-page');

    // Check for form
    const form = await page.$('form');
    if (form) {
      console.log('  ✓ Form element found');
    }

    // Check for key form fields
    const communitySelect = await page.$('select, input[id*="community"]');
    const roundsInput = await page.$('input[type="number"], input[id*="round"]');
    const questionInputs = await page.$$('input[type="text"], textarea');

    if (communitySelect) console.log('  ✓ Community selector found');
    if (roundsInput) console.log('  ✓ Rounds input found');
    console.log(`  ✓ Question inputs found: ${questionInputs.length} input fields`);

    await browser.close();

    return {
      test: 'Create Discussion Page',
      success: true,
      hasForm: !!form,
      hasCommunitySelect: !!communitySelect,
      hasRoundsInput: !!roundsInput,
      questionInputCount: questionInputs.length,
      logs
    };
  } catch (error) {
    console.error(`  ✗ Test failed: ${error.message}`);
    await screenshot(page, 'create-error');
    await browser.close();
    return {
      test: 'Create Discussion Page',
      success: false,
      error: error.message,
      logs
    };
  }
}

async function testSuccessfulSubmission() {
  console.log('\n' + '='.repeat(60));
  console.log('TEST 3: Submit Valid Discussion Form (SUCCESS CASE)');
  console.log('='.repeat(60));
  console.log('  Questions (no ranking keywords):');
  console.log('    Q1: "What are the main challenges we face?"');
  console.log('    Q2: "How can we address these challenges?"');
  console.log('    Q3: "What resources do we need?"');

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const logs = setupConsoleListener(page);
  const networkRequests = [];

  page.on('response', response => {
    networkRequests.push({
      url: response.url(),
      status: response.status(),
      method: response.request().method()
    });
  });

  try {
    console.log('  → Navigating to /discussions/create');
    await page.goto('http://localhost:3000/discussions/create', {
      waitUntil: 'networkidle',
      timeout: 15000
    });

    await screenshot(page, 'success-form-initial');

    // Find community selector and select first option
    console.log('  → Selecting community...');
    const communitySelect = await page.$('select');
    if (communitySelect) {
      await communitySelect.selectOption({ index: 1 }); // Select first available
      console.log('  ✓ Community selected');
    }

    // Set total_rounds to 3
    console.log('  → Setting total_rounds to 3...');
    const roundsInputs = await page.$$('input[type="number"]');
    if (roundsInputs.length > 0) {
      await roundsInputs[0].fill('3');
      console.log('  ✓ Rounds set to 3');
    }

    // Add questions
    const questions = [
      "What are the main challenges we face?",
      "How can we address these challenges?",
      "What resources do we need?"
    ];

    console.log('  → Filling in questions...');
    const textareas = await page.$$('textarea');
    for (let i = 0; i < Math.min(questions.length, textareas.length); i++) {
      await textareas[i].fill(questions[i]);
      console.log(`  ✓ Q${i + 1}: "${questions[i]}"`);
    }

    await screenshot(page, 'success-form-filled');

    // Submit form
    console.log('  → Submitting form...');
    const submitButton = await page.$('button[type="submit"]');
    if (submitButton) {
      await submitButton.click();
      console.log('  ✓ Submit button clicked');
    }

    // Wait for navigation or response
    await page.waitForNavigation({ timeout: 10000 }).catch(() => {
      console.log('  ⚠ No navigation detected, checking page state...');
    });

    await screenshot(page, 'success-after-submit');

    // Check for white screen
    const bodyText = await page.textContent('body');
    const hasContent = bodyText && bodyText.trim().length > 0;
    console.log(`  ✓ Page has content after submission: ${hasContent}`);

    // Check current URL
    const currentUrl = page.url();
    console.log(`  ✓ Current URL: ${currentUrl}`);

    // Check for errors
    const errorElements = await page.$$('.error, .alert-danger, [role="alert"]');
    if (errorElements.length > 0) {
      const errorTexts = await Promise.all(
        errorElements.map(el => el.textContent())
      );
      console.log(`  ! Errors found: ${errorTexts.join(', ')}`);
    } else {
      console.log('  ✓ No error elements found');
    }

    await browser.close();

    return {
      test: 'Successful Submission',
      success: hasContent && !currentUrl.includes('create'),
      hasContent,
      currentUrl,
      errorCount: errorElements.length,
      networkRequests,
      logs
    };
  } catch (error) {
    console.error(`  ✗ Test failed: ${error.message}`);
    await screenshot(page, 'success-error');
    await browser.close();
    return {
      test: 'Successful Submission',
      success: false,
      error: error.message,
      networkRequests,
      logs
    };
  }
}

async function testRankingKeywordValidation() {
  console.log('\n' + '='.repeat(60));
  console.log('TEST 4: Test Ranking Keyword Validation (FAILURE CASE)');
  console.log('='.repeat(60));
  console.log('  Testing with ranking keyword: "What is your favorite challenge?"');
  console.log('  Expected: Form validation error preventing submission');

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const logs = setupConsoleListener(page);

  try {
    console.log('  → Navigating to /discussions/create');
    await page.goto('http://localhost:3000/discussions/create', {
      waitUntil: 'networkidle',
      timeout: 15000
    });

    // Select community
    const communitySelect = await page.$('select');
    if (communitySelect) {
      await communitySelect.selectOption({ index: 1 });
      console.log('  ✓ Community selected');
    }

    // Set rounds
    const roundsInputs = await page.$$('input[type="number"]');
    if (roundsInputs.length > 0) {
      await roundsInputs[0].fill('3');
      console.log('  ✓ Rounds set to 3');
    }

    // Add question with ranking keyword
    const textareas = await page.$$('textarea');
    if (textareas.length > 0) {
      await textareas[0].fill('What is your favorite challenge?');
      console.log('  ✓ Question filled with ranking keyword "favorite"');
    }

    await screenshot(page, 'ranking-form-filled');

    // Try to submit
    console.log('  → Attempting to submit...');
    const submitButton = await page.$('button[type="submit"]');

    // Check if submit is disabled
    const isDisabled = await submitButton.evaluate(el => el.disabled);
    if (isDisabled) {
      console.log('  ✓ Submit button is DISABLED (validation preventing submission)');
    } else {
      console.log('  ⚠ Submit button is enabled, attempting to click...');
      await submitButton.click();

      // Wait a bit for validation to show
      await page.waitForTimeout(2000);
    }

    await screenshot(page, 'ranking-validation-result');

    // Check for validation error messages
    const errorMessages = await page.$$('.error, .alert-danger, [role="alert"], .form-error');
    const errorTexts = await Promise.all(
      errorMessages.map(el => el.textContent())
    );

    console.log(`  ✓ Error messages found: ${errorTexts.length}`);
    errorTexts.forEach(text => {
      const cleaned = text.trim().substring(0, 80);
      console.log(`    - "${cleaned}${text.length > 80 ? '...' : ''}"`);
    });

    const pageUrl = page.url();
    const stillOnCreatePage = pageUrl.includes('create');
    console.log(`  ✓ Still on create page: ${stillOnCreatePage}`);

    await browser.close();

    return {
      test: 'Ranking Keyword Validation',
      success: isDisabled || (stillOnCreatePage && errorTexts.length > 0),
      isSubmitDisabled: isDisabled,
      stillOnCreatePage,
      errorCount: errorTexts.length,
      errorTexts,
      logs
    };
  } catch (error) {
    console.error(`  ✗ Test failed: ${error.message}`);
    await screenshot(page, 'ranking-error');
    await browser.close();
    return {
      test: 'Ranking Keyword Validation',
      success: false,
      error: error.message,
      logs
    };
  }
}

async function testAPIHealthAndCommunities() {
  console.log('\n' + '='.repeat(60));
  console.log('TEST 5: Check Backend API Health');
  console.log('='.repeat(60));

  try {
    console.log('  → Checking /health endpoint...');
    const healthResponse = await fetch('http://localhost:8000/health', {
      timeout: 5000
    });
    console.log(`  ✓ Health check: ${healthResponse.status}`);

    console.log('  → Checking /api/communities endpoint...');
    const commResponse = await fetch('http://localhost:8000/api/communities', {
      timeout: 5000
    });
    console.log(`  ✓ Communities endpoint: ${commResponse.status}`);

    if (commResponse.ok) {
      const data = await commResponse.json();
      console.log(`  ✓ Communities returned: ${Array.isArray(data) ? data.length : 'object'}`);
    }

    return {
      test: 'API Health',
      success: healthResponse.ok && commResponse.ok,
      healthStatus: healthResponse.status,
      communitiesStatus: commResponse.status
    };
  } catch (error) {
    console.error(`  ✗ Test failed: ${error.message}`);
    return {
      test: 'API Health',
      success: false,
      error: error.message
    };
  }
}

async function runAllTests() {
  console.log('\n');
  console.log('╔' + '='.repeat(58) + '╗');
  console.log('║' + ' '.repeat(10) + 'OpenDiscuss Application Test Suite' + ' '.repeat(14) + '║');
  console.log('╚' + '='.repeat(58) + '╝');

  const results = [];

  // Run tests in sequence
  results.push(await testAPIHealthAndCommunities());
  results.push(await testHomePageLoad());
  results.push(await testCreateDiscussionPage());
  results.push(await testSuccessfulSubmission());
  results.push(await testRankingKeywordValidation());

  // Summary
  console.log('\n' + '='.repeat(60));
  console.log('TEST SUMMARY');
  console.log('='.repeat(60));

  results.forEach((result, idx) => {
    const status = result.success ? '✓ PASS' : '✗ FAIL';
    console.log(`${idx + 1}. ${status}: ${result.test}`);
    if (result.error) {
      console.log(`   Error: ${result.error}`);
    }
  });

  const passCount = results.filter(r => r.success).length;
  const totalCount = results.length;
  console.log(`\n${passCount}/${totalCount} tests passed`);

  if (passCount === totalCount) {
    console.log('\n✅ All tests PASSED! The white screen issue appears to be RESOLVED.');
  } else {
    console.log('\n⚠️ Some tests failed. Review the details above.');
  }

  // Create detailed report
  const report = {
    timestamp: new Date().toISOString(),
    totalTests: totalCount,
    passed: passCount,
    failed: totalCount - passCount,
    results
  };

  const reportPath = '/tmp/opendiscuss-test-report.json';
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  console.log(`\n📋 Detailed report saved to: ${reportPath}`);

  return passCount === totalCount;
}

// Run tests
runAllTests().then(success => {
  process.exit(success ? 0 : 1);
}).catch(error => {
  console.error('Fatal error:', error);
  process.exit(1);
});
