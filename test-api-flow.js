/**
 * OpenDiscuss API Testing Suite
 * Tests the discussion creation flow via API and verifies validation
 */

const BASE_URL = 'http://localhost:8000/api/v1';

async function makeRequest(method, endpoint, data = null) {
  const url = `${BASE_URL}${endpoint}`;
  const options = {
    method,
    headers: {
      'Content-Type': 'application/json',
    },
    timeout: 15000,
  };

  if (data) {
    options.body = JSON.stringify(data);
  }

  try {
    const response = await fetch(url, options);
    const responseBody = await response.json();

    return {
      status: response.status,
      ok: response.ok,
      data: responseBody,
      headers: Object.fromEntries(response.headers),
    };
  } catch (error) {
    return {
      status: 0,
      ok: false,
      error: error.message,
    };
  }
}

async function testHealthCheck() {
  console.log('\n' + '='.repeat(70));
  console.log('TEST 1: Health Check');
  console.log('='.repeat(70));

  try {
    const response = await fetch('http://localhost:8000/health', {
      timeout: 5000,
    });
    const data = await response.json();

    console.log(`  ✓ Status: ${response.status}`);
    console.log(`  ✓ Service: ${data.service}`);
    console.log(`  ✓ Version: ${data.version}`);
    console.log(`  ✓ Status: ${data.status}`);

    return {
      test: 'Health Check',
      success: response.ok,
      data,
    };
  } catch (error) {
    console.error(`  ✗ Error: ${error.message}`);
    return {
      test: 'Health Check',
      success: false,
      error: error.message,
    };
  }
}

async function testSuccessfulDiscussionCreation() {
  console.log('\n' + '='.repeat(70));
  console.log('TEST 2: Create Discussion with Valid Questions (SUCCESS CASE)');
  console.log('='.repeat(70));

  const questions = [
    'What are the main challenges we face?',
    'How can we address these challenges?',
    'What resources do we need?',
  ];

  console.log('  Testing questions (no ranking keywords):');
  questions.forEach((q, i) => console.log(`    Q${i + 1}: "${q}"`));

  const payload = {
    community_id: '00000000-0000-0000-0000-000000000001',
    mode: 'HOST_DEFINED',
    total_rounds: 3,
    questions,
  };

  console.log('\n  → Sending POST /discussions request...');
  const response = await makeRequest('POST', '/discussions', payload);

  if (!response.ok) {
    console.error(`  ✗ Request failed with status ${response.status}`);
    console.error(`  ✗ Response:`, JSON.stringify(response.data, null, 2));
    return {
      test: 'Successful Discussion Creation',
      success: false,
      status: response.status,
      error: response.data?.message || 'Unknown error',
    };
  }

  const discussion = response.data;
  console.log(`  ✓ Discussion created successfully!`);
  console.log(`  ✓ Discussion ID: ${discussion.discussion_id}`);
  console.log(`  ✓ Status: ${discussion.status}`);
  console.log(`  ✓ Mode: ${discussion.mode}`);
  console.log(`  ✓ Rounds: ${discussion.total_rounds}`);

  return {
    test: 'Successful Discussion Creation',
    success: true,
    discussionId: discussion.discussion_id,
    status: discussion.status,
  };
}

