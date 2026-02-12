# Frontend Testing Quick Start Guide

## Prerequisites

```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/frontend
npm install
```

## First-Time Setup

Install Playwright browsers (only needed once):

```bash
npm run playwright:install
```

This will download Chromium, Firefox, and WebKit browsers for E2E testing.

## Running Tests

### Quick Test (All Unit Tests)

```bash
npm run test:unit
```

Expected output:
- 35+ tests for TextInputForm
- 30+ tests for CountdownTimer
- Should complete in <10 seconds

### Watch Mode (Development)

```bash
npm run test:unit:watch
```

Tests will re-run automatically when you change files.

### E2E Tests (Full User Flows)

```bash
npm run test:e2e
```

Expected output:
- 15+ tests for text submission
- 15+ tests for voice submission
- Should complete in <30 seconds

### Interactive E2E Testing

```bash
npm run test:e2e:ui
```

Opens Playwright UI for visual debugging and test inspection.

### Debug Specific Test

```bash
npm run test:e2e:debug
```

Opens Playwright Inspector for step-by-step test execution.

## Test Files

### Unit Tests
- `/frontend/tests/unit/TextInputForm.test.tsx` - Form component tests
- `/frontend/tests/unit/CountdownTimer.test.tsx` - Timer component tests

### E2E Tests
- `/frontend/tests/e2e/test_text_submission.spec.ts` - Text submission workflow
- `/frontend/tests/e2e/test_voice_submission.spec.ts` - Voice submission workflow

## Common Commands

```bash
# Run specific unit test file
npx vitest tests/unit/TextInputForm.test.tsx

# Run specific E2E test file
npx playwright test tests/e2e/test_text_submission.spec.ts

# Run tests with coverage report
npx vitest --coverage

# Run E2E tests in headed mode (see browser)
npx playwright test --headed

# Run E2E tests in specific browser
npx playwright test --project=firefox

# Generate HTML test report
npx playwright show-report
```

## Troubleshooting

### Tests Won't Run

```bash
# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install
```

### Playwright Browsers Missing

```bash
npm run playwright:install
```

### Test Failures

```bash
# Run with debug mode to see what's happening
npm run test:e2e:debug

# Check screenshots in test-results/ directory
ls test-results/
```

### Port Already in Use

E2E tests start a dev server on port 5173. If it's in use:

```bash
# Kill existing process
pkill -f vite

# Or change port in playwright.config.ts
```

## Test Coverage

### What's Tested

- Character counting and validation
- Form submission workflows
- Real-time countdown timer
- WebSocket connections
- Rate limiting enforcement
- Error handling
- Voice recording and transcription
- Keyboard accessibility
- Screen reader compatibility

### Test Statistics

- **Total Test Files**: 4
- **Total Test Cases**: 95+
- **Lines of Test Code**: 2,051
- **Components Tested**: 2 (TextInputForm, CountdownTimer)
- **User Flows Tested**: 2 (Text submission, Voice submission)

## Continuous Integration

Tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Install dependencies
  run: npm install

- name: Install Playwright
  run: npx playwright install --with-deps

- name: Run unit tests
  run: npm run test:unit

- name: Run E2E tests
  run: npm run test:e2e
```

## Documentation

For detailed information:
- **Full Documentation**: `/frontend/tests/README.md`
- **Implementation Summary**: `/frontend/TESTING_IMPLEMENTATION_SUMMARY.md`
- **Task List**: `/specs/002-input-collection/tasks.md` (T078-T081)

## Support

If you encounter issues:

1. Check `/frontend/tests/README.md` for detailed troubleshooting
2. Verify all components exist in `/frontend/src/components/`
3. Ensure backend services are running for integration tests
4. Review test output for specific error messages

## Next Steps

After running tests successfully:

1. Review coverage report: `npx vitest --coverage`
2. Add tests for new features following existing patterns
3. Run tests before committing changes
4. Integrate tests into CI/CD pipeline

---

**Quick Reference**:
- Unit tests: `npm run test:unit`
- E2E tests: `npm run test:e2e`
- Watch mode: `npm run test:unit:watch`
- Debug mode: `npm run test:e2e:debug`
