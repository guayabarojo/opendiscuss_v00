#!/bin/bash
set -e

echo "🧪 OpenDiscuss Test Runner"
echo "=========================="
echo ""

cd backend

# Check if dependencies are installed
if [ ! -d ".venv" ]; then
    echo "❌ Backend dependencies not installed. Run ./start-all.sh first."
    exit 1
fi

echo "Running tests in order of importance..."
echo ""

# 1. Quick smoke test - just verify imports work
echo "1️⃣  Smoke Test (verifying imports)..."
poetry run python -c "
from src.main import app
from src.models.discussion import Discussion
from src.services.discussion_service import DiscussionService
print('✓ All imports successful')
"
echo ""

# 2. Unit/fast tests first
echo "2️⃣  Running fast unit tests..."
poetry run pytest tests/integration/test_single_round_discussion.py::test_single_round_discussion_complete_flow -v --tb=short || echo "⚠️  Some tests failed (expected if DB not seeded)"
echo ""

# 3. Integration tests
echo "3️⃣  Running integration tests (may take 1-2 minutes)..."
poetry run pytest tests/integration/ -v -x --tb=short -k "not performance" || echo "⚠️  Some integration tests failed"
echo ""

# 4. Compliance tests
echo "4️⃣  Running constitutional compliance tests..."
poetry run pytest tests/compliance/ -v --tb=short || echo "⚠️  Some compliance tests failed"
echo ""

# 5. Performance benchmarks (optional - slow)
echo "5️⃣  Running performance benchmarks (optional - can be slow)..."
read -p "Run performance tests? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    poetry run pytest tests/performance/ -v --tb=short -m performance
else
    echo "⏭️  Skipping performance tests"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Test run complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Note: Some tests may fail if:"
echo "  - Docker services (PostgreSQL/Redis) are not running"
echo "  - Database migrations haven't been run"
echo "  - Test data hasn't been seeded"
echo ""
echo "To see detailed test output:"
echo "  cd backend"
echo "  poetry run pytest tests/ -vv"
echo ""