async function testRankingKeywordRejection() {
  console.log('\n' + '='.repeat(70));
  console.log('TEST 3: Reject Discussion with Ranking Keyword (FAILURE CASE)');
  console.log('='.repeat(70));

  const questions = [
    'What is your favorite challenge?',
    'How can we address these challenges?',
    'What resources do we need?',
  ];

  console.log('  Testing question with ranking keyword:');
  console.log(`    Q1: "${questions[0]}" (contains "favorite")`);
  console.log(`  Expected: 400 Bad Request with CONTAINS_RANKING_KEYWORD error`);

  const payload = {
    community_id: '00000000-0000-0000-0000-000000000001',
    mode: 'HOST_DEFINED',
    total_rounds: 3,
    questions,
  };

  console.log('\n  → Sending POST /discussions request...');
  const response = await makeRequest('POST', '/discussions', payload);

  if (response.ok) {
    console.error(`  ✗ Request succeeded but should have failed!`);
    return {
      test: 'Ranking Keyword Rejection',
      success: false,
      error: 'Validation should have rejected ranking keyword',
    };
  }

  console.log(`  ✓ Request correctly rejected with status ${response.status}`);

  const errorData = response.data?.message || response.data;
  if (typeof errorData === 'object') {
    console.log(`  ✓ Error type: ${errorData.error}`);
    console.log(`  ✓ Error message: ${errorData.message}`);
    if (errorData.details?.error_code) {
      console.log(`  ✓ Error code: ${errorData.details.error_code}`);
    }
  } else {
    console.log(`  ✓ Error message: ${errorData}`);
  }

  const isCorrectError =
    response.status === 400 &&
    (response.data?.message?.error === 'VALIDATION_ERROR' ||
      JSON.stringify(response.data).includes('CONTAINS_RANKING_KEYWORD') ||
      JSON.stringify(response.data).includes('favorite'));

  return {
    test: 'Ranking Keyword Rejection',
    success: isCorrectError,
    status: response.status,
    errorCode:
      response.data?.message?.details?.error_code ||
      'CONTAINS_RANKING_KEYWORD',
  };
}

async function testMultipleRankingKeywords() {
  console.log('\n' + '='.repeat(70));
  console.log('TEST 4: Test Multiple Ranking Keywords');
  console.log('='.repeat(70));

  const rankingKeywords = [
    'favorite',
    'best',
    'worst',
    'rank',
    'vote',
    'choose',
  ];
  const results = [];

  for (const keyword of rankingKeywords) {
    const question = `What is the ${keyword} approach to this problem?`;

    const payload = {
      community_id: '00000000-0000-0000-0000-000000000001',
      mode: 'HOST_DEFINED',
      total_rounds: 3,
      questions: [question, 'How do we proceed?', 'What is next?'],
    };

    const response = await makeRequest('POST', '/discussions', payload);

    const rejected = !response.ok && response.status === 400;
    const keywordDetected =
      JSON.stringify(response.data).includes(keyword) ||
      JSON.stringify(response.data).includes('CONTAINS_RANKING_KEYWORD');

    results.push({
      keyword,
      rejected,
      keywordDetected,
    });

    const status = rejected && keywordDetected ? '✓' : '✗';
    console.log(`  ${status} "${keyword}": rejected=${rejected}`);
  }

  const allRejected = results.every(r => r.rejected);
  return {
    test: 'Multiple Ranking Keywords',
    success: allRejected,
    testResults: results,
  };
}

async function testInvalidQuestionLength() {
  console.log('\n' + '='.repeat(70));
  console.log('TEST 5: Test Question Length Validation');
  console.log('='.repeat(70));

  const testCases = [
    {
      name: 'Too short (< 10 chars)',
      question: 'Short?',
      shouldFail: true,
    },
    {
      name: 'Valid minimum (10 chars)',
      question: 'How are you',
      shouldFail: false,
    },
    {
      name: 'Valid maximum (200 chars)',
      question:
        'W' +
        'h'.repeat(198),
      shouldFail: false,
    },
    {
      name: 'Too long (> 200 chars)',
      question: 'What is ' + 'x'.repeat(200),
      shouldFail: true,
    },
  ];

  const results = [];

  for (const testCase of testCases) {
    const payload = {
      community_id: '00000000-0000-0000-0000-000000000001',
      mode: 'HOST_DEFINED',
      total_rounds: 3,
      questions: [
        testCase.question,
        'How do we proceed?',
        'What is next?',
      ],
    };

    const response = await makeRequest('POST', '/discussions', payload);

    const failed = !response.ok;
    const outcome = failed === testCase.shouldFail ? 'PASS' : 'FAIL';
    const symbol = outcome === 'PASS' ? '✓' : '✗';

    results.push({
      name: testCase.name,
      length: testCase.question.length,
      shouldFail: testCase.shouldFail,
      actuallyFailed: failed,
      pass: outcome === 'PASS',
    });

    console.log(
      `  ${symbol} ${testCase.name} (${testCase.question.length} chars): ${outcome}`
    );
  }

  const allPass = results.every(r => r.pass);
  return {
    test: 'Question Length Validation',
    success: allPass,
    testResults: results,
  };
}

