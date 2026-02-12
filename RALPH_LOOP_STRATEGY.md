# Ralph Loop - Autonomous Test-Fix-Iterate Strategy

**Purpose**: Continuously run tests, fix failures, and iterate until 100% pass rate achieved.

**Created**: 2026-01-31
**Project**: Spec 006 - Question Progression Protocol
**Status**: Ready to execute after implementation phases complete

---

## Overview

The Ralph Loop is an autonomous, iterative testing and fixing cycle that:
1. Runs the complete test suite
2. Analyzes all failures with detailed diagnostics
3. **Fixes the code** to address each failure
4. Re-runs tests to verify fixes
5. **Repeats until all tests pass** (100% pass rate)
6. Performs user acceptance testing with /mcp and Playwright

---

## Ralph Loop Phases

### Phase A: Unit Test Fixing Loop

**Target**: `backend/tests/spec6/unit/`

**Process**:
```
ITERATION = 1
while unit_tests_have_failures():
    print(f"Ralph Loop Iteration {ITERATION} - Unit Tests")

    # 1. Run unit tests
    results = run_tests("backend/tests/spec6/unit/", verbose=True)

    # 2. If all pass, break
    if results.all_passed:
        break

    # 3. Analyze failures
    failures = parse_test_failures(results)
    for failure in failures:
        - Identify failing test name
        - Extract stack trace
        - Identify source file and line
        - Determine root cause

    # 4. Fix code
    for failure in failures:
        - Read implementation file
        - Identify bug/issue
        - Modify code to fix issue
        - Verify syntax

    # 5. Re-run affected tests
    verify_fixes(affected_tests)

    # 6. Increment and continue
    ITERATION += 1
```

**Success Criteria**: All unit tests pass (0 failures)

---

### Phase B: Integration Test Fixing Loop

**Target**: `backend/tests/spec6/integration/`

**Process**:
```
ITERATION = 1
while integration_tests_have_failures():
    print(f"Ralph Loop Iteration {ITERATION} - Integration Tests")

    # 1. Run integration tests (requires database + Redis)
    results = run_tests("backend/tests/spec6/integration/", verbose=True)

    # 2. If all pass, break
    if results.all_passed:
        break

    # 3. Analyze failures
    failures = parse_test_failures(results)
    for failure in failures:
        - Check database connection issues
        - Check API endpoint failures
        - Check service layer integration
        - Check event bus communication

    # 4. Fix code
    for failure in failures:
        - Fix database queries/migrations
        - Fix API endpoint logic
        - Fix service integration
        - Fix async/await issues

    # 5. Re-run affected tests
    verify_fixes(affected_tests)

    ITERATION += 1
```

**Success Criteria**: All integration tests pass (0 failures)

---

### Phase C: Contract Test Fixing Loop

**Target**: `backend/tests/spec6/contract/`

**Process**:
```
ITERATION = 1
while contract_tests_have_failures():
    print(f"Ralph Loop Iteration {ITERATION} - Contract Tests")

    # 1. Run contract tests (API + Event schema validation)
    results = run_tests("backend/tests/spec6/contract/", verbose=True)

    # 2. If all pass, break
    if results.all_passed:
        break

    # 3. Analyze failures
    failures = parse_test_failures(results)
    for failure in failures:
        - Check OpenAPI schema violations
        - Check AsyncAPI schema violations
        - Check response field mismatches
        - Check event payload mismatches

    # 4. Fix code
    for failure in failures:
        - Fix API response schemas
        - Fix event payload structures
        - Update Pydantic models
        - Add missing fields

    # 5. Re-run affected tests
    verify_fixes(affected_tests)

    ITERATION += 1
```

**Success Criteria**: All API and event contracts validated (0 failures)

---

### Phase D: E2E Test Fixing Loop

**Target**: `backend/tests/spec6/e2e/`

**Process**:
```
ITERATION = 1
while e2e_tests_have_failures():
    print(f"Ralph Loop Iteration {ITERATION} - E2E Tests")

    # 1. Run E2E tests (requires CLAUDE_API_KEY, real services)
    results = run_tests("backend/tests/spec6/e2e/", args="--e2e", verbose=True)

    # 2. If all pass, break
    if results.all_passed:
        break

    # 3. Analyze failures
    failures = parse_test_failures(results)
    for failure in failures:
        - Check Claude API integration issues
        - Check LLM prompt effectiveness
        - Check timeout handling
        - Check retry logic
        - Check validation with real responses

    # 4. Fix code
    for failure in failures:
        - Fix Claude API client configuration
        - Improve LLM prompts for better outputs
        - Adjust timeouts if needed
        - Fix retry/backoff logic
        - Handle real API edge cases

    # 5. Re-run affected tests
    verify_fixes(affected_tests)

    ITERATION += 1
```

**Success Criteria**: All E2E tests pass with real Claude API (0 failures)

---

### Phase E: User Acceptance Testing

**Target**: End-to-end user workflows with /mcp and Playwright

**Process**:
```
ITERATION = 1
while user_tests_have_failures():
    print(f"Ralph Loop Iteration {ITERATION} - User Acceptance")

    # 1. Setup /mcp server
    start_mcp_server()

    # 2. Run Playwright tests
    results = run_playwright_tests()

    # 3. If all pass, break
    if results.all_passed:
        break

    # 4. Analyze failures
    failures = parse_playwright_failures(results)
    for failure in failures:
        - Check UI interaction issues
        - Check API response delays
        - Check user flow interruptions
        - Check error message clarity

    # 5. Fix code
    for failure in failures:
        - Fix API performance issues
        - Improve error messages
        - Fix edge cases in user flows
        - Improve UX based on test feedback

    # 6. Re-run affected tests
    verify_fixes(affected_tests)

    ITERATION += 1
```

