#!/bin/bash
# Helper script to set up PostgreSQL and Redis services
# Run with: bash setup-services.sh

echo "🔧 OpenDiscuss Service Setup"
echo "=============================="
echo ""
echo "This script will help you set up PostgreSQL and Redis"
echo ""

# Check if already installed
echo "Checking for existing installations..."
PSQL_INSTALLED=false
REDIS_INSTALLED=false

if command -v psql &> /dev/null; then
    echo "✓ PostgreSQL is installed"
    PSQL_INSTALLED=true
else
    echo "✗ PostgreSQL is not installed"
fi

if command -v redis-cli &> /dev/null; then
    echo "✓ Redis is installed"
    REDIS_INSTALLED=true
else
    echo "✗ Redis is not installed"
fi

echo ""

# Install if needed
if [ "$PSQL_INSTALLED" = false ] || [ "$REDIS_INSTALLED" = false ]; then
    echo "Installing missing services..."
    echo "You will be prompted for your sudo password"
    echo ""
    sudo apt-get update

    if [ "$PSQL_INSTALLED" = false ]; then
        echo "Installing PostgreSQL..."
        sudo apt-get install -y postgresql postgresql-contrib
    fi

    if [ "$REDIS_INSTALLED" = false ]; then
        echo "Installing Redis..."
        sudo apt-get install -y redis-server
    fi
    echo "✓ Installation complete"
    echo ""
fi

# Start services
echo "Starting services..."
sudo service postgresql start
sudo service redis-server start
echo ""

# Verify services
echo "Verifying services..."
sleep 2

if pg_isready -h localhost -p 5432 &> /dev/null; then
    echo "✓ PostgreSQL is running"
else
    echo "✗ PostgreSQL is not running"
    exit 1
fi

if redis-cli ping &> /dev/null; then
    echo "✓ Redis is running"
else
    echo "✗ Redis is not running"
    exit 1
fi

echo ""
echo "Creating database and user..."

# Create database and user
sudo -u postgres psql << 'EOFPSQL'
-- Drop existing database if it exists
DROP DATABASE IF EXISTS opendiscuss;

-- Create database
CREATE DATABASE opendiscuss;

-- Create user if it doesn't exist
DO
$$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = 'opendiscuss') THEN
      CREATE USER opendiscuss WITH PASSWORD 'opendiscuss';
   END IF;
END
$$;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE opendiscuss TO opendiscuss;
ALTER DATABASE opendiscuss OWNER TO opendiscuss;

-- Connect to the database and grant schema privileges
\c opendiscuss
GRANT ALL ON SCHEMA public TO opendiscuss;
EOFPSQL

if [ $? -eq 0 ]; then
    echo "✓ Database and user created"
else
    echo "✗ Failed to create database"
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Services are ready!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next step: Run the application setup"
echo "  bash quick-setup.sh"
echo ""
