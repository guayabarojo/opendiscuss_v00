# E2E Tests Setup

## Prerequisites
1. Set ANTHROPIC_API_KEY environment variable
2. Start PostgreSQL and Redis
3. Apply all migrations

## Running E2E Tests
```bash
pytest tests/spec6/e2e/ --e2e -v
```

## Cost Warning
E2E tests make real Claude API calls (~$0.10 per test run)

## Test Coverage
- **test_real_generation.py**: Real Claude API integration tests
  - T093: Real question generation with Claude
  - T094: Complete HOST_DEFINED discussion flow
  - T095: Complete AUTO_GENERATED discussion flow
  - T096: Auto-generation latency performance test

## Environment Variables
- `ANTHROPIC_API_KEY`: Required for all E2E tests
- `DATABASE_URL`: PostgreSQL connection string (defaults to test database)
- `REDIS_URL`: Redis connection string (defaults to test Redis DB)

## Performance Metrics
- p95 latency < 10 seconds (Sankey complete → question ready)
- p99 latency < 30 seconds
- Question validation < 10ms
- Sequence query < 5ms (indexed)

## Notes
- E2E tests are skipped by default (require --e2e flag)
- Tests use real external services (Claude API, PostgreSQL, Redis)
- Each test run costs approximately $0.10 in API credits
- Tests may take 5-10 minutes to complete due to LLM calls
