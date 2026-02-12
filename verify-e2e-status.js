/**
 * Quick verification script to check the actual page content
 * after starting a discussion
 */

const { chromium } = require('playwright');

async function verifyStatus() {
  const browser = await chromium.launch({ headless: false });
  const page = await browser.newPage();

  try {
    // Navigate to the discussion that was just created
    const discussionId = '6a1a44e5-d00b-4b4c-843e-f98d2f2aee8b';
    console.log(`Navigating to discussion ${discussionId}...`);

    await page.goto(`http://localhost:3000/discussions/${discussionId}/live`, {
      waitUntil: 'networkidle',
      timeout: 10000
    });

    console.log('Page loaded. Waiting 3 seconds...');
    await page.waitForTimeout(3000);

    // Get all text content
    const bodyText = await page.textContent('body');
    console.log('\n=== PAGE TEXT ===');
    console.log(bodyText);
    console.log('=================\n');

    // Check for specific elements
    const statusBadge = await page.$('.status-badge');
    if (statusBadge) {
      const statusText = await statusBadge.textContent();
      console.log(`Status badge: "${statusText}"`);
    } else {
      console.log('No status badge found');
    }

    // Take a screenshot
    await page.screenshot({ path: '/tmp/verify-status.png', fullPage: true });
    console.log('Screenshot saved to /tmp/verify-status.png');

    // Keep browser open for inspection
    console.log('\nKeeping browser open for 30 seconds for manual inspection...');
    await page.waitForTimeout(30000);

    await browser.close();

  } catch (error) {
    console.error('Error:', error.message);
    await page.screenshot({ path: '/tmp/verify-error.png', fullPage: true });
    await browser.close();
  }
}

verifyStatus();