async function testProhibitedOpeningWords() {
  console.log('\n' + '='.repeat(70));
  console.log('TEST 6: Test Prohibited Opening Words');
  console.log('='.repeat(70));

  const testCases = [
    { question: 'What are the main issues?', shouldPass: true },
    { question: 'How can we improve?', shouldPass: true },
    { question: 'Why do you think this?', shouldPass: false },
    { question: 'Do you agree?', shouldPass: false },
    { question: 'Should we proceed?', shouldPass: false },
    { question: 'Would you like this?', shouldPass: false },
  ];

  const results = [];

  for (const testCase of testCases) {
    const payload = {
      community_id: '00000000-0000-0000-0000-000000000001',
      mode: 'HOST_DEFINED',
      total_rounds: 3,
      questions: [
        testCase.question,
        'How do we proceed?',
        'What is next?',
      ],
    };

    const response = await makeRequest('POST', '/discussions', payload);

    const passed = response.ok;
    const outcome = passed === testCase.shouldPass ? 'PASS' : 'FAIL';
    const symbol = outcome === 'PASS' ? '✓' : '✗';

    results.push({
      question: testCase.question,
      shouldPass: testCase.shouldPass,
      actuallyPassed: passed,
      pass: outcome === 'PASS',
    });

    console.log(
      `  ${symbol} "${testCase.question}": pass=${passed} (expected=${testCase.shouldPass})`
    );
  }

  const allPass = results.every(r => r.pass);
  return {
    test: 'Prohibited Opening Words',
    success: allPass,
    testResults: results,
  };
}

async function testBinaryChoiceRejection() {
  console.log('\n' + '='.repeat(70));
  console.log('TEST 7: Test Binary Choice Rejection');
  console.log('='.repeat(70));

  const binaryQuestions = [
    'Do you agree or disagree?',
    'Is this true or false?',
    'Yes or no, should we proceed?',
  ];

  const results = [];

  for (const question of binaryQuestions) {
    const payload = {
      community_id: '00000000-0000-0000-0000-000000000001',
      mode: 'HOST_DEFINED',
      total_rounds: 3,
      questions: [question, 'How do we proceed?', 'What is next?'],
    };

    const response = await makeRequest('POST', '/discussions', payload);

    const rejected = !response.ok && response.status === 400;
    const binaryDetected =
      JSON.stringify(response.data).includes('binary') ||
      JSON.stringify(response.data).includes('BINARY_CHOICE');

    results.push({
      question,
      rejected,
      binaryDetected,
    });

    const symbol = rejected && binaryDetected ? '✓' : '✗';
    console.log(`  ${symbol} "${question}": rejected=${rejected}`);
  }

  const allRejected = results.every(r => r.rejected);
  return {
    test: 'Binary Choice Rejection',
    success: allRejected,
    testResults: results,
  };
}

async function runAllTests() {
  console.log('\n');
  console.log('╔' + '='.repeat(68) + '╗');
  console.log('║' + ' '.repeat(15) + 'OpenDiscuss API Testing Suite' + ' '.repeat(24) + '║');
  console.log('╚' + '='.repeat(68) + '╝');

  const results = [];

  results.push(await testHealthCheck());
  results.push(await testSuccessfulDiscussionCreation());
  results.push(await testRankingKeywordRejection());
  results.push(await testMultipleRankingKeywords());
  results.push(await testInvalidQuestionLength());
  results.push(await testProhibitedOpeningWords());
  results.push(await testBinaryChoiceRejection());

  // Summary
  console.log('\n' + '='.repeat(70));
  console.log('TEST SUMMARY');
  console.log('='.repeat(70));

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
    console.log('\n✅ All API tests PASSED!');
    console.log('   - Valid discussions are created successfully');
    console.log('   - Ranking keywords are properly rejected');
    console.log('   - Question validation is working correctly');
    console.log('   - The backend is functioning as expected');
  } else {
    console.log('\n⚠️ Some tests failed. Review the details above.');
  }

  // Create detailed report
  const report = {
    timestamp: new Date().toISOString(),
    totalTests: totalCount,
    passed: passCount,
    failed: totalCount - passCount,
    results,
  };

  const fs = require('fs');
  const reportPath = '/tmp/opendiscuss-api-test-report.json';
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
