#!/bin/bash
# OpenDiscuss Deployment Verification Script

echo "🔍 OpenDiscuss Deployment Verification"
echo "========================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check Backend
echo -e "${BLUE}Checking Backend...${NC}"
BACKEND_HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null)
if echo "$BACKEND_HEALTH" | grep -q "ok"; then
    echo -e "${GREEN}✅ Backend is running${NC}"
    echo "   Response: $BACKEND_HEALTH"
else
    echo -e "${RED}❌ Backend is not responding${NC}"
fi
echo ""

# Check Frontend
echo -e "${BLUE}Checking Frontend...${NC}"
FRONTEND=$(curl -s http://localhost:3000 2>/dev/null | grep -o '<title>.*</title>')
if [ ! -z "$FRONTEND" ]; then
    echo -e "${GREEN}✅ Frontend is running${NC}"
    echo "   Title: $FRONTEND"
else
    echo -e "${RED}❌ Frontend is not responding${NC}"
fi
echo ""

# Check API Documentation
echo -e "${BLUE}Checking API Documentation...${NC}"
API_DOCS=$(curl -s http://localhost:8000/docs 2>/dev/null | grep -o '<title>.*</title>')
if [ ! -z "$API_DOCS" ]; then
    echo -e "${GREEN}✅ API Documentation is accessible${NC}"
    echo "   Title: $API_DOCS"
else
    echo -e "${RED}❌ API Documentation is not accessible${NC}"
fi
echo ""

# Check Database
echo -e "${BLUE}Checking PostgreSQL...${NC}"
if pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PostgreSQL is running${NC}"
else
    echo -e "${RED}❌ PostgreSQL is not responding${NC}"
fi
echo ""

# Check Redis
echo -e "${BLUE}Checking Redis...${NC}"
if redis-cli -h localhost -p 6379 ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Redis is running${NC}"
else
    echo -e "${RED}❌ Redis is not responding${NC}"
fi
echo ""

# Check CORS
echo -e "${BLUE}Checking CORS...${NC}"
CORS_HEADER=$(curl -s -I -X OPTIONS http://localhost:8000/api/v1/clusters \
    -H "Origin: http://localhost:3000" \
    -H "Access-Control-Request-Method: GET" 2>/dev/null | grep -i "access-control-allow-origin")
if echo "$CORS_HEADER" | grep -q "localhost:3000"; then
    echo -e "${GREEN}✅ CORS is configured correctly${NC}"
    echo "   $CORS_HEADER"
else
    echo -e "${RED}❌ CORS is not configured${NC}"
fi
echo ""

# List Available Endpoints
echo -e "${BLUE}Sample API Endpoints:${NC}"
curl -s http://localhost:8000/openapi.json 2>/dev/null | \
    jq -r '.paths | keys[]' 2>/dev/null | head -10
echo ""

echo "========================================"
echo -e "${GREEN}✅ Deployment verification complete!${NC}"
echo ""
echo "Access the application at:"
echo "  • Frontend: http://localhost:3000"
echo "  • API Docs: http://localhost:8000/docs"
echo "  • Health:   http://localhost:8000/health"
