# Phase 1 Testing Guide - Spec 004 Clustering

Quick guide to test and verify Phase 1 setup is working correctly.

---

## 1. Run Verification Script

```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend
python3 verify_phase1_setup.py
```

**Expected**: All checks should pass with green ✓ marks.

---

## 2. Start Docker Services

```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00

# Start PostgreSQL and Redis
docker-compose up -d postgres redis

# Check services are running
docker-compose ps
```

**Expected output**:
```
NAME                    IMAGE                   STATUS
opendiscuss-postgres    pgvector/pgvector:pg15  Up (healthy)
opendiscuss-redis       redis:7-alpine          Up (healthy)
```

---

## 3. Verify pgvector Extension

```bash
# Connect to PostgreSQL and check pgvector extension
docker exec opendiscuss-postgres psql -U opendiscuss -d opendiscuss -c '\dx vector'
```

**Expected output**:
```
                               List of installed extensions
  Name   | Version |   Schema   |                      Description
---------+---------+------------+--------------------------------------------------------
 vector  | 0.5.1   | public     | vector data type and ivfflat access method
(1 row)
```

---

## 4. Test Vector Operations

```bash
# Test creating a table with vector column
docker exec opendiscuss-postgres psql -U opendiscuss -d opendiscuss -c "
CREATE TEMPORARY TABLE test_vectors (
    id SERIAL PRIMARY KEY,
    embedding vector(384)
);
"
```

**Expected**: `CREATE TABLE` (no errors)

```bash
# Test inserting a vector
docker exec opendiscuss-postgres psql -U opendiscuss -d opendiscuss -c "
INSERT INTO test_vectors (embedding)
VALUES ('[0.1, 0.2, 0.3, 0.4, 0.5]'::vector);
"
```

**Expected**: `INSERT 0 1` (no errors)

---

## 5. Test Python Dependencies

```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend

# Create/activate virtual environment (if not already done)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Test imports
python3 -c "
import sentence_transformers
import hdbscan
import numpy
import scipy
import sklearn
print('✓ All clustering dependencies imported successfully')
"
```

**Expected**: `✓ All clustering dependencies imported successfully`

---

## 6. Test SBERT Model Loading

```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend

python3 -c "
from sentence_transformers import SentenceTransformer
import os

# Load model specified in .env
model_name = os.getenv('EMBEDDING_MODEL_VERSION', 'all-MiniLM-L6-v2')
print(f'Loading model: {model_name}')

model = SentenceTransformer(model_name)
print(f'✓ Model loaded: {model_name}')
print(f'✓ Embedding dimension: {model.get_sentence_embedding_dimension()}')

# Test embedding generation
test_text = 'This is a test sentence'
embedding = model.encode(test_text)
print(f'✓ Generated embedding with shape: {embedding.shape}')
"
```

**Expected output**:
```
Loading model: all-MiniLM-L6-v2
✓ Model loaded: all-MiniLM-L6-v2
✓ Embedding dimension: 384
✓ Generated embedding with shape: (384,)
```

---

## 7. Test HDBSCAN Clustering

```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend

python3 -c "
import hdbscan
import numpy as np

# Create test data
data = np.random.rand(20, 384)  # 20 samples, 384 dimensions
print(f'Test data shape: {data.shape}')

# Initialize HDBSCAN with spec parameters
clusterer = hdbscan.HDBSCAN(
    min_cluster_size=2,
    allow_single_cluster=True,
    cluster_selection_method='eom'
)
print('✓ HDBSCAN initialized with spec parameters')

# Fit clustering
labels = clusterer.fit_predict(data)
print(f'✓ Clustering complete. Found {len(set(labels))} clusters (including noise)')
print(f'✓ Cluster labels: {set(labels)}')
"
```

**Expected output**:
```
Test data shape: (20, 384)
✓ HDBSCAN initialized with spec parameters
✓ Clustering complete. Found X clusters (including noise)
✓ Cluster labels: {-1, 0, 1, ...}
```

---

## 8. Test Redis Connection

```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend

python3 -c "
import redis
import os

redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
print(f'Connecting to: {redis_url}')

r = redis.from_url(redis_url)
r.ping()
print('✓ Redis connection successful')

# Test pub/sub
r.publish('test_channel', 'test_message')
print('✓ Redis publish successful')
"
```

**Expected output**:
```
Connecting to: redis://localhost:6379/0
✓ Redis connection successful
✓ Redis publish successful
```

---

## 9. Test PostgreSQL Connection with asyncpg

```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend

python3 -c "
import asyncio
import asyncpg
import os

async def test_connection():
    database_url = os.getenv('DATABASE_URL', 'postgresql://opendiscuss:opendiscuss@localhost:5432/opendiscuss')
    # Remove asyncpg+ prefix if present
    database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')

    print(f'Connecting to database...')
    conn = await asyncpg.connect(database_url)

    # Test basic query
    result = await conn.fetchval('SELECT 1')
    print(f'✓ Database connection successful (result: {result})')

    # Check pgvector extension
    version = await conn.fetchval(\"SELECT extversion FROM pg_extension WHERE extname = 'vector'\")
    if version:
        print(f'✓ pgvector extension enabled (version: {version})')
    else:
        print('✗ pgvector extension not found')

    await conn.close()

asyncio.run(test_connection())
"
```

**Expected output**:
```
Connecting to database...
✓ Database connection successful (result: 1)
✓ pgvector extension enabled (version: 0.5.1)
```

---

## 10. Run pytest Setup Verification

```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend

# Run pytest with spec004 marker (should find 0 tests - Phase 1 doesn't have tests yet)
pytest -v -m spec004
```

**Expected output**:
```
collected 0 items
```

This is correct - Phase 1 is setup only. Tests will be added in Phase 2 and beyond.

---

## Troubleshooting

### Issue: Docker permission denied
**Solution**: Run Docker with appropriate permissions or add user to docker group:
```bash
sudo usermod -aG docker $USER
# Log out and back in
```

### Issue: Module not found (Python packages)
**Solution**: Install dependencies:
```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend
pip install -r requirements.txt
```

### Issue: PostgreSQL connection refused
**Solution**: Ensure PostgreSQL is running:
```bash
docker-compose up -d postgres
docker-compose ps postgres
```

### Issue: pgvector extension not found
**Solution**: Recreate PostgreSQL container:
```bash
docker-compose down postgres
docker volume rm opendiscuss-postgres-data
docker-compose up -d postgres
# Wait for initialization, then check:
docker exec opendiscuss-postgres psql -U opendiscuss -c '\dx vector'
```

### Issue: SBERT model download fails
**Solution**: Model downloads on first use. Ensure internet connection and retry:
```bash
python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

---

## Success Criteria

Phase 1 is complete when:

- ✅ All verification script checks pass
- ✅ Docker services start and show "healthy" status
- ✅ pgvector extension is enabled in PostgreSQL
- ✅ Python dependencies import without errors
- ✅ SBERT model loads and generates 384-dim embeddings
- ✅ HDBSCAN initializes with spec parameters
- ✅ Redis accepts connections and pub/sub works
- ✅ PostgreSQL accepts connections via asyncpg

---

## Next Steps

Once all tests pass, proceed to Phase 2 (Foundational):
- T006-T010: Database schema creation
- T011-T014: Entity models
- T015-T018: Event service and FastAPI setup

See: `/specs/004-clustering-alignment/tasks.md` for Phase 2 tasks.