**Success Criteria**: All user workflows complete successfully

---

## Ralph Loop Agent Configuration

### Agent Characteristics

**Autonomous**: Runs without human intervention until complete
**Persistent**: Continues iterating until 100% pass rate
**Diagnostic**: Deep analysis of each failure
**Surgical**: Targeted fixes to specific issues
**Verifying**: Re-tests after each fix
**Documenting**: Logs all changes made

### Agent Tools Available

- **Bash**: Run pytest, check output, grep failures
- **Read**: Analyze test code, implementation code, stack traces
- **Edit**: Fix implementation code surgically
- **Write**: Create new fixes if needed
- **Grep**: Search for error patterns
- **Task**: Spawn sub-agents for complex fixes if needed

### Fix Strategy

**Priority Order**:
1. Syntax errors (highest priority - breaks compilation)
2. Import errors (blocks test execution)
3. Database/connection errors (blocks integration tests)
4. Logic errors (incorrect behavior)
5. Validation errors (schema mismatches)
6. Performance issues (timeouts, slow responses)
7. Edge cases (rare scenarios)

**Fix Approach**:
- **Minimal changes**: Fix only what's needed
- **Test-driven**: Fix to make test pass
- **Verify**: Run affected tests immediately
- **Document**: Log what was changed and why
- **Iterate**: If fix introduces new failures, address them

---

## Execution Plan

### Pre-Ralph Loop Setup

Before starting ralph loop, ensure:
- [x] All implementation phases complete (1-11)
- [x] Database migrations applied
- [x] Redis server running
- [x] Environment variables configured (CLAUDE_API_KEY)
- [x] Dependencies installed (poetry install)
- [x] All source code syntax-valid

### Ralph Loop Execution Order

1. **Phase A**: Unit Tests (fastest, no external deps)
2. **Phase B**: Integration Tests (needs DB + Redis)
3. **Phase C**: Contract Tests (schema validation)
4. **Phase D**: E2E Tests (real Claude API)
5. **Phase E**: User Acceptance (Playwright)

**Rationale**: Fix from foundation → integration → contracts → real API → user experience

### Exit Conditions

**Success Exit**: All phases pass with 0 failures
- Unit tests: 100% pass
- Integration tests: 100% pass
- Contract tests: 100% pass
- E2E tests: 100% pass
- User tests: 100% pass

**Failure Exit** (abort conditions):
- Max iterations exceeded (50 iterations per phase)
- Unfixable errors (syntax impossible to fix, missing dependencies)
- Breaking changes detected (fixes break other passing tests)

In failure exit case: Report status, document remaining issues, suggest manual intervention

---

## Metrics Tracking

### Per Iteration

- **Tests run**: Total count
- **Tests passed**: Count and percentage
- **Tests failed**: Count and percentage
- **Fixes applied**: Number of code modifications
- **Time elapsed**: Duration of iteration

### Overall

- **Total iterations**: Across all phases
- **Total fixes**: Cumulative code modifications
- **Final pass rate**: Percentage (target: 100%)
- **Time to completion**: Total ralph loop duration

---

## Example Ralph Loop Output

```
╔══════════════════════════════════════════════════════════════╗
║              RALPH LOOP - Iteration 1                        ║
║              Phase A: Unit Tests                             ║
╚══════════════════════════════════════════════════════════════╝

[1/3] Running unit tests...
  pytest backend/tests/spec6/unit/ -v

  Results: 77 tests, 72 passed, 5 failed
  Pass rate: 93.5%

[2/3] Analyzing failures...
  ✗ test_validation_starts_with_what - AssertionError line 45
    Root cause: Validator not checking lowercase "what"
    Fix: Add .lower() to opening word check

  ✗ test_sequence_create_with_11_questions - ValidationError
    Root cause: Max questions check uses >= instead of >
    Fix: Change condition to > 10

  ✗ test_question_immutability - AttributeError: 'NoneType'
    Root cause: immutable_since not initialized
    Fix: Set default value in model

  ✗ test_generate_from_sankey - TimeoutError
    Root cause: Mock timeout not configured
    Fix: Add timeout parameter to mock

  ✗ test_provenance_record - IntegrityError
    Root cause: Foreign key constraint violation
    Fix: Create parent Question before Provenance

[3/3] Applying fixes...
  ✓ Fixed backend/src/question_progression/validators.py:45
  ✓ Fixed backend/src/question_progression/services/sequence.py:78
  ✓ Fixed backend/src/question_progression/models.py:123
  ✓ Fixed backend/tests/spec6/unit/test_generation.py:89
  ✓ Fixed backend/tests/spec6/unit/test_provenance.py:34

[4/3] Re-running tests...
  pytest backend/tests/spec6/unit/ -v

  Results: 77 tests, 77 passed, 0 failed
  Pass rate: 100% ✓

╔══════════════════════════════════════════════════════════════╗
║              RALPH LOOP - Phase A Complete                   ║
║              Unit Tests: 100% PASS                           ║
╚══════════════════════════════════════════════════════════════╝

Proceeding to Phase B: Integration Tests...
```

---

## Ralph Loop Documentation

After completion, generate:
- **RALPH_LOOP_REPORT.md**: Summary of all iterations, fixes, final metrics
- **FIXES_APPLIED.md**: Detailed log of every code change made
- **TEST_RESULTS.md**: Final test results from all phases

---

## Status

**Ready to Execute**: After Phases 1-11 complete
**Target**: 100% test pass rate across all test suites
**Approach**: Autonomous, iterative, fix-until-pass
**Duration**: Unknown (continues until complete)

---

**Next Action**: Wait for implementation phases to complete, then launch ralph loop agent.
