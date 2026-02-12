#!/bin/bash

# Phase 3 Verification Script
# Verifies all Phase 3 components are in place

set -e

echo "================================"
echo "Phase 3 Verification Script"
echo "================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counter for checks
PASSED=0
FAILED=0

check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} Found: $1"
        ((PASSED++))
    else
        echo -e "${RED}✗${NC} Missing: $1"
        ((FAILED++))
    fi
}

check_directory() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✓${NC} Found: $1"
        ((PASSED++))
    else
        echo -e "${RED}✗${NC} Missing: $1"
        ((FAILED++))
    fi
}

echo "Checking Phase 3 Implementation Files..."
echo ""

# Core service files
echo "1. Service Layer (T018-T024)"
check_file "backend/src/question_progression/services/sequence.py"
check_file "backend/src/question_progression/services/__init__.py"

# API files
echo ""
echo "2. API Layer (T020-T021, T027)"
check_file "backend/src/question_progression/api/questions.py"
check_file "backend/src/question_progression/api/__init__.py"

# Models and validators (Phase 2, but required)
echo ""
echo "3. Models and Validators (Phase 2 - Required)"
check_file "backend/src/question_progression/models.py"
check_file "backend/src/question_progression/validators.py"

# Integration points
echo ""
echo "4. Integration Points (T025-T026)"
check_file "backend/src/models/round.py"
check_file "backend/src/api/discussion_routes.py"
check_file "backend/src/main.py"

# Test files
echo ""
echo "5. Unit Tests (T018-T024)"
check_file "backend/tests/spec6/unit/test_sequence_service.py"

echo ""
echo "6. Integration Tests (T020-T021)"
check_file "backend/tests/spec6/integration/test_sequence_api.py"

# Documentation
echo ""
echo "7. Documentation"
check_file "PHASE3_IMPLEMENTATION_SUMMARY.md"
check_file "PHASE3_QUICK_REFERENCE.md"
check_file "specs/006-question-progression/tasks.md"

# Test directories
echo ""
echo "8. Test Directory Structure"
check_directory "backend/tests/spec6"
check_directory "backend/tests/spec6/unit"
check_directory "backend/tests/spec6/integration"

echo ""
echo "================================"
echo "Verification Summary"
echo "================================"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ Phase 3 verification PASSED!${NC}"
    echo ""
    echo "All Phase 3 components are in place."
    echo ""
    echo "Next steps:"
    echo "1. Run unit tests: pytest backend/tests/spec6/unit/test_sequence_service.py -v"
    echo "2. Run integration tests: pytest backend/tests/spec6/integration/test_sequence_api.py -v"
    echo "3. Start backend: cd backend && uvicorn src.main:app --reload"
    echo "4. Test endpoints: curl http://localhost:8000/docs"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Phase 3 verification FAILED!${NC}"
    echo ""
    echo "Please check missing files listed above."
    echo ""
    exit 1
fi
