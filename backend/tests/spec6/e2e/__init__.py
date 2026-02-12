"""
End-to-end tests for Question Progression Protocol with real Claude API.

Tests require --e2e flag and CLAUDE_API_KEY environment variable.

Tests:
- test_real_generation.py: Real LLM generation with performance validation
  - Complete host-defined discussion workflow
  - Complete auto-generated discussion workflow
  - Auto-generation latency (p95 < 10s)
"""
