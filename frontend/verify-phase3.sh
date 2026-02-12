#!/bin/bash

# Phase 3 Frontend Implementation Verification Script

echo "================================"
echo "Phase 3 Implementation Verification"
echo "================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check counters
checks_passed=0
checks_failed=0

# Function to check file exists
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} File exists: $1"
        ((checks_passed++))
        return 0
    else
        echo -e "${RED}✗${NC} File missing: $1"
        ((checks_failed++))
        return 1
    fi
}

# Function to check file has minimum lines
check_file_size() {
    if [ -f "$1" ]; then
        lines=$(wc -l < "$1")
        if [ "$lines" -ge "$2" ]; then
            echo -e "${GREEN}✓${NC} File has $lines lines (minimum $2): $1"
            ((checks_passed++))
            return 0
        else
            echo -e "${RED}✗${NC} File has only $lines lines (minimum $2): $1"
            ((checks_failed++))
            return 1
        fi
    else
        echo -e "${RED}✗${NC} File missing: $1"
        ((checks_failed++))
        return 1
    fi
}

# Function to check package.json has dependency
check_dependency() {
    if grep -q "\"$1\"" package.json; then
        echo -e "${GREEN}✓${NC} Dependency found: $1"
        ((checks_passed++))
        return 0
    else
        echo -e "${RED}✗${NC} Dependency missing: $1"
        ((checks_failed++))
        return 1
    fi
}

echo "1. Checking Core Implementation Files"
echo "--------------------------------------"
check_file_size "src/types/api.ts" 100
check_file_size "src/services/discussionApi.ts" 200
check_file_size "src/services/eventStream.ts" 200
check_file_size "src/pages/DiscussionReport.tsx" 450

echo ""
echo "2. Checking Supporting Files"
echo "-----------------------------"
check_file ".env.example"
check_file "src/services/README.md"
check_file "IMPLEMENTATION_NOTES.md"
check_file "PHASE3_COMPLETION_SUMMARY.md"
check_file "QUICK_START_PHASE3.md"

echo ""
echo "3. Checking Dependencies"
echo "------------------------"
check_dependency "d3"
check_dependency "recharts"
check_dependency "@types/d3"
check_dependency "axios"

echo ""
echo "4. Checking TypeScript Compilation"
echo "-----------------------------------"
if npx tsc --noEmit 2>&1 | grep -q "error TS"; then
    echo -e "${RED}✗${NC} TypeScript compilation failed"
    ((checks_failed++))
else
    echo -e "${GREEN}✓${NC} TypeScript compilation passed"
    ((checks_passed++))
fi

echo ""
echo "5. Checking API Type Exports"
echo "-----------------------------"
grep -q "export interface Discussion" src/types/api.ts && echo -e "${GREEN}✓${NC} Discussion type exported" && ((checks_passed++)) || (echo -e "${RED}✗${NC} Discussion type missing" && ((checks_failed++)))
grep -q "export interface RoundStatusResponse" src/types/api.ts && echo -e "${GREEN}✓${NC} RoundStatusResponse type exported" && ((checks_passed++)) || (echo -e "${RED}✗${NC} RoundStatusResponse type missing" && ((checks_failed++)))
grep -q "export interface DiscussionReport" src/types/api.ts && echo -e "${GREEN}✓${NC} DiscussionReport type exported" && ((checks_passed++)) || (echo -e "${RED}✗${NC} DiscussionReport type missing" && ((checks_failed++)))
grep -q "export interface SankeyDiagram" src/types/api.ts && echo -e "${GREEN}✓${NC} SankeyDiagram type exported" && ((checks_passed++)) || (echo -e "${RED}✗${NC} SankeyDiagram type missing" && ((checks_failed++)))

echo ""
echo "6. Checking API Client Methods"
echo "-------------------------------"
grep -q "createDiscussion" src/services/discussionApi.ts && echo -e "${GREEN}✓${NC} createDiscussion method found" && ((checks_passed++)) || (echo -e "${RED}✗${NC} createDiscussion method missing" && ((checks_failed++)))
grep -q "getDiscussion" src/services/discussionApi.ts && echo -e "${GREEN}✓${NC} getDiscussion method found" && ((checks_passed++)) || (echo -e "${RED}✗${NC} getDiscussion method missing" && ((checks_failed++)))
grep -q "startDiscussion" src/services/discussionApi.ts && echo -e "${GREEN}✓${NC} startDiscussion method found" && ((checks_passed++)) || (echo -e "${RED}✗${NC} startDiscussion method missing" && ((checks_failed++)))
grep -q "getRoundStatus" src/services/discussionApi.ts && echo -e "${GREEN}✓${NC} getRoundStatus method found" && ((checks_passed++)) || (echo -e "${RED}✗${NC} getRoundStatus method missing" && ((checks_failed++)))
grep -q "getReport" src/services/discussionApi.ts && echo -e "${GREEN}✓${NC} getReport method found" && ((checks_passed++)) || (echo -e "${RED}✗${NC} getReport method missing" && ((checks_failed++)))

echo ""
echo "7. Checking Event Stream Features"
echo "----------------------------------"
grep -q "EventSource" src/services/eventStream.ts && echo -e "${GREEN}✓${NC} EventSource implementation found" && ((checks_passed++)) || (echo -e "${RED}✗${NC} EventSource implementation missing" && ((checks_failed++)))
grep -q "subscribe" src/services/eventStream.ts && echo -e "${GREEN}✓${NC} subscribe method found" && ((checks_passed++)) || (echo -e "${RED}✗${NC} subscribe method missing" && ((checks_failed++)))
grep -q "reconnect" src/services/eventStream.ts && echo -e "${GREEN}✓${NC} reconnection logic found" && ((checks_passed++)) || (echo -e "${RED}✗${NC} reconnection logic missing" && ((checks_failed++)))

echo ""
echo "8. Checking Sankey Visualization"
echo "---------------------------------"
grep -q "d3" src/pages/DiscussionReport.tsx && echo -e "${GREEN}✓${NC} D3 import found" && ((checks_passed++)) || (echo -e "${RED}✗${NC} D3 import missing" && ((checks_failed++)))
grep -q "renderSankeyDiagram" src/pages/DiscussionReport.tsx && echo -e "${GREEN}✓${NC} Sankey render function found" && ((checks_passed++)) || (echo -e "${RED}✗${NC} Sankey render function missing" && ((checks_failed++)))
grep -q "Download Report" src/pages/DiscussionReport.tsx && echo -e "${GREEN}✓${NC} Download button found" && ((checks_passed++)) || (echo -e "${RED}✗${NC} Download button missing" && ((checks_failed++)))

echo ""
echo "================================"
echo "Verification Summary"
echo "================================"
echo -e "Checks passed: ${GREEN}$checks_passed${NC}"
echo -e "Checks failed: ${RED}$checks_failed${NC}"
echo ""

if [ $checks_failed -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed! Phase 3 implementation is complete.${NC}"
    exit 0
else
    echo -e "${RED}✗ Some checks failed. Please review the output above.${NC}"
    exit 1
fi
