/**
 * Diagnose Frontend Issues - Test all critical modules
 */
const http = require('http');

async function testEndpoint(path, description) {
  return new Promise((resolve) => {
    http.get(`http://localhost:3000${path}`, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        const success = res.statusCode === 200;
        console.log(`${success ? '✓' : '✗'} ${description}: HTTP ${res.statusCode}`);
        if (!success) {
          console.log(`  Response: ${data.substring(0, 200)}`);
        }
        resolve({ path, success, status: res.statusCode, data });
      });
    }).on('error', (err) => {
      console.log(`✗ ${description}: ${err.message}`);
      resolve({ path, success: false, error: err.message });
    });
  });
}

async function diagnose() {
  console.log('🔍 Diagnosing Frontend Issues...\n');

  const tests = [
    ['/', 'Home Page HTML'],
    ['/discussions/create', 'Create Page HTML'],
    ['/src/main.tsx', 'Main Entry Point'],
    ['/src/App.tsx', 'App Component'],
    ['/src/pages/DiscussionCreate.tsx', 'DiscussionCreate Component'],
    ['/src/components/ErrorBoundary.tsx', 'ErrorBoundary Component'],
    ['/src/services/discussionApi.ts', 'Discussion API Service'],
    ['/src/types/api.ts', 'API Types'],
    ['/@vite/client', 'Vite Client'],
  ];

  console.log('Testing Module Loading:\n');
  const results = [];
  for (const [path, desc] of tests) {
    const result = await testEndpoint(path, desc);
    results.push(result);
    await new Promise(resolve => setTimeout(resolve, 100)); // Rate limit
  }

  console.log('\n📊 Summary:');
  const failed = results.filter(r => !r.success);
  if (failed.length === 0) {
    console.log('✅ All modules loading successfully!');
    console.log('\nThe issue is likely a runtime JavaScript error.');
    console.log('Open Chrome DevTools at http://localhost:3000/discussions/create');
    console.log('and check the Console tab for errors.');
  } else {
    console.log(`❌ ${failed.length} modules failed to load:`);
    failed.forEach(f => console.log(`  - ${f.path}`));
  }

  console.log('\n💡 To debug in browser:');
  console.log('1. Open http://localhost:3000/discussions/create in Chrome/Firefox');
  console.log('2. Press F12 to open DevTools');
  console.log('3. Go to Console tab');
  console.log('4. Look for red error messages');
  console.log('5. Take a screenshot and share the error');
}

diagnose();
