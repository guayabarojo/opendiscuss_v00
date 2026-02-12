/**
 * Browser Visible Test - Opens actual browser window to debug white screen
 */
const { chromium } = require('playwright');

async function testCreatePageVisible() {
  console.log('🔍 Opening browser window to test Create Discussion page...');

  // Launch browser in HEADED mode (visible window)
  const browser = await chromium.launch({
    headless: false,  // SHOW THE BROWSER WINDOW
    slowMo: 500,      // Slow down actions so we can see them
  });

  const page = await browser.newPage();

  // Capture console logs from the browser
  page.on('console', msg => {
    const type = msg.type();
    const text = msg.text();
    console.log(`[Browser ${type.toUpperCase()}]:`, text);
  });

  // Capture JavaScript errors
  page.on('pageerror', error => {
    console.error('❌ [Browser ERROR]:', error.message);
    console.error('Stack:', error.stack);
  });

  // Capture failed requests
  page.on('requestfailed', request => {
    console.error('❌ [Network FAILED]:', request.url());
  });

  try {
    console.log('\n1. Navigating to home page...');
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle', timeout: 10000 });
    console.log('✓ Home page loaded');

    await page.screenshot({ path: '/tmp/01-homepage.png' });
    console.log('✓ Screenshot saved: /tmp/01-homepage.png');

    console.log('\n2. Navigating to Create Discussion page...');
    await page.goto('http://localhost:3000/discussions/create', {
      waitUntil: 'networkidle',
      timeout: 10000
    });
    console.log('✓ Create page loaded (or attempted to load)');

    await page.screenshot({ path: '/tmp/02-create-page.png' });
    console.log('✓ Screenshot saved: /tmp/02-create-page.png');

    // Wait a bit to see the page
    console.log('\n3. Waiting 10 seconds for you to inspect the browser window...');
    await page.waitForTimeout(10000);

    // Try to find elements
    console.log('\n4. Checking for page elements...');
    const title = await page.$('h1');
    if (title) {
      const text = await title.textContent();
      console.log('✓ Found h1:', text);
    } else {
      console.log('✗ No h1 element found');
    }

    const form = await page.$('form');
    if (form) {
      console.log('✓ Form element found');
    } else {
      console.log('✗ No form element found - THIS IS THE WHITE SCREEN ISSUE');
    }

    // Get full HTML if white screen
    const bodyText = await page.evaluate(() => document.body.textContent);
    console.log('\n5. Body text content:', bodyText.substring(0, 200));

    console.log('\n✅ Test complete. Press Ctrl+C to close browser or wait 30 more seconds...');
    await page.waitForTimeout(30000);

  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
    await page.screenshot({ path: '/tmp/error-screenshot.png' });
    console.log('Error screenshot saved: /tmp/error-screenshot.png');
  } finally {
    await browser.close();
  }
}

testCreatePageVisible().catch(error => {
  console.error('Fatal error:', error);
  process.exit(1);
});
