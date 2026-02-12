# OpenDiscuss Quick Start Guide

## Prerequisites

- Docker and Docker Compose installed
- Python 3.11+ installed
- Node.js 18+ installed (✅ Already have v18.19.1)
- Poetry installed for Python dependency management

## Step 1: Install Poetry (if not installed)

```bash
# On Windows (PowerShell)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -

# On Linux/WSL
curl -sSL https://install.python-poetry.org | python3 -

# Add to PATH (follow Poetry's output instructions)
```

## Step 2: Start Database & Redis Services

```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00

# Start PostgreSQL and Redis in background
docker-compose up -d

# Verify services are running
docker ps
```

**Expected output**: Two containers running (postgres, redis)

## Step 3: Setup Backend

```bash
cd backend

# Install Python dependencies (takes ~2 minutes)
poetry install

# Run database migrations
poetry run alembic upgrade head

# Verify backend is ready
poetry run python -c "import sys; print(f'Python {sys.version}')"
```

## Step 4: Start Backend Server

```bash
# In backend directory
poetry run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Server will start at: http://localhost:8000
# API docs available at: http://localhost:8000/docs
```

## Step 5: Start Frontend (New Terminal)

```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/frontend

# Dependencies already installed (node_modules exists)
# Start dev server
npm run dev

# Frontend will start at: http://localhost:3000
```

## Step 6: Try It Out!

Open browser to **http://localhost:3000** and:

1. **Create Discussion**: Click "Create Discussion" button
   - Enter community ID
   - Add 1-3 questions (e.g., "What are your thoughts on remote work?")
   - Click "Create"

2. **Start Discussion**: Click "Start Discussion" button
   - Countdown timer begins (3-6 minute window)
   - Round 1 opens for submissions

3. **View Discussion**: Navigate to discussion page
   - See live countdown timer
   - View participant stats
   - Monitor round status

4. **View Report** (after completion):
   - See Sankey diagram with thought space visualization
   - Hover over nodes and flows for details

## Running Tests

### Backend Integration Tests

```bash
cd backend

# Run all tests
poetry run pytest tests/ -v

# Run specific test suites
poetry run pytest tests/integration/ -v           # Integration tests
poetry run pytest tests/compliance/ -v            # Constitutional compliance
poetry run pytest tests/performance/ -v -m performance  # Performance benchmarks

# Run with coverage
poetry run pytest tests/ --cov=src --cov-report=html
```

### Frontend E2E Tests (Optional - requires Cypress)

```bash
cd frontend

# Install Cypress
npm install --save-dev cypress @types/cypress

# Run E2E tests
npx cypress run

# Or open Cypress GUI
npx cypress open
```

## Troubleshooting

### Docker Services Won't Start

```bash
# Check if ports are already in use
netstat -ano | findstr :5432   # PostgreSQL
netstat -ano | findstr :6379   # Redis

# Stop any conflicting services
docker-compose down
docker-compose up -d
```

### Backend Dependencies Fail

```bash
# Update Poetry
poetry self update

# Clear cache and reinstall
poetry cache clear pypi --all
poetry install
```

### Database Migration Errors

```bash
# Reset database (WARNING: Deletes all data)
docker-compose down -v
docker-compose up -d
poetry run alembic upgrade head
```

### Frontend Won't Start

```bash
# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install
npm run dev
```

## API Documentation

Once backend is running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## Sample API Requests

### Create Discussion

```bash
curl -X POST http://localhost:8000/api/v1/discussions \
  -H "Content-Type: application/json" \
  -d '{
    "community_id": "550e8400-e29b-41d4-a716-446655440000",
    "host_user_id": "660e8400-e29b-41d4-a716-446655440000",
    "mode": "HOST_DEFINED",
    "total_rounds": 3,
    "questions": [
      "What are your thoughts on remote work?",
      "How can we improve team collaboration?",
      "What tools would help most?"
    ],
    "submission_window_duration_sec": 300
  }'
```

### Start Discussion

```bash
curl -X POST http://localhost:8000/api/v1/discussions/{discussion_id}/start
```

### Get Round Status

```bash
curl http://localhost:8000/api/v1/rounds/{round_id}/status
```

## Next Steps

1. **Create Sample Data**: Use the API to create a few discussions
2. **Run Tests**: `poetry run pytest tests/ -v` to validate everything works
3. **Explore API Docs**: http://localhost:8000/docs
4. **Read Deployment Guide**: See `backend/docs/deployment.md` for production setup

## Architecture Overview

```
Frontend (React + Vite)     Backend (FastAPI)           Database
http://localhost:3000  -->  http://localhost:8000  -->  PostgreSQL:5432
                                    |                    Redis:6379
                                    v
                            Sub-Protocol Events
                            (Pub/Sub via Redis)
```

## Constitutional Principles in Action

When you create a discussion, the system enforces:

1. **Parallel-First**: All participants submit simultaneously (no threading)
2. **Intent Fidelity**: 100% approval required before clustering
3. **Semantic Accuracy**: All participants assigned to clusters
4. **Temporal Transparency**: Flows show actual movement, not similarity
5. **Synchronous Deliberation**: 3-6 min windows, ±100ms precision
6. **No Voting**: Questions cannot contain voting/ranking keywords

## Demo Data

For testing, you can use these UUIDs:
- Community ID: `550e8400-e29b-41d4-a716-446655440000`
- Host User ID: `660e8400-e29b-41d4-a716-446655440000`
- Participant IDs: Generate with `python -c "import uuid; print(uuid.uuid4())"`

## Need Help?

- **API Issues**: Check logs in terminal where `uvicorn` is running
- **Database Issues**: `docker logs opendiscuss_v00-postgres-1`
- **Redis Issues**: `docker logs opendiscuss_v00-redis-1`
- **Test Failures**: Run with `-vv` flag for detailed output

---

**Status**: All code implemented ✅ | Ready to run after setup ⚙️
