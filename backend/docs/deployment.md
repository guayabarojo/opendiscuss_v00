# OpenDiscuss Discussion Protocol - Deployment Guide

**Version**: 1.0.0
**Last Updated**: 2026-01-29
**Target**: Production deployment with Docker Compose

This guide provides comprehensive instructions for deploying the OpenDiscuss Discussion Protocol (System Spine) to production environments.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Configuration](#environment-configuration)
3. [Docker Compose Production Setup](#docker-compose-production-setup)
4. [Database Migrations](#database-migrations)
5. [Monitoring & Observability](#monitoring--observability)
6. [Performance Tuning](#performance-tuning)
7. [Security Hardening](#security-hardening)
8. [Backup & Recovery](#backup--recovery)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

- **OS**: Linux (Ubuntu 22.04 LTS recommended)
- **RAM**: Minimum 4GB (8GB recommended for production)
- **CPU**: 2+ cores
- **Storage**: 20GB+ available disk space
- **Network**: Stable internet connection with open ports 80/443

### Software Requirements

- Docker Engine 24.0+ ([Install Guide](https://docs.docker.com/engine/install/))
- Docker Compose v2.20+ ([Install Guide](https://docs.docker.com/compose/install/))
- PostgreSQL 14+ (via Docker)
- Redis 7+ (via Docker)
- Python 3.11+ (for local development/migrations)

### Domain & SSL

- Registered domain name (e.g., `api.opendiscuss.example`)
- SSL/TLS certificate (Let's Encrypt recommended)
- DNS A record pointing to your server IP

---

## Environment Configuration

### Environment Variables Reference

Create a `.env` file in the project root with the following variables:

```bash
# Application Settings
APP_ENV=production
APP_NAME="OpenDiscuss Discussion Protocol"
DEBUG=false
LOG_LEVEL=INFO

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
API_RELOAD=false

# CORS Settings (adjust for your frontend domains)
CORS_ORIGINS=["https://app.opendiscuss.example", "https://www.opendiscuss.example"]
CORS_ALLOW_CREDENTIALS=true

# Security
SECRET_KEY=your-production-secret-key-min-32-chars-here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60

# Database Configuration
DATABASE_URL=postgresql+asyncpg://opendiscuss:SECURE_PASSWORD_HERE@postgres:5432/opendiscuss_prod
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30
DATABASE_ECHO=false

# Redis Configuration
REDIS_URL=redis://redis:6379/0
REDIS_MAX_CONNECTIONS=50
REDIS_SOCKET_TIMEOUT=5

# Timing Service (Constitutional Principle VI)
TIMING_PRECISION_MS=100
SUBMISSION_WINDOW_MIN_SEC=180
SUBMISSION_WINDOW_MAX_SEC=360
ROUND_PROCESSING_TIMEOUT_SEC=600

# Rate Limiting (US3)
SUBMISSION_RATE_LIMIT=3
APPROVAL_TIMEOUT_MINUTES=10

# Performance
MAX_PARTICIPANTS_PER_DISCUSSION=100
MAX_ROUNDS=10
SANKEY_CONSTRUCTION_TIMEOUT_SEC=5

# Monitoring
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
ENABLE_TELEMETRY=true
TELEMETRY_EXPORT_ENDPOINT=http://jaeger:4318/v1/traces

# Sub-Protocol Endpoints (Specs 2-6)
SUBMISSION_SERVICE_URL=http://submission-service:8001
SUMMARIZATION_SERVICE_URL=http://summarization-service:8002
CLUSTERING_SERVICE_URL=http://clustering-service:8003
SANKEY_SERVICE_URL=http://sankey-service:8004
QUESTION_GEN_SERVICE_URL=http://question-gen-service:8005

# Health Check
HEALTH_CHECK_INTERVAL_SEC=30
```

### Generating Secrets

```bash
# Generate SECRET_KEY (32+ characters)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate database password
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

### Environment-Specific Files

Create environment-specific files:

- `.env.production` - Production settings
- `.env.staging` - Staging settings
- `.env.local` - Local development

**Security Note**: Never commit `.env` files to version control. Add to `.gitignore`:

```bash
echo ".env*" >> .gitignore
echo "!.env.example" >> .gitignore
```

---

## Docker Compose Production Setup

### Production docker-compose.yml

Create `docker-compose.prod.yml`:

```yaml
version: '3.9'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:14-alpine
    container_name: opendiscuss-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: opendiscuss_prod
      POSTGRES_USER: opendiscuss
      POSTGRES_PASSWORD: ${DATABASE_PASSWORD}
      POSTGRES_INITDB_ARGS: "--encoding=UTF-8 --lc-collate=en_US.UTF-8 --lc-ctype=en_US.UTF-8"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/alembic/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U opendiscuss"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - opendiscuss-network

  # Redis Cache
  redis:
    image: redis:7-alpine
    container_name: opendiscuss-redis
    restart: unless-stopped
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
    networks:
      - opendiscuss-network

  # Discussion Protocol API
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
      args:
        PYTHON_VERSION: 3.11
    container_name: opendiscuss-api
    restart: unless-stopped
    env_file:
      - .env.production
    environment:
      DATABASE_URL: postgresql+asyncpg://opendiscuss:${DATABASE_PASSWORD}@postgres:5432/opendiscuss_prod
      REDIS_URL: redis://redis:6379/0
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - opendiscuss-network
    volumes:
      - ./backend/logs:/app/logs
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G

  # Nginx Reverse Proxy
  nginx:
    image: nginx:alpine
    container_name: opendiscuss-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - ./nginx/logs:/var/log/nginx
    depends_on:
      - api
    networks:
      - opendiscuss-network

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local

networks:
  opendiscuss-network:
    driver: bridge
```

### Dockerfile.prod

Create `backend/Dockerfile.prod`:

```dockerfile
FROM python:3.11-slim as builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==1.7.1

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 opendiscuss

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=opendiscuss:opendiscuss . .

# Switch to non-root user
USER opendiscuss

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application with Uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Nginx Configuration

Create `nginx/nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream api_backend {
        server api:8000;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

    server {
        listen 80;
        server_name api.opendiscuss.example;

        # Redirect to HTTPS
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name api.opendiscuss.example;

        # SSL Configuration
        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;

        # Security Headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

        # Logging
        access_log /var/log/nginx/access.log;
        error_log /var/log/nginx/error.log;

        # API Proxy
        location /api/ {
            limit_req zone=api_limit burst=20 nodelay;

            proxy_pass http://api_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # Timeouts
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        # Health Check
        location /health {
            proxy_pass http://api_backend/health;
            access_log off;
        }

        # API Documentation
        location /docs {
            proxy_pass http://api_backend/docs;
        }

        location /redoc {
            proxy_pass http://api_backend/redoc;
        }
    }
}
```

### Deployment Commands

```bash
# 1. Clone repository
git clone https://github.com/opendiscuss/opendiscuss.git
cd opendiscuss

# 2. Configure environment
cp .env.example .env.production
nano .env.production  # Edit with production values

# 3. Build and start services
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# 4. Check service health
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs -f api

# 5. Run database migrations (see next section)
```

---

## Database Migrations

### Running Migrations with Alembic

```bash
# 1. Access API container
docker exec -it opendiscuss-api bash

# 2. Check migration status
alembic current

# 3. View pending migrations
alembic history

# 4. Run all migrations
alembic upgrade head

# 5. Verify migration
alembic current
psql $DATABASE_URL -c "\dt"  # List tables

# Exit container
exit
```

### Migration Strategy

**Initial Deployment**:
```bash
# Run all migrations on first deployment
alembic upgrade head
```

**Updating Existing Deployment**:
```bash
# 1. Backup database first (see Backup section)
# 2. Pull latest code
git pull origin main

# 3. Rebuild and restart API
docker-compose -f docker-compose.prod.yml build api
docker-compose -f docker-compose.prod.yml up -d api

# 4. Run migrations
docker exec opendiscuss-api alembic upgrade head
```

**Rollback Migrations**:
```bash
# Rollback one migration
docker exec opendiscuss-api alembic downgrade -1

# Rollback to specific revision
docker exec opendiscuss-api alembic downgrade <revision_id>
```

### Creating Custom Migrations

```bash
# Generate migration from model changes
docker exec opendiscuss-api alembic revision --autogenerate -m "Add new feature"

# Review generated migration
docker exec opendiscuss-api cat alembic/versions/<revision>_add_new_feature.py

# Apply migration
docker exec opendiscuss-api alembic upgrade head
```

---

## Monitoring & Observability

### Health Checks

**Endpoint**: `GET /health`

```bash
# Check API health
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "database": {"status": "healthy"},
  "redis": {"status": "healthy"}
}
```

**Monitoring Script** (`scripts/health_check.sh`):
```bash
#!/bin/bash
HEALTH_URL="http://localhost:8000/health"

response=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL)

if [ $response -eq 200 ]; then
    echo "✓ Health check passed"
    exit 0
else
    echo "✗ Health check failed (HTTP $response)"
    exit 1
fi
```

### Structured Logging

Logs are written to `backend/logs/` with JSON format:

```bash
# View API logs
docker-compose -f docker-compose.prod.yml logs -f api

# Filter by log level
docker-compose logs api | grep "ERROR"

# View last 100 lines
docker-compose logs --tail=100 api
```

**Log Format**:
```json
{
  "timestamp": "2026-01-29T12:00:00Z",
  "level": "INFO",
  "trace_id": "abc123",
  "discussion_id": "uuid",
  "round_id": "uuid",
  "message": "Round 1 submission window closed",
  "details": {"submissions_count": 42}
}
```

### OpenTelemetry Tracing

**Jaeger Setup** (add to docker-compose.prod.yml):
```yaml
  jaeger:
    image: jaegertracing/all-in-one:latest
    container_name: opendiscuss-jaeger
    ports:
      - "16686:16686"  # Jaeger UI
      - "4318:4318"    # OTLP HTTP
    environment:
      COLLECTOR_OTLP_ENABLED: true
    networks:
      - opendiscuss-network
```

Access Jaeger UI: `http://localhost:16686`

### Prometheus Metrics

**Metrics Endpoint**: `GET /metrics`

Key metrics:
- `discussion_created_total`: Total discussions created
- `round_duration_seconds`: Round processing time
- `submission_count`: Submissions per round
- `flow_accuracy_ratio`: Flow computation accuracy

**Prometheus Config** (`prometheus.yml`):
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'opendiscuss-api'
    static_configs:
      - targets: ['api:8000']
```

### Error Tracking with Sentry

Configure Sentry DSN in `.env.production`:
```bash
SENTRY_DSN=https://your-key@sentry.io/project-id
```

Sentry captures:
- Unhandled exceptions
- Failed invariant validations
- Database connection errors
- Sub-protocol coordination failures

---

## Performance Tuning

### Database Optimization

**Connection Pooling**:
```bash
# .env.production
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30
```

**Indexes** (auto-created via migrations):
- `idx_discussion_community_status` on `(community_id, status)`
- `idx_round_discussion_num` on `(discussion_id, round_num)`
- `idx_participant_discussion` on `(discussion_id)`
- `idx_flow_source_target` on `(source_cluster_id, target_cluster_id)`

**Vacuum & Analyze**:
```bash
# Run weekly
docker exec opendiscuss-postgres psql -U opendiscuss -d opendiscuss_prod -c "VACUUM ANALYZE;"
```

### Redis Tuning

**Memory Management**:
```bash
# docker-compose.prod.yml
command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
```

**Connection Pool**:
```bash
# .env.production
REDIS_MAX_CONNECTIONS=50
REDIS_SOCKET_TIMEOUT=5
```

### API Performance

**Uvicorn Workers**:
```bash
# Formula: (2 x CPU cores) + 1
# For 2 CPU cores: 5 workers
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "5"]
```

**CORS Optimization**:
- Limit `CORS_ORIGINS` to specific domains
- Disable `CORS_ALLOW_CREDENTIALS` if not needed

### Constitutional Timing (Principle VI)

**Timing Precision** (±100ms guarantee):
```bash
TIMING_PRECISION_MS=100
```

**Performance Targets**:
- Submission window closure: ±100ms (99th percentile)
- Round processing: <10 minutes (SC-004)
- Sankey construction: <2 seconds for 100 participants (SC-006)
- 5-round discussion: <60 minutes total (SC-008)

**Monitoring**:
```bash
# Check timing metrics
curl http://localhost:8000/api/v1/discussions/{id}/timing
```

---

## Security Hardening

### Network Security

**Firewall Rules** (UFW):
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

**Docker Network Isolation**:
- API containers on private `opendiscuss-network`
- Only Nginx exposed to public internet
- Database and Redis not externally accessible

### Application Security

**JWT Configuration**:
```bash
# Strong secret key (32+ characters)
SECRET_KEY=your-production-secret-min-32-chars-here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60
```

**Rate Limiting**:
```bash
# Nginx rate limiting (10 req/sec, burst 20)
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
```

**Database Security**:
```bash
# Use strong password
POSTGRES_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(24))")

# Restrict connections to Docker network only
# No external port exposure in production
```

### Docker Security

**Non-Root User**:
```dockerfile
# Dockerfile.prod
RUN useradd -m -u 1000 opendiscuss
USER opendiscuss
```

**Read-Only Filesystem** (where possible):
```yaml
# docker-compose.prod.yml
services:
  nginx:
    read_only: true
    tmpfs:
      - /var/cache/nginx
      - /var/run
```

---

## Backup & Recovery

### Database Backups

**Automated Backup Script** (`scripts/backup_db.sh`):
```bash
#!/bin/bash
BACKUP_DIR="/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/opendiscuss_$DATE.sql.gz"

mkdir -p $BACKUP_DIR

# Create backup
docker exec opendiscuss-postgres pg_dump -U opendiscuss opendiscuss_prod | gzip > $BACKUP_FILE

# Verify backup
if [ $? -eq 0 ]; then
    echo "✓ Backup created: $BACKUP_FILE"
    # Delete backups older than 30 days
    find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
else
    echo "✗ Backup failed"
    exit 1
fi
```

**Cron Job** (daily at 2 AM):
```bash
crontab -e
# Add:
0 2 * * * /path/to/scripts/backup_db.sh >> /var/log/backup.log 2>&1
```

**Manual Backup**:
```bash
docker exec opendiscuss-postgres pg_dump -U opendiscuss opendiscuss_prod > backup.sql
```

### Restore from Backup

```bash
# 1. Stop API
docker-compose -f docker-compose.prod.yml stop api

# 2. Drop existing database
docker exec opendiscuss-postgres psql -U opendiscuss -c "DROP DATABASE opendiscuss_prod;"
docker exec opendiscuss-postgres psql -U opendiscuss -c "CREATE DATABASE opendiscuss_prod;"

# 3. Restore backup
gunzip -c backup.sql.gz | docker exec -i opendiscuss-postgres psql -U opendiscuss opendiscuss_prod

# 4. Restart API
docker-compose -f docker-compose.prod.yml start api
```

### Redis Persistence

Redis uses AOF (Append-Only File) for persistence:

```bash
# Backup Redis data
docker exec opendiscuss-redis redis-cli BGSAVE
docker cp opendiscuss-redis:/data/dump.rdb ./redis_backup.rdb

# Restore Redis data
docker cp ./redis_backup.rdb opendiscuss-redis:/data/dump.rdb
docker-compose restart redis
```

---

## Troubleshooting

### Common Issues

#### API Container Won't Start

**Symptom**: API container exits immediately

**Solutions**:
```bash
# Check logs
docker-compose logs api

# Common causes:
# 1. Database connection failed
docker-compose ps postgres  # Ensure healthy

# 2. Invalid environment variables
docker exec opendiscuss-api env | grep DATABASE_URL

# 3. Port already in use
sudo lsof -i :8000
```

#### Database Connection Errors

**Symptom**: `sqlalchemy.exc.OperationalError: could not connect to server`

**Solutions**:
```bash
# Check PostgreSQL health
docker exec opendiscuss-postgres pg_isready

# Verify DATABASE_URL format
# postgresql+asyncpg://user:pass@host:port/db

# Check network connectivity
docker exec opendiscuss-api ping postgres
```

#### Timing Precision Violations

**Symptom**: `timing.violation` events in logs

**Solutions**:
```bash
# Check Redis performance
docker exec opendiscuss-redis redis-cli INFO stats | grep ops_per_sec

# Increase Redis max memory
# docker-compose.prod.yml: --maxmemory 512mb

# Check system load
docker stats
```

#### Slow Round Processing

**Symptom**: Rounds take >10 minutes

**Solutions**:
```bash
# Check database query performance
docker exec opendiscuss-postgres psql -U opendiscuss opendiscuss_prod -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"

# Increase API workers
# Dockerfile.prod: --workers 6

# Check sub-protocol latency
docker-compose logs summarization-service
```

### Health Check Failures

```bash
# Debug health endpoint
docker exec opendiscuss-api curl http://localhost:8000/health

# Check database connectivity
docker exec opendiscuss-api python -c "from src.database import test_connection; test_connection()"

# Check Redis connectivity
docker exec opendiscuss-redis redis-cli PING
```

### Log Debugging

```bash
# Enable debug logging
# .env.production: LOG_LEVEL=DEBUG

# Follow logs in real-time
docker-compose -f docker-compose.prod.yml logs -f --tail=100 api

# Export logs for analysis
docker-compose logs api > api_logs.txt
```

---

## Production Checklist

Before going live, verify:

- [ ] All environment variables set in `.env.production`
- [ ] Strong `SECRET_KEY` and `DATABASE_PASSWORD` generated
- [ ] SSL certificates installed in `nginx/ssl/`
- [ ] DNS A record pointing to server IP
- [ ] Firewall configured (only 80/443 open)
- [ ] Database migrations applied (`alembic upgrade head`)
- [ ] Health checks passing (`/health` returns 200)
- [ ] Backup script configured and tested
- [ ] Monitoring tools configured (Sentry, Prometheus, Jaeger)
- [ ] Log rotation enabled
- [ ] Docker containers set to `restart: unless-stopped`
- [ ] Rate limiting tested
- [ ] Performance benchmarks met (SC-004, SC-006, SC-008)
- [ ] Constitutional timing validated (±100ms precision)

---

## Additional Resources

- **Constitution**: `.specify/memory/constitution.md`
- **API Contracts**: `specs/001-discussion-protocol/contracts/discussion-api.yaml`
- **Architecture**: `specs/001-discussion-protocol/plan.md`
- **API Documentation**: `http://localhost:8000/docs`

---

**Version History**:
- 1.0.0 (2026-01-29): Initial production deployment guide

**Maintenance**: Review this guide quarterly and update with operational learnings.
