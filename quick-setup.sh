#!/bin/bash
# Quick Setup for OpenDiscuss (Application Setup Only)
# Run with: bash quick-setup.sh
#
# Prerequisites: PostgreSQL and Redis must be installed and running
# Use setup-services.sh to set up services first if needed

set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo "🚀 OpenDiscuss Application Setup"
echo "=================================="
echo ""

# Check prerequisites
echo "🔍 Step 1: Checking prerequisites..."

# Check Poetry
if ! command -v poetry &> /dev/null; then
    echo "⚠️  Poetry not found. Installing poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
    # Verify installation
    if ! command -v poetry &> /dev/null; then
        echo "❌ Poetry installation failed"
        exit 1
    fi
fi
echo "✓ Poetry found"

# Check PostgreSQL
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL not found"
    echo ""
    echo "Please run: bash setup-services.sh"
    exit 1
fi

# Check Redis
if ! command -v redis-cli &> /dev/null; then
    echo "❌ Redis not found"
    echo ""
    echo "Please run: bash setup-services.sh"
    exit 1
fi

echo "✓ PostgreSQL and Redis found"
echo ""

# Verify services are running
echo "🔧 Step 2: Verifying services..."

# Check PostgreSQL
if ! pg_isready -h localhost -p 5432 &> /dev/null; then
    echo "❌ PostgreSQL is not running"
    echo ""
    echo "Please run: bash setup-services.sh"
    echo "Or manually: sudo service postgresql start"
    exit 1
fi
echo "✓ PostgreSQL is running"

# Check Redis
if ! redis-cli ping &> /dev/null 2>&1; then
    echo "❌ Redis is not running"
    echo ""
    echo "Please run: bash setup-services.sh"
    echo "Or manually: sudo service redis-server start"
    exit 1
fi
echo "✓ Redis is running"
echo ""

# Check database exists
echo "🗄️  Step 3: Checking database..."

# Set password for psql (to avoid prompts)
export PGPASSWORD='opendiscuss'

# Check if database exists
if psql -h localhost -U opendiscuss -d opendiscuss -c "SELECT 1" &> /dev/null; then
    echo "✓ Database 'opendiscuss' exists and is accessible"
else
    echo "⚠️  Database 'opendiscuss' not found or not accessible"
    echo ""
    echo "Please run: bash setup-services.sh"
    echo ""
    echo "Or create manually:"
    echo '  sudo -u postgres psql -c "CREATE DATABASE opendiscuss;"'
    echo '  sudo -u postgres psql -c "CREATE USER opendiscuss WITH PASSWORD '"'"'opendiscuss'"'"';"'
    echo '  sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE opendiscuss TO opendiscuss;"'
    exit 1
fi
echo ""

# Check .env file
echo "⚙️  Step 4: Checking environment configuration..."
cd "$BACKEND_DIR"

if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cat > .env << 'EOFENV'
# Database
DATABASE_URL=postgresql+asyncpg://opendiscuss:opendiscuss@localhost:5432/opendiscuss

# Redis
REDIS_URL=redis://localhost:6379/0

# Application
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# CORS
CORS_ORIGINS=["http://localhost:3000"]

# API
API_VERSION=v1

# Telemetry
ENABLE_TELEMETRY=false
EOFENV
    echo "✓ Environment file created"
else
    echo "✓ Environment file exists"
fi
echo ""

# Install Python dependencies
echo "📚 Step 5: Installing Python dependencies..."
export PATH="$HOME/.local/bin:$PATH"

# Check if dependencies are already installed
if [ -d ".venv" ] && poetry run python -c "import fastapi" &> /dev/null; then
    echo "✓ Dependencies already installed (skipping)"
else
    echo "Installing dependencies (this may take a few minutes)..."
    poetry install
    echo "✓ Dependencies installed"
fi
echo ""

# Run migrations
echo "🔄 Step 6: Running database migrations..."
if poetry run alembic upgrade head; then
    echo "✓ Migrations complete"
else
    echo "⚠️  Migration failed or no migrations to run"
    echo "This might be okay if migrations were already applied"
fi
echo ""

# Create sample data
echo "🎨 Step 7: Creating sample data..."
if [ -f "create_sample_data.py" ]; then
    if poetry run python create_sample_data.py; then
        echo "✓ Sample data created"
    else
        echo "⚠️  Sample data creation failed or data already exists"
    fi
else
    echo "⚠️  create_sample_data.py not found, skipping"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🚀 Start the application:"
echo ""
echo "Backend:"
echo "  cd $BACKEND_DIR"
echo "  poetry run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
if [ -d "$FRONTEND_DIR" ]; then
    echo "Frontend:"
    echo "  cd $FRONTEND_DIR"
    echo "  npm install  # (first time only)"
    echo "  npm run dev"
    echo ""
fi
echo "📍 URLs:"
echo "  Backend API: http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
if [ -d "$FRONTEND_DIR" ]; then
    echo "  Frontend: http://localhost:3000"
fi
echo ""
