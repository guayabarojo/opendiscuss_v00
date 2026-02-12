# Parallel Fix Loop Skill

Use this pattern to fix multiple failing tests in parallel by spawning independent agent threads.

## Pattern Overview

This skill enables efficient resolution of multiple failing tests by leveraging parallel agent execution. Each agent operates independently to diagnose and fix a specific test failure.

## Workflow

1. **Run Test Suite and Capture Failures**
   - Execute the full test suite
   - Parse output to identify all failing tests
   - Extract test names and error messages

2. **Spawn Parallel Fix Agents**
   - For each failing test, spawn a general-purpose agent with:
     - **Prompt**: "Fix {test_name}: Read test file, understand the issue, fix code/test, verify it passes"
     - **Background**: true (enables parallel execution)
     - **Context**: Include relevant error message and stack trace

3. **Wait for Completion**
   - Monitor all agent threads
   - Collect results from each agent

4. **Re-run Test Suite**
   - Execute full test suite again
   - Check if failures persist

5. **Iterate if Needed**
   - If failures remain, spawn new agents for remaining failures
   - Repeat until all tests pass or maximum iterations reached

## Example Usage

### Scenario: 6 Failing Tests

```bash
# Initial test run shows 6 failures
pytest tests/ --tb=short

# Spawn 6 parallel agents (one per failure)
# Agent 1: Fix test_user_authentication
# Agent 2: Fix test_data_validation
# Agent 3: Fix test_api_endpoint
# Agent 4: Fix test_database_query
# Agent 5: Fix test_cache_invalidation
# Agent 6: Fix test_async_handler

# Each agent can spawn subagents if needed for complex fixes
```

## Agent Prompt Template

```text
Fix failing test: {test_name}

Steps:
1. Read the test file at {test_file_path}
2. Understand what the test is checking
3. Read the error message:
   {error_message}
4. Identify the root cause
5. Fix the implementation code or test code as needed
6. Run the specific test to verify it passes: pytest {test_file_path}::{test_name}
7. Report success or escalate if unable to fix

Context:
- Test file: {test_file_path}
- Error type: {error_type}
- Stack trace: {stack_trace}
```

## Best Practices

1. **Isolation**: Each agent should work independently without coordinating with others
2. **Verification**: Every agent must verify their fix by running the specific test
3. **Subagents**: Agents can spawn subagents for complex multi-file changes
4. **Error Handling**: If an agent cannot fix the issue, it should report back clearly
5. **Resource Limits**: Consider system resources when spawning many agents (recommend max 10-15 parallel)

## Implementation Notes

- Works best for tests with independent failure causes
- If tests have interdependencies, may need sequential fixing
- Suitable for unit tests, integration tests, and API tests
- Can be adapted for other parallel fix scenarios (linting errors, type errors, etc.)

## Variations

### Sequential with Parallelism Hybrid
- Group related tests
- Fix groups sequentially
- Fix tests within each group in parallel

### Priority-Based
- Spawn agents for critical tests first
- Lower priority tests in subsequent waves

### Dependency-Aware
- Analyze test dependencies
- Fix foundational tests before dependent tests

## Exit Conditions

- All tests pass
- Maximum iterations reached (default: 3)
- No progress made in last iteration
- Manual intervention required flag set by multiple agents

## Metrics to Track

- Number of tests fixed per iteration
- Time to fix each test
- Number of subagents spawned
- Success rate per agent
- Overall time to fix all tests
