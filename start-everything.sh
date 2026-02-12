#!/bin/bash
# Complete OpenDiscuss Startup Script
# This script will start all services and create sample data

set -e

export PATH="$HOME/.local/bin:$PATH"

echo "🚀 OpenDiscuss Complete Startup"
echo "================================"
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00

# Step 1: Check Docker
echo -e "${BLUE}Step 1: Checking Docker...${NC}"
if docker ps > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Docker is accessible${NC}"
else
    echo -e "${RED}❌ Docker is not accessible${NC}"
    echo ""
    echo "Please fix Docker permissions first:"
    echo "  bash fix-docker.sh"
    echo ""
    echo "Or start Docker Desktop manually on Windows"
    exit 1
fi

# Step 2: Start Docker services
echo ""
echo -e "${BLUE}Step 2: Starting PostgreSQL and Redis...${NC}"
docker-compose down 2>/dev/null || true
docker-compose up -d

echo "Waiting 10 seconds for services to initialize..."
sleep 10

# Check if services are running
if docker ps | grep -q postgres; then
    echo -e "${GREEN}✓ PostgreSQL is running${NC}"
else
    echo -e "${RED}❌ PostgreSQL failed to start${NC}"
    exit 1
fi

if docker ps | grep -q redis; then
    echo -e "${GREEN}✓ Redis is running${NC}"
else
    echo -e "${RED}❌ Redis failed to start${NC}"
    exit 1
fi

# Step 3: Run migrations
echo ""
echo -e "${BLUE}Step 3: Running database migrations...${NC}"
cd backend
poetry run alembic upgrade head
echo -e "${GREEN}✓ Migrations complete${NC}"

# Step 4: Create sample data
echo ""
echo -e "${BLUE}Step 4: Creating sample data...${NC}"
poetry run python create_sample_data.py
echo -e "${GREEN}✓ Sample data created${NC}"

cd ..

# Step 5: Instructions to start servers
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Setup complete! Ready to start servers.${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${YELLOW}Open TWO new terminals and run:${NC}"
echo ""
echo -e "${BLUE}Terminal 1 - Backend Server:${NC}"
echo "  cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend"
echo "  poetry run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo -e "${BLUE}Terminal 2 - Frontend Server:${NC}"
echo "  cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/frontend"
echo "  npm run dev"
echo ""
echo -e "${GREEN}Then open your browser to:${NC}"
echo "  Frontend: http://localhost:3000"
echo "  API Docs: http://localhost:8000/docs"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
