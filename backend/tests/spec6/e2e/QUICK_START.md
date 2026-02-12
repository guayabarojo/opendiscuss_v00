# Quick Start: E2E Tests

## Setup (One-time)

```bash
# 1. Set API key
export ANTHROPIC_API_KEY="your-api-key-here"

# 2. Ensure services are running
docker-compose up -d postgres redis

# 3. Apply migrations
cd backend
alembic upgrade head
```

## Running Tests

### Run All E2E Tests
```bash
# From backend directory
pytest tests/spec6/e2e/ --e2e -v
```

### Run Specific Test
```bash
# T093: Real Claude API test
pytest tests/spec6/e2e/test_real_generation.py::test_real_claude_api_question_generation --e2e -v

# T094: HOST_DEFINED flow
pytest tests/spec6/e2e/test_real_generation.py::test_complete_host_defined_discussion_e2e --e2e -v

# T095: AUTO_GENERATED flow
pytest tests/spec6/e2e/test_real_generation.py::test_complete_auto_generated_discussion_e2e --e2e -v

# T096: Performance test
pytest tests/spec6/e2e/test_real_generation.py::test_auto_generation_latency_performance --e2e -v
```

### Run Without E2E Flag (Tests Skipped)
```bash
# E2E tests will be skipped automatically
pytest tests/spec6/e2e/ -v
```

## Expected Output

### Success
```
tests/spec6/e2e/test_real_generation.py::test_real_claude_api_question_generation PASSED
✓ Generated question: What strategies can we implement to address funding constraints?
✓ Latency: 6.23s
✓ Provenance: model=claude-sonnet-4-5, tokens=520+45, retries=0, validation_attempts=1
```

### Performance Test Output
```
================================================================================
Performance Test: Auto-Generation Latency
================================================================================

Generating 10 questions to measure latency...

  Generation 1/10: 5.87s - What strategies can we implement to address...
  Generation 2/10: 6.23s - How can we improve communication channels...
  ...

--------------------------------------------------------------------------------
Latency Distribution:
--------------------------------------------------------------------------------
  Successful generations: 10/10
  Mean:    6.23s
  Median:  5.87s
  Min:     4.12s
  Max:     9.45s
  p95:     8.92s
  p99:     9.45s
--------------------------------------------------------------------------------
✓ p95 latency 8.92s < 10s threshold
✓ p99 latency 9.45s < 30s threshold
================================================================================
```

## Troubleshooting

### Error: "ANTHROPIC_API_KEY environment variable not set"
```bash
export ANTHROPIC_API_KEY="your-api-key"
```

### Error: Tests are skipped
```bash
# Add --e2e flag
pytest tests/spec6/e2e/ --e2e -v
```

### Error: Connection refused (PostgreSQL)
```bash
# Start services
docker-compose up -d postgres redis
```

### Error: Rate limit exceeded
```bash
# Wait 60 seconds and retry
sleep 60
pytest tests/spec6/e2e/ --e2e -v
```

## Cost Monitoring

- Each full E2E test run: **~$0.10**
- T096 (10 generations): **~$0.03**
- Individual tests: **~$0.01-0.03**

**Tip**: Run E2E tests sparingly to control costs.

## Next Steps

After E2E tests pass:
1. Review performance metrics
2. Run full test suite: `pytest tests/spec6/ -v`
3. Check test coverage: `pytest tests/spec6/ --cov=src.question_progression`
