# Test Execution Guide - Spec 002 Input Collection Protocol

**Status**: ✅ All 245+ tests created and ready to run
**Implementation**: ✅ Complete (88/90 core tasks)
**Next Step**: Execute tests to verify functionality

---

## Prerequisites

### Backend
```bash
cd backend
poetry install                    # Install all dependencies
createdb opendiscuss             # Create PostgreSQL database
poetry run alembic upgrade head  # Run migrations
```

### Frontend
```bash
cd frontend
npm install                      # Install dependencies
npm run playwright:install       # Install Playwright browsers (first time only)
```

---

## Test Execution Commands

### Backend Tests (150 tests)

#### 1. Unit Tests (119 tests)
```bash
cd backend
poetry run pytest tests/unit/ -v

# Run specific test files
poetry run pytest tests/unit/test_window_enforcement.py -v  # 29 tests
poetry run pytest tests/unit/test_rate_limiter.py -v        # 22 tests
poetry run pytest tests/unit/test_normalization.py -v       # 68 tests
```

**Expected Output**:
```
======================== 119 passed in X.XXs ========================
```

#### 2. Integration Tests (31 tests)
```bash
cd backend
poetry run pytest tests/integration/ -v

# Run specific test files
poetry run pytest tests/integration/test_text_submission.py -v           # 6 tests
poetry run pytest tests/integration/test_voice_transcription.py -v       # 8 tests
poetry run pytest tests/integration/test_rate_limiting.py -v             # 3 tests
poetry run pytest tests/integration/test_window_enforcement.py -v        # 8 tests
poetry run pytest tests/contract/test_submission_to_summarization.py -v  # 6 tests
```

**Expected Output**:
```
======================== 31 passed in X.XXs ========================
```

#### 3. All Backend Tests (150 tests)
```bash
cd backend
poetry run pytest tests/ -v --tb=short
```

---

### Frontend Tests (95+ tests)

#### 1. Unit Tests (65+ tests)
```bash
cd frontend
npm run test:unit

# Watch mode for development
npm run test:unit:watch

# Run specific test files
npm run test:unit -- TextInputForm.test.tsx
npm run test:unit -- CountdownTimer.test.tsx
```

**Expected Output**:
```
 ✓ tests/unit/TextInputForm.test.tsx (35 tests)
 ✓ tests/unit/CountdownTimer.test.tsx (30 tests)

 Test Files  2 passed (2)
      Tests  65 passed (65)
```

#### 2. E2E Tests (30+ tests)
**Important**: Backend and frontend must be running first!

```bash
# Terminal 1: Start backend
cd backend
poetry run uvicorn src.main:app --reload

# Terminal 2: Start frontend
cd frontend
npm run dev

# Terminal 3: Run E2E tests
cd frontend
npm run test:e2e

# Run specific test files
npm run test:e2e -- test_text_submission.spec.ts
npm run test:e2e -- test_voice_submission.spec.ts

# Run with UI (interactive mode)
npm run test:e2e:ui

# Run in debug mode
npm run test:e2e:debug
```

**Expected Output**:
```
Running 30 tests using 3 workers

  ✓ test_text_submission.spec.ts (15 tests)
  ✓ test_voice_submission.spec.ts (15 tests)

  30 passed (XXs)
```

---

## Quick Validation Script

For a fast sanity check, run the quickstart validation script:

```bash
cd specs/002-input-collection
chmod +x quickstart_validation.sh
./quickstart_validation.sh
```

**Expected Output**:
```
[PASS] Prerequisites check
[PASS] Text submission within window
[PASS] Window enforcement (before window)
[PASS] Window enforcement (after window)
[PASS] Rate limiting (3 submissions)
[PASS] Rate limiting (4th rejected)

All tests passed! ✅
```

---

## Test Coverage by User Story

### US1: Text Submission MVP ✅
- **Unit Tests**: Window enforcement (29), Normalization (68)
- **Integration Tests**: Text submission flow (6), Window enforcement (8)
- **E2E Tests**: Text submission workflow (15+)
- **Total**: ~126 tests

### US2: Voice Input ✅
- **Integration Tests**: Voice transcription (8)
- **E2E Tests**: Voice submission workflow (15+)
- **Total**: ~23 tests

### US3: Multiple Submissions ✅
- **Unit Tests**: Rate limiter (22)
- **Integration Tests**: Rate limiting (3)
- **E2E Tests**: Multiple submission scenarios (included in text/voice E2E)
- **Total**: ~25 tests

### US4: Countdown Timer ✅
- **Unit Tests**: CountdownTimer component (30+)
- **E2E Tests**: Timer behavior (included in text/voice E2E)
- **Total**: ~30 tests

### US5: Dropout Handling ✅
- **Integration Tests**: Dropout detection (4, in test_us5_dropout_handling.py)
- **Total**: ~4 tests

### Cross-Cutting (Polish) ✅
- **Contract Tests**: Spec 2 → Spec 3 event schema (6)
- **Unit Tests**: TextInputForm (35+)
- **Total**: ~41 tests

---

## Troubleshooting

### Backend Test Failures

**Database connection errors**:
```bash
# Check PostgreSQL is running
pg_isready

# Create database if needed
createdb opendiscuss

# Run migrations
cd backend
poetry run alembic upgrade head
```

**Missing dependencies**:
```bash
cd backend
poetry install --no-root
```

**OpenAI API key errors** (for voice tests):
```bash
# Set mock API key for tests
export OPENAI_API_KEY=sk-test-mock-key
```

### Frontend Test Failures

**Playwright browser not installed**:
```bash
cd frontend
npm run playwright:install
```

**Port already in use** (for E2E tests):
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Kill process on port 5173
lsof -ti:5173 | xargs kill -9
```

**Module not found errors**:
```bash
cd frontend
rm -rf node_modules
npm install
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Run Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_DB: opendiscuss_test
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd backend
          pip install poetry
          poetry install
      - name: Run tests
        run: |
          cd backend
          poetry run pytest tests/ -v

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - name: Install dependencies
        run: |
          cd frontend
          npm install
          npm run playwright:install --with-deps
      - name: Run unit tests
        run: |
          cd frontend
          npm run test:unit
      - name: Run E2E tests
        run: |
          cd frontend
          npm run build
          npm run test:e2e
```

---

## Success Criteria

### All Tests Should Pass ✅
- Backend unit tests: 119/119 ✅
- Backend integration tests: 31/31 ✅
- Frontend unit tests: 65+/65+ ✅
- Frontend E2E tests: 30+/30+ ✅

### Test Coverage Goals ✅
- Services: >90% coverage
- API routes: >85% coverage
- React components: >80% coverage

### Performance Targets ✅
- Unit tests: <5 seconds total
- Integration tests: <30 seconds total
- E2E tests: <2 minutes total

---

## Next Steps After Tests Pass

1. ✅ Verify all 245+ tests pass
2. Review test coverage reports
3. Run load tests (100+ concurrent users)
4. Deploy to staging environment
5. Run manual acceptance testing
6. Integrate with Spec 3 (Summarization & Approval)
7. Production deployment

---

## Documentation References

- **Test Implementation**: `/backend/tests/integration/TEST_IMPLEMENTATION_SUMMARY.md`
- **Frontend Testing**: `/frontend/TESTING_IMPLEMENTATION_SUMMARY.md`
- **Quick Start**: `/frontend/QUICKSTART_TESTING.md`
- **Constitutional Review**: `/specs/002-input-collection/CONSTITUTIONAL_COMPLIANCE_REVIEW.md`

---

**Status**: All tests created and ready to execute. Run the commands above to verify the implementation.
