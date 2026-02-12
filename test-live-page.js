const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  const errors = [];
  const consoleMessages = [];

  // Capture console messages
  page.on('console', msg => {
    const text = msg.text();
    consoleMessages.push(`[${msg.type()}] ${text}`);
    if (msg.type() === 'error') {
      errors.push(text);
    }
  });

  // Capture page errors
  page.on('pageerror', error => {
    errors.push(`Page error: ${error.message}`);
    console.error('Page error:', error.message);
  });

  try {
    console.log('1. Navigating to live discussion page...');
    await page.goto('http://localhost:3000/discussions/352a4495-69d3-49ea-bff4-4055c398ba2c/live', {
      waitUntil: 'networkidle',
      timeout: 10000
    });

    console.log('2. Page loaded. Waiting for content...');
    await page.waitForTimeout(2000);

    // Check if page loaded without white screen
    const bodyText = await page.textContent('body');
    console.log('Body has text:', bodyText.length > 0);

    // Take initial screenshot
    await page.screenshot({ path: '/mnt/c/Users/Guayaba/apps/opendiscuss_v00/screenshot-initial.png', fullPage: true });
    console.log('Initial screenshot saved');

    // Check for status
    const statusVisible = await page.locator('text=/status|round|created|active/i').first().isVisible().catch(() => false);
    console.log('Status visible:', statusVisible);

    // Check for Start Discussion button
    const startButton = page.locator('button:has-text("Start Discussion")').first();
    const hasStartButton = await startButton.isVisible().catch(() => false);
    console.log('3. Has Start Discussion button:', hasStartButton);

    if (hasStartButton) {
      console.log('4. Clicking Start Discussion button...');
      await startButton.click();
      await page.waitForTimeout(1000);

      // Look for confirm button in dialog
      const confirmButton = page.locator('button:has-text("Start")').last();
      const hasConfirm = await confirmButton.isVisible().catch(() => false);
      if (hasConfirm) {
        console.log('   Clicking confirm...');
        await confirmButton.click();
      }

      console.log('5. Waiting 5 seconds for update...');
      await page.waitForTimeout(5000);
    } else {
      console.log('4-5. No start button, waiting 5 seconds...');
      await page.waitForTimeout(5000);
    }

    console.log('6. Checking for Round 1 status...');
    const roundText = await page.locator('text=/round 1|round 2|collecting|input/i').first().textContent().catch(() => null);
    console.log('Round status text:', roundText);

    // Take final screenshot
    await page.screenshot({ path: '/mnt/c/Users/Guayaba/apps/opendiscuss_v00/screenshot-final.png', fullPage: true });
    console.log('7. Final screenshot saved');

    console.log('\n=== RESULTS ===');
    console.log('Page loaded successfully:', bodyText.length > 0);
    console.log('Errors found:', errors.length);
    if (errors.length > 0) {
      console.log('\nERRORS:');
      errors.forEach(err => console.log('  -', err));
    }

    console.log('\nRecent console messages:');
    consoleMessages.slice(-10).forEach(msg => console.log('  ', msg));

  } catch (error) {
    console.error('Test failed:', error.message);
    await page.screenshot({ path: '/mnt/c/Users/Guayaba/apps/opendiscuss_v00/screenshot-error.png', fullPage: true });
  } finally {
    await page.waitForTimeout(2000);
    await browser.close();
  }
})();
