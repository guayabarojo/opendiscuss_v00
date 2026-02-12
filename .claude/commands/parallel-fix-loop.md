---
description: Spawn parallel agents to fix multiple failing tests concurrently
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Overview

This command implements a parallel fix loop pattern to efficiently resolve multiple failing tests by spawning independent agent threads. Each agent operates autonomously to diagnose and fix a specific test failure.

## Execution Steps

1. **Initial Test Suite Run**
   - Execute the test suite (pytest, npm test, cargo test, etc.)
   - Capture full output including:
     - Test names
     - Error messages
     - Stack traces
     - File paths
   - Parse and categorize failures

2. **Analyze Failures**
   - Count total failing tests
   - Extract failure details for each test:
     - Test name
     - Test file path
     - Error type (assertion, exception, timeout, etc.)
     - Error message
     - Stack trace
   - Check for resource limits (max 10-15 parallel agents recommended)

3. **Spawn Parallel Fix Agents**
   - For each failing test, create an agent prompt:
     ```
     Fix failing test: {test_name}

     Steps:
     1. Read the test file at {test_file_path}
     2. Understand what the test is checking
     3. Read the error message: {error_message}
     4. Identify the root cause
     5. Fix the implementation code or test code as needed
     6. Run the specific test to verify it passes: {test_command}
     7. Report success or escalate if unable to fix

     Context:
     - Test file: {test_file_path}
     - Error type: {error_type}
     - Stack trace: {stack_trace}
     ```
   - Spawn each agent with background=true for parallel execution
   - Track agent IDs for monitoring

4. **Monitor Progress**
   - Wait for all agents to complete
   - Collect results from each agent:
     - Success: Test fixed and verified
     - Failure: Unable to fix, needs escalation
     - Partial: Fixed but verification failed

5. **Re-run Test Suite**
   - Execute full test suite again
   - Compare results with initial run
   - Identify remaining failures

6. **Iterate if Needed**
   - If failures remain and max iterations not reached (default: 3):
     - Spawn new agents for remaining failures
     - Repeat from step 3
   - If no progress made:
     - Stop and report issues requiring manual intervention

7. **Report Results**
   - Summary of initial failures vs. current state
   - List of tests fixed by each agent
   - List of remaining failures (if any)
   - Suggested next steps

## Exit Conditions

- All tests pass
- Maximum iterations reached (default: 3)
- No progress made in last iteration
- All agents report manual intervention required

## Best Practices

1. **Isolation**: Each agent works independently without coordination
2. **Verification**: Every agent must verify their fix by running the specific test
3. **Subagents**: Agents can spawn subagents for complex multi-file changes
4. **Error Handling**: If an agent cannot fix the issue, it reports back clearly
5. **Resource Limits**: Consider system resources when spawning many agents

## Variations

### Sequential-Parallel Hybrid
- Group related tests
- Fix groups sequentially
- Fix tests within each group in parallel

### Priority-Based
- Spawn agents for critical tests first
- Lower priority tests in subsequent waves

### Dependency-Aware
- Analyze test dependencies
- Fix foundational tests before dependent tests

## Example Workflow

```
1. Run: pytest tests/ --tb=short
   Result: 6 failures detected

2. Spawn 6 parallel agents:
   - Agent 1: Fix test_user_authentication
   - Agent 2: Fix test_data_validation
   - Agent 3: Fix test_api_endpoint
   - Agent 4: Fix test_database_query
   - Agent 5: Fix test_cache_invalidation
   - Agent 6: Fix test_async_handler

3. Wait for agents to complete

4. Re-run: pytest tests/
   Result: 2 failures remain

5. Iteration 2: Spawn 2 agents for remaining failures

6. Final run: pytest tests/
   Result: All tests pass
```

## Notes

- Works best for tests with independent failure causes
- If tests have interdependencies, may need sequential fixing
- Suitable for unit tests, integration tests, and API tests
- Can be adapted for other parallel fix scenarios (linting, type errors, etc.)

## Metrics Tracked

- Number of tests fixed per iteration
- Time to fix each test
- Number of subagents spawned
- Success rate per agent
- Overall time to fix all tests
