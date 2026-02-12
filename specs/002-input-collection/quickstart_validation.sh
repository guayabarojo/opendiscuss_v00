#!/bin/bash
#
# Quickstart Validation Script for Input Collection Protocol (Spec 002)
#
# Purpose: Executes examples from quickstart.md and verifies expected outputs
# Usage: ./quickstart_validation.sh
# Requirements:
#   - Backend running on localhost:8000
#   - PostgreSQL database initialized
#   - curl, jq installed
#
# Constitutional Compliance:
# - Temporal Transparency: Validates timing constraints
# - Parallel-First: Tests independent submission handling
# - Synchronous Deliberation: Verifies window enforcement
#
# Exit codes:
#   0 - All tests passed
#   1 - One or more tests failed
#   2 - Setup/prerequisites failed

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
API_BASE="http://localhost:8000/api/v1"
PASSED=0
FAILED=0

# Utility functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

assert_status() {
    local expected=$1
    local actual=$2
    local test_name=$3

    if [ "$expected" -eq "$actual" ]; then
        log_info "✓ $test_name - Status code $actual"
        PASSED=$((PASSED + 1))
        return 0
    else
        log_error "✗ $test_name - Expected $expected, got $actual"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

assert_json_field() {
    local json=$1
    local field=$2
    local expected=$3
    local test_name=$4

    local actual=$(echo "$json" | jq -r ".$field")

    if [ "$actual" = "$expected" ]; then
        log_info "✓ $test_name - Field '$field' = $expected"
        PASSED=$((PASSED + 1))
        return 0
    else
        log_error "✗ $test_name - Field '$field': expected $expected, got $actual"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

assert_json_field_exists() {
    local json=$1
    local field=$2
    local test_name=$3

    local actual=$(echo "$json" | jq -r ".$field")

    if [ "$actual" != "null" ] && [ -n "$actual" ]; then
        log_info "✓ $test_name - Field '$field' exists"
        PASSED=$((PASSED + 1))
        return 0
    else
        log_error "✗ $test_name - Field '$field' does not exist"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

# Prerequisites check
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check curl
    if ! command -v curl &> /dev/null; then
        log_error "curl not found. Please install curl."
        exit 2
    fi

    # Check jq
    if ! command -v jq &> /dev/null; then
        log_error "jq not found. Please install jq for JSON parsing."
        exit 2
    fi

    # Check backend health
    if ! curl -s -f "$API_BASE/../health" > /dev/null 2>&1; then
        log_error "Backend not reachable at $API_BASE. Please start the backend server."
        exit 2
    fi

    log_info "Prerequisites OK"
}

# Generate test UUIDs
DISCUSSION_ID="d1234567-89ab-cdef-0123-456789abcdef"
PARTICIPANT_ID_1="p1234567-89ab-cdef-0123-456789abcdef"
PARTICIPANT_ID_2="p2345678-89ab-cdef-0123-456789abcdef"

# Test Scenario 1: Submit Text Input
test_scenario_1() {
    log_info "\n=== Scenario 1: Submit Text Input ==="

    # Step 1: Create a round (simulating Spec 1)
    log_info "Creating test round..."

    # Calculate time window: current time + 1 minute to + 6 minutes
    WINDOW_START=$(date -u -d "+1 minute" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -v +1M +"%Y-%m-%dT%H:%M:%SZ")
    WINDOW_END=$(date -u -d "+6 minutes" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -v +6M +"%Y-%m-%dT%H:%M:%SZ")

    CREATE_ROUND_RESPONSE=$(curl -s -X POST "$API_BASE/rounds" \
        -H "Content-Type: application/json" \
        -d "{
            \"discussion_id\": \"$DISCUSSION_ID\",
            \"round_number\": 1,
            \"window_start\": \"$WINDOW_START\",
            \"window_end\": \"$WINDOW_END\"
        }")

    ROUND_ID=$(echo "$CREATE_ROUND_RESPONSE" | jq -r '.round_id')

    if [ "$ROUND_ID" = "null" ] || [ -z "$ROUND_ID" ]; then
        log_error "Failed to create round"
        return 1
    fi

    log_info "Round created: $ROUND_ID"

    # Step 2: Get window status
    log_info "Checking window status..."

    WINDOW_RESPONSE=$(curl -s -w "\n%{http_code}" "$API_BASE/rounds/$ROUND_ID/window")
    WINDOW_STATUS=$(echo "$WINDOW_RESPONSE" | tail -n1)
    WINDOW_JSON=$(echo "$WINDOW_RESPONSE" | head -n-1)

    assert_status 200 "$WINDOW_STATUS" "Get window status"
    assert_json_field_exists "$WINDOW_JSON" "round_id" "Window response has round_id"
    assert_json_field_exists "$WINDOW_JSON" "window_start" "Window response has window_start"
    assert_json_field_exists "$WINDOW_JSON" "is_open" "Window response has is_open"

    # Step 3: Submit text (will be accepted since we're within window)
    log_info "Submitting text..."

    SUBMIT_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/submissions" \
        -H "Content-Type: application/json" \
        -d "{
            \"participant_id\": \"$PARTICIPANT_ID_1\",
            \"round_id\": \"$ROUND_ID\",
            \"text\": \"I think we should prioritize accessibility features.\",
            \"modality\": \"TEXT\"
        }")

    SUBMIT_STATUS=$(echo "$SUBMIT_RESPONSE" | tail -n1)
    SUBMIT_JSON=$(echo "$SUBMIT_RESPONSE" | head -n-1)

    assert_status 201 "$SUBMIT_STATUS" "Submit text input"
    assert_json_field_exists "$SUBMIT_JSON" "submission_id" "Submission response has submission_id"
    assert_json_field "$SUBMIT_JSON" "modality" "TEXT" "Submission modality is TEXT"
    assert_json_field "$SUBMIT_JSON" "counted" "false" "Initial counted status is false"
}

# Test Scenario 3: Window Enforcement
test_scenario_3() {
    log_info "\n=== Scenario 3: Window Enforcement ==="

    # Create a round with past window (already closed)
    log_info "Creating round with past window..."

    PAST_START=$(date -u -d "-10 minutes" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -v -10M +"%Y-%m-%dT%H:%M:%SZ")
    PAST_END=$(date -u -d "-5 minutes" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -v -5M +"%Y-%m-%dT%H:%M:%SZ")

    CREATE_PAST_ROUND=$(curl -s -X POST "$API_BASE/rounds" \
        -H "Content-Type: application/json" \
        -d "{
            \"discussion_id\": \"$DISCUSSION_ID\",
            \"round_number\": 2,
            \"window_start\": \"$PAST_START\",
            \"window_end\": \"$PAST_END\"
        }")

    PAST_ROUND_ID=$(echo "$CREATE_PAST_ROUND" | jq -r '.round_id')

    if [ "$PAST_ROUND_ID" = "null" ] || [ -z "$PAST_ROUND_ID" ]; then
        log_error "Failed to create past round"
        return 1
    fi

    log_info "Past round created: $PAST_ROUND_ID"

    # Attempt submission after window closed
    log_info "Attempting submission after window closed..."

    LATE_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/submissions" \
        -H "Content-Type: application/json" \
        -d "{
            \"participant_id\": \"$PARTICIPANT_ID_1\",
            \"round_id\": \"$PAST_ROUND_ID\",
            \"text\": \"Late submission attempt.\",
            \"modality\": \"TEXT\"
        }")

    LATE_STATUS=$(echo "$LATE_RESPONSE" | tail -n1)
    LATE_JSON=$(echo "$LATE_RESPONSE" | head -n-1)

    assert_status 422 "$LATE_STATUS" "Reject submission after window"

    # Check error response
    ERROR_CODE=$(echo "$LATE_JSON" | jq -r '.detail.error_code')
    if [ "$ERROR_CODE" = "OUTSIDE_WINDOW" ]; then
        log_info "✓ Correct error code: OUTSIDE_WINDOW"
        PASSED=$((PASSED + 1))
    else
        log_error "✗ Expected OUTSIDE_WINDOW error, got: $ERROR_CODE"
        FAILED=$((FAILED + 1))
    fi
}

# Test Scenario 4: Rate Limiting
test_scenario_4() {
    log_info "\n=== Scenario 4: Rate Limiting ==="

    # Create a round for rate limit testing
    log_info "Creating round for rate limit test..."

    RATE_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u +"%Y-%m-%dT%H:%M:%SZ")
    RATE_END=$(date -u -d "+10 minutes" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -v +10M +"%Y-%m-%dT%H:%M:%SZ")

    CREATE_RATE_ROUND=$(curl -s -X POST "$API_BASE/rounds" \
        -H "Content-Type: application/json" \
        -d "{
            \"discussion_id\": \"$DISCUSSION_ID\",
            \"round_number\": 3,
            \"window_start\": \"$RATE_START\",
            \"window_end\": \"$RATE_END\"
        }")

    RATE_ROUND_ID=$(echo "$CREATE_RATE_ROUND" | jq -r '.round_id')

    if [ "$RATE_ROUND_ID" = "null" ] || [ -z "$RATE_ROUND_ID" ]; then
        log_error "Failed to create rate limit test round"
        return 1
    fi

    log_info "Rate limit test round created: $RATE_ROUND_ID"

    # Submit 3 times (should all succeed)
    for i in 1 2 3; do
        log_info "Submission attempt $i..."

        SUB_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/submissions" \
            -H "Content-Type: application/json" \
            -d "{
                \"participant_id\": \"$PARTICIPANT_ID_2\",
                \"round_id\": \"$RATE_ROUND_ID\",
                \"text\": \"Submission attempt $i\",
                \"modality\": \"TEXT\"
            }")

        SUB_STATUS=$(echo "$SUB_RESPONSE" | tail -n1)

        assert_status 201 "$SUB_STATUS" "Rate limit - submission $i accepted"

        sleep 0.5  # Brief delay between submissions
    done

    # 4th submission should be rejected
    log_info "Attempting 4th submission (should be rejected)..."

    FOURTH_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/submissions" \
        -H "Content-Type: application/json" \
        -d "{
            \"participant_id\": \"$PARTICIPANT_ID_2\",
            \"round_id\": \"$RATE_ROUND_ID\",
            \"text\": \"Fourth submission attempt\",
            \"modality\": \"TEXT\"
        }")

    FOURTH_STATUS=$(echo "$FOURTH_RESPONSE" | tail -n1)
    FOURTH_JSON=$(echo "$FOURTH_RESPONSE" | head -n-1)

    assert_status 429 "$FOURTH_STATUS" "Reject 4th submission (rate limit)"

    # Check error response
    ERROR_CODE=$(echo "$FOURTH_JSON" | jq -r '.detail.error_code')
    if [ "$ERROR_CODE" = "TOO_MANY_REQUESTS" ]; then
        log_info "✓ Correct error code: TOO_MANY_REQUESTS"
        PASSED=$((PASSED + 1))
    else
        log_error "✗ Expected TOO_MANY_REQUESTS error, got: $ERROR_CODE"
        FAILED=$((FAILED + 1))
    fi

    # Verify submission history
    log_info "Checking submission history..."

    HISTORY_RESPONSE=$(curl -s -w "\n%{http_code}" \
        "$API_BASE/submissions/participant/$PARTICIPANT_ID_2/round/$RATE_ROUND_ID")

    HISTORY_STATUS=$(echo "$HISTORY_RESPONSE" | tail -n1)
    HISTORY_JSON=$(echo "$HISTORY_RESPONSE" | head -n-1)

    assert_status 200 "$HISTORY_STATUS" "Get submission history"

    TOTAL_COUNT=$(echo "$HISTORY_JSON" | jq -r '.total_count')
    if [ "$TOTAL_COUNT" = "3" ]; then
        log_info "✓ Submission history shows 3 submissions"
        PASSED=$((PASSED + 1))
    else
        log_error "✗ Expected 3 submissions in history, got: $TOTAL_COUNT"
        FAILED=$((FAILED + 1))
    fi

    CAN_SUBMIT=$(echo "$HISTORY_JSON" | jq -r '.can_submit_more')
    if [ "$CAN_SUBMIT" = "false" ]; then
        log_info "✓ can_submit_more is false"
        PASSED=$((PASSED + 1))
    else
        log_error "✗ Expected can_submit_more=false, got: $CAN_SUBMIT"
        FAILED=$((FAILED + 1))
    fi
}

# Main execution
main() {
    log_info "Starting Input Collection Protocol Validation"
    log_info "API Base: $API_BASE"

    check_prerequisites

    test_scenario_1
    test_scenario_3
    test_scenario_4

    # Summary
    echo ""
    echo "========================================"
    echo "Test Results"
    echo "========================================"
    log_info "Passed: $PASSED"

    if [ $FAILED -gt 0 ]; then
        log_error "Failed: $FAILED"
        exit 1
    else
        log_info "All tests passed!"
        exit 0
    fi
}

# Run main function
main
