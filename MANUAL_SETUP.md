# OpenDiscuss Manual Setup (No Docker Required)

Since Docker Desktop requires manual setup, here's a simpler approach using local PostgreSQL and Redis in WSL.

## Option A: Install PostgreSQL & Redis Locally (Recommended)

### Step 1: Install PostgreSQL and Redis

```bash
# Update package list
sudo apt-get update

# Install PostgreSQL
sudo apt-get install -y postgresql postgresql-contrib

# Install Redis
sudo apt-get install -y redis-server

# Start services
sudo service postgresql start
sudo service redis-server start
```

### Step 2: Setup PostgreSQL Database

```bash
# Switch to postgres user and create database
sudo -u postgres psql << 'EOF'
CREATE DATABASE opendiscuss;
CREATE USER opendiscuss WITH PASSWORD 'opendiscuss';
GRANT ALL PRIVILEGES ON DATABASE opendiscuss TO opendiscuss;
\q
EOF

# Test connection
psql -h localhost -U opendiscuss -d opendiscuss -c "SELECT version();"
# Password: opendiscuss
```

### Step 3: Update Environment Variables

```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend

# Create .env file
cat > .env << 'EOF'
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

# Telemetry (optional)
ENABLE_TELEMETRY=false
EOF

echo "✓ Environment file created"
```

### Step 4: Run Migrations and Create Sample Data

```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend
export PATH="$HOME/.local/bin:$PATH"

# Run migrations
poetry run alembic upgrade head

# Create sample data
poetry run python create_sample_data.py
```

### Step 5: Start Servers

**Terminal 1 - Backend:**
```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend
export PATH="$HOME/.local/bin:$PATH"
poetry run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/frontend
npm run dev
```

### Step 6: Access the Application

- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

---

## Option B: Fix Docker Desktop (If You Prefer Docker)

### Manual Steps:

1. **Find Docker Desktop:**
   - Check Start Menu for "Docker Desktop"
   - Or check: `C:\Program Files\Docker\Docker\Docker Desktop.exe`

2. **Start Docker Desktop:**
   - Double-click the application
   - Wait for "Docker Desktop is running" message in system tray
   - This can take 1-2 minutes

3. **Verify in WSL:**
   ```bash
   docker ps
   # Should show "CONTAINER ID   IMAGE..." header
   ```

4. **Start Services:**
   ```bash
   cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00
   docker-compose up -d
   ```

5. **Continue with migrations:**
   ```bash
   cd backend
   poetry run alembic upgrade head
   poetry run python create_sample_data.py
   ```

---

## Quick Status Check

Run this to see what's working:

```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00

echo "=== Status Check ==="
echo ""

# Check PostgreSQL
echo "PostgreSQL:"
pg_isready -h localhost 2>/dev/null && echo "  ✓ Running" || echo "  ✗ Not running"

# Check Redis
echo "Redis:"
redis-cli ping 2>/dev/null && echo "  ✓ Running" || echo "  ✗ Not running"

# Check Backend dependencies
echo "Backend:"
cd backend && poetry run python -c "import sys; print(f'  ✓ Python {sys.version.split()[0]}')" 2>/dev/null || echo "  ✗ Dependencies not installed"
cd ..

# Check Frontend dependencies
echo "Frontend:"
[ -d "frontend/node_modules" ] && echo "  ✓ Dependencies installed" || echo "  ✗ Dependencies not installed"
```

---

## Troubleshooting

### PostgreSQL Connection Issues

```bash
# Check if PostgreSQL is running
sudo service postgresql status

# Start if needed
sudo service postgresql start

# Check port
sudo netstat -plnt | grep 5432
```

### Redis Connection Issues

```bash
# Check if Redis is running
sudo service redis-server status

# Start if needed
sudo service redis-server start

# Test connection
redis-cli ping
# Should return: PONG
```

### Database Permission Issues

```bash
# Reset database (WARNING: Deletes all data)
sudo -u postgres psql << 'EOF'
DROP DATABASE IF EXISTS opendiscuss;
CREATE DATABASE opendiscuss;
GRANT ALL PRIVILEGES ON DATABASE opendiscuss TO opendiscuss;
EOF
```

---

## Recommended: Option A (Local Install)

**Why?**
- ✅ No Docker Desktop needed
- ✅ Faster startup (services always running)
- ✅ Simpler troubleshooting
- ✅ Better for development
- ✅ Less resource usage

**Installation time:** ~3 minutes

---

## Need Help?

After following these steps, if you encounter issues:

1. Check service status with the status check script above
2. Look for error messages in terminal output
3. Check logs: `tail -f backend/logs/app.log`

**Current Status:**
- ✅ Backend code: Complete and tested
- ✅ Frontend code: Complete and tested
- ✅ Python dependencies: Installed
- ✅ Node dependencies: Installed
- ⏳ Database: Needs setup (choose Option A or B above)
