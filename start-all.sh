#!/bin/bash
set -e

echo "🚀 OpenDiscuss Quick Start Script"
echo "=================================="
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker first.${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found. Please install Docker Compose first.${NC}"
    exit 1
fi

if ! command -v poetry &> /dev/null; then
    echo -e "${YELLOW}⚠️  Poetry not found. Installing Poetry...${NC}"
    curl -sSL https://install.python-poetry.org | python3 -
    echo -e "${GREEN}✓ Poetry installed. Please add Poetry to your PATH and run this script again.${NC}"
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js not found. Please install Node.js 18+ first.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ All prerequisites met${NC}"
echo ""

# Start Docker services
echo "🐳 Starting Docker services (PostgreSQL + Redis)..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check if services are running
if ! docker ps | grep -q postgres; then
    echo -e "${RED}❌ PostgreSQL failed to start${NC}"
    exit 1
fi

if ! docker ps | grep -q redis; then
    echo -e "${RED}❌ Redis failed to start${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker services running${NC}"
echo ""

# Setup backend
echo "🐍 Setting up backend..."
cd backend

if [ ! -d ".venv" ]; then
    echo "📦 Installing Python dependencies (this may take 2-3 minutes)..."
    poetry install
else
    echo "✓ Dependencies already installed"
fi

echo "🗄️  Running database migrations..."
poetry run alembic upgrade head

echo -e "${GREEN}✓ Backend ready${NC}"
echo ""

# Check frontend
cd ../frontend
echo "⚛️  Checking frontend dependencies..."
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
else
    echo "✓ Dependencies already installed"
fi

echo -e "${GREEN}✓ Frontend ready${NC}"
echo ""

# Instructions to start servers
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup complete! Ready to start servers."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "To start the application, open TWO terminal windows:"
echo ""
echo "📍 Terminal 1 - Backend Server:"
echo "   cd backend"
echo "   poetry run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "📍 Terminal 2 - Frontend Dev Server:"
echo "   cd frontend"
echo "   npm run dev"
echo ""
echo "Then open your browser to:"
echo "   Frontend: http://localhost:3000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📚 To run tests:"
echo "   cd backend"
echo "   poetry run pytest tests/ -v"
echo ""
