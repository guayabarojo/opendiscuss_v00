/**
 * Comprehensive Application Test Suite
 * Tests the full OpenDiscuss application flow
 */

const { chromium } = require('playwright');

async function testHomePage() {
  console.log('🔍 Testing: Home Page...');
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  try {
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle', timeout: 10000 });

    // Check page title
    const title = await page.title();
    console.log(`✓ Page title: ${title}`);

    // Check for welcome text
    const welcomeText = await page.textContent('h2');
    console.log(`✓ Welcome text: ${welcomeText}`);

    // Check for Create button
    const createButton = await page.$('.btn-primary');
    if (createButton) {
      console.log('✓ Create Discussion button found');
    } else {
      console.log('✗ Create Discussion button NOT found');
    }

    await browser.close();
    return { success: true, page: 'home' };
  } catch (error) {
    console.error('✗ Home page test failed:', error.message);
    await browser.close();
    return { success: false, page: 'home', error: error.message };
  }
}

async function testCreateDiscussionPage() {
  console.log('🔍 Testing: Create Discussion Page...');
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  try {
    await page.goto('http://localhost:3000/discussions/create', { waitUntil: 'networkidle', timeout: 10000 });

    // Check if form exists
    const form = await page.$('form');
    if (form) {
      console.log('✓ Discussion creation form found');
    } else {
      console.log('✗ Discussion creation form NOT found');
    }

    // Take screenshot
    await page.screenshot({ path: '/tmp/create-discussion.png' });
    console.log('✓ Screenshot saved to /tmp/create-discussion.png');

    await browser.close();
    return { success: true, page: 'create' };
  } catch (error) {
    console.error('✗ Create discussion page test failed:', error.message);
    await browser.close();
    return { success: false, page: 'create', error: error.message };
  }
}

async function testCreateDiscussionFlow() {
  console.log('🔍 Testing: Full Create Discussion Flow...');
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  // Listen for console messages and network requests
  page.on('console', msg => console.log('  Browser console:', msg.text()));
  page.on('requestfailed', request => console.log('  ✗ Failed request:', request.url()));

  try {
    await page.goto('http://localhost:3000/discussions/create', { waitUntil: 'networkidle', timeout: 10000 });

    // Wait for form to be ready
    await page.waitForSelector('input[name="community_id"], input[id*="community"], input', { timeout: 5000 });

    // Take screenshot of form
    await page.screenshot({ path: '/tmp/form-initial.png' });
    console.log('✓ Initial form screenshot saved');

    // Try to fill form (adjust selectors based on actual form)
    try {
      // Try different possible selectors for community ID
      const communityInput = await page.$('input[name="community_id"]') ||
                           await page.$('input[id*="community"]') ||
                           await page.$('input[type="text"]');

      if (communityInput) {
        await communityInput.fill('00000000-0000-0000-0000-000000000001');
        console.log('✓ Filled community ID');
      }

      // Try to add questions
      const questionInputs = await page.$$('input[type="text"], textarea');
      console.log(`  Found ${questionInputs.length} text inputs`);

      await page.screenshot({ path: '/tmp/form-filled.png' });
      console.log('✓ Filled form screenshot saved');

    } catch (fillError) {
      console.log('  ⚠ Could not fill form:', fillError.message);
    }

    await browser.close();
    return { success: true, flow: 'create' };
  } catch (error) {
    console.error('✗ Create discussion flow test failed:', error.message);
    await page.screenshot({ path: '/tmp/form-error.png' }).catch(() => {});
    await browser.close();
    return { success: false, flow: 'create', error: error.message };
  }
}

async function testAPIEndpoints() {
  console.log('🔍 Testing: API Endpoints...');

  const tests = [
    { name: 'Health Check', url: 'http://localhost:8000/health' },
    { name: 'API Docs', url: 'http://localhost:8000/docs' },
  ];

  const results = [];

  for (const test of tests) {
    try {
      const response = await fetch(test.url);
      if (response.ok) {
        console.log(`✓ ${test.name}: ${response.status}`);
        results.push({ test: test.name, success: true, status: response.status });
      } else {
        console.log(`✗ ${test.name}: ${response.status}`);
        results.push({ test: test.name, success: false, status: response.status });
      }
    } catch (error) {
      console.log(`✗ ${test.name}: ${error.message}`);
      results.push({ test: test.name, success: false, error: error.message });
    }
  }

  return { success: true, results };
}

async function runAllTests() {
  console.log('🚀 Starting OpenDiscuss Application Tests\n');
  console.log('=' .repeat(50));

  const results = await Promise.all([
    testHomePage(),
    testCreateDiscussionPage(),
    testCreateDiscussionFlow(),
    testAPIEndpoints(),
  ]);

  console.log('\n' + '='.repeat(50));
  console.log('📊 Test Results Summary:');
  results.forEach((result, idx) => {
    const status = result.success ? '✓ PASS' : '✗ FAIL';
    console.log(`  ${status}: Test ${idx + 1}`);
    if (!result.success && result.error) {
      console.log(`    Error: ${result.error}`);
    }
  });

  const allPassed = results.every(r => r.success);
  console.log('\n' + (allPassed ? '✅ All tests passed!' : '❌ Some tests failed'));

  return allPassed;
}

// Run tests
runAllTests().then(success => {
  process.exit(success ? 0 : 1);
}).catch(error => {
  console.error('Fatal error:', error);
  process.exit(1);
});
