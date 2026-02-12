# Frontend Test Suite - Spec 002 Input Collection Protocol

This directory contains comprehensive tests for the Input Collection Protocol frontend components.

## Test Structure

```
tests/
├── setup.ts                    # Vitest setup and configuration
├── unit/                       # Unit tests for React components
│   ├── TextInputForm.test.tsx  # T078: TextInputForm component tests
│   └── CountdownTimer.test.tsx # T079: CountdownTimer component tests
└── e2e/                        # End-to-end tests with Playwright
    ├── test_text_submission.spec.ts   # T080: Text submission flow
    └── test_voice_submission.spec.ts  # T081: Voice submission flow
```

## Running Tests

### Unit Tests (Vitest)

```bash
# Run all unit tests
npm run test:unit

# Run unit tests in watch mode
npm run test:unit:watch

# Run all tests (unit + integration)
npm test
```

### E2E Tests (Playwright)

First, install Playwright browsers:

```bash
npm run playwright:install
```

Then run the E2E tests:

```bash
# Run all E2E tests
npm run test:e2e

# Run E2E tests with UI
npm run test:e2e:ui

# Run E2E tests in debug mode
npm run test:e2e:debug
```

## Test Coverage

### T078: TextInputForm Unit Tests

Tests for `/frontend/src/components/TextInputForm.tsx`:

- **Character Count**: Displays and updates character count, shows warning near limit
- **Validation**: Empty text, whitespace-only, max length enforcement
- **Submit Button States**: Disabled when invalid, enabled when valid, loading state
- **Form Submission**: Calls onSubmit, clears form on success, displays errors
- **Rate Limiting**: Shows remaining count, disables when limit reached
- **Initial Text**: Loads and updates with initialText prop
- **Edge Cases**: Exactly 5000 chars, multiline text, special/unicode characters

**Total Tests**: 35+ test cases covering all user interactions

### T079: CountdownTimer Unit Tests

Tests for `/frontend/src/components/CountdownTimer.tsx`:

- **Time Formatting**: MM:SS format, padding zeros, handling negative/null values
- **Color Coding**: Green (>60s), yellow (31-60s), red (≤30s), gray (closed)
- **Status Messages**: Open, closed, before window, not configured
- **Warnings**: Display when <1 minute remaining
- **WebSocket Connection**: Initialization, updates, disconnect on unmount
- **Error Handling**: Connection failures, error clearing
- **Window Close Callback**: Triggers when countdown reaches zero and closes
- **Edge Cases**: Very large times, negative times, null values

**Total Tests**: 30+ test cases covering real-time timer functionality

### T080: Text Submission E2E Tests

Tests for complete text submission user journey:

- **Happy Path**: Navigate → type → submit → verify success
- **Validation**: Empty text, whitespace-only, max length exceeded
- **Error Handling**: Window closed, rate limit exceeded, submission errors
- **Rate Limiting**: Display remaining count, disable form when limit reached
- **Character Count**: Updates in real-time, warning near limit
- **User Input**: Multiline text, special characters, keyboard shortcuts
- **Accessibility**: Keyboard navigation, ARIA labels, screen reader announcements

**Total Tests**: 15+ E2E scenarios covering full user flows

### T081: Voice Submission E2E Tests

Tests for complete voice submission user journey:

- **Happy Path**: Record → stop → transcribe → review → accept → submit
- **Re-recording**: User can re-record if not satisfied with transcript
- **Error Handling**: Transcription failures, microphone permission denial
- **Latency Monitoring**: Shows latency info, warns if >3000ms
- **Transcript Review**: Displays transcript, action buttons (accept/re-record)
- **Modality Verification**: Submits with VOICE modality
- **Recording Controls**: Start, stop, cancel, cleanup audio resources
- **Multiple Submissions**: Can record multiple times in same round
- **Accessibility**: Keyboard navigation, button labels, state announcements

**Total Tests**: 15+ E2E scenarios covering voice input flow

## Test Technologies

### Unit Tests
- **Vitest**: Fast unit test runner with native ESM support
- **React Testing Library**: User-centric testing utilities
- **@testing-library/user-event**: Realistic user interaction simulation
- **jsdom**: Simulated browser environment

### E2E Tests
- **Playwright**: Modern browser automation
- **Mock APIs**: Route interception for API testing
- **Mock MediaRecorder**: Simulated audio recording without real microphone
- **Accessibility Testing**: Keyboard navigation and ARIA compliance

## Test Best Practices

1. **User-Centric**: Tests focus on user behavior, not implementation details
2. **Comprehensive Coverage**: Edge cases, errors, and accessibility
3. **Realistic Interactions**: Uses userEvent for realistic typing/clicking
4. **Isolated**: Each test is independent with proper setup/cleanup
5. **Mock External Dependencies**: WebSocket, MediaRecorder, API calls
6. **Accessibility**: Includes keyboard navigation and screen reader tests

## Continuous Integration

These tests are designed to run in CI/CD pipelines:

- Unit tests run quickly (<10s) for fast feedback
- E2E tests can run headlessly in CI environments
- Playwright supports multiple browsers (Chromium, Firefox, WebKit)
- Screenshots/videos captured on failure for debugging

## Debugging Tests

### Unit Tests

```bash
# Run specific test file
npx vitest tests/unit/TextInputForm.test.tsx

# Run with coverage
npx vitest --coverage
```

### E2E Tests

```bash
# Run specific test file
npx playwright test tests/e2e/test_text_submission.spec.ts

# Run with headed browser (see what's happening)
npx playwright test --headed

# Run in debug mode (step through test)
npx playwright test --debug

# Generate test report
npx playwright show-report
```

## Component Dependencies

### TextInputForm
- **Props**: participantId, roundId, onSubmit, disabled, initialText, remainingSubmissions
- **API**: POST /api/v1/submissions/
- **Services**: submissionApi.submitText()

### CountdownTimer
- **Props**: roundId, onWindowClose
- **WebSocket**: /ws/rounds/{roundId}/timer
- **Services**: WebSocketTimerClient

### RoundInputPage
- **Components**: TextInputForm, InputCollectionHistory, CountdownTimer
- **API**: GET /api/v1/submissions/participant/{participantId}/round/{roundId}
- **Services**: submissionApi.getParticipantSubmissions()

## Test Data

All tests use mock data:
- Participant ID: `test-participant-{test-type}`
- Round ID: `test-round-{test-type}`
- Mock API responses with realistic data structures
- Mock WebSocket updates with sub-second timing simulation

## Known Limitations

1. **Voice Tests**: Uses mocked MediaRecorder, not testing real audio processing
2. **WebSocket Tests**: Mocked connections, not testing real WebSocket server
3. **Timing Tests**: May be flaky in slow CI environments (use generous timeouts)
4. **Browser Support**: E2E tests primarily run in Chromium (CI), all browsers in dev

## Contributing

When adding new tests:

1. Follow existing naming conventions
2. Group related tests in describe blocks
3. Use clear, descriptive test names
4. Add comments for complex test setup
5. Clean up after each test (cleanup functions)
6. Mock external dependencies appropriately
7. Include both happy path and error cases

## Maintenance

These tests align with tasks in `/specs/002-input-collection/tasks.md`:
- T078: TextInputForm unit tests
- T079: CountdownTimer unit tests
- T080: Text submission E2E tests
- T081: Voice submission E2E tests

Update this README when adding new test scenarios or changing test structure.
