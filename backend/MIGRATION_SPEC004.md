# Spec 004: Clustering & Alignment Database Migration Guide

**Task**: T010 - Run database migrations to create all tables with pgvector support

**Date**: 2026-02-02

**Status**: Migration files created and ready to execute

---

## Migration Overview

This document provides instructions for running database migrations to set up Spec 004 tables for semantic clustering and cross-round alignment functionality.

### Migration Details

**Migration Revision ID**: `013_create_spec004_clustering`

**File Location**: `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/alembic/versions/013_create_spec004_clustering_tables.py`

**Depends On**: `012_summary_indexes` (Spec 003 summary table migration)

---

## What Gets Created

The migration creates four core tables for Spec 004:

### 1. **embeddings** Table
- **Purpose**: Stores semantic embedding vectors for approved summaries
- **Schema**:
  - `summary_id` (UUID, PRIMARY KEY, FK to summaries)
  - `embedding_vector` (pgvector(384), NOT NULL) - 384D SBERT vectors
  - `model_version` (VARCHAR(50), DEFAULT='all-MiniLM-L6-v2')
  - `created_at` (TIMESTAMP, DEFAULT=NOW())
- **Task**: T006
- **Indexes**:
  - `idx_embeddings_model_version` - for model version queries

### 2. **clusters** Table
- **Purpose**: Represents semantic groupings (thought spaces) of approved summaries
- **Schema**:
  - `cluster_id` (UUID, PRIMARY KEY)
  - `round_id` (UUID, FK to rounds)
  - `user_count` (INT, NOT NULL, CHECK > 0) - participants in cluster
  - `user_pct` (FLOAT, NOT NULL, CHECK 0 < x ≤ 1.0) - percentage of round
  - `label_summary_id` (UUID, FK to summaries) - medoid label
  - `centroid_vector` (pgvector(384), NOT NULL) - mean of member vectors
  - `display_group_id` (UUID, NULLABLE) - visual continuity across rounds
  - `created_at` (TIMESTAMP, DEFAULT=NOW())
- **Task**: T007
- **Indexes**:
  - `idx_clusters_round` - query all clusters in a round
  - `idx_clusters_label_summary` - lookup label summary
  - `idx_clusters_centroid` (IVFFlat) - cosine similarity search for alignment
  - `idx_clusters_display_group` - visual grouping queries

### 3. **cluster_members** Table
- **Purpose**: Join table linking clusters to member summaries and participants
- **Schema**:
  - `cluster_id` (UUID, FK to clusters, PRIMARY KEY)
  - `summary_id` (UUID, FK to summaries, PRIMARY KEY)
  - `user_id` (UUID, NOT NULL) - participant ID
  - **Constraint**: UNIQUE(cluster_id, user_id) - one user per cluster
- **Task**: T008
- **Indexes**:
  - `idx_cluster_members_summary` - find which cluster a summary belongs to
  - `idx_cluster_members_user` - find a user's cluster in a round

### 4. **alignment_maps** Table
- **Purpose**: Records cross-round alignment between semantically similar clusters
- **Schema**:
  - `alignment_id` (UUID, PRIMARY KEY)
  - `discussion_id` (UUID, FK to discussions)
  - `round_r` (INT, NOT NULL) - earlier round
  - `round_r1` (INT, NOT NULL) - later round (r+1)
  - `cluster_r_id` (UUID, FK to clusters)
  - `cluster_r1_id` (UUID, FK to clusters)
  - `similarity_score` (FLOAT, NOT NULL, CHECK 0 ≤ x ≤ 1.0)
  - `display_group_id` (UUID, NULLABLE) - visual alignment grouping
  - `created_at` (TIMESTAMP, DEFAULT=NOW())
  - **Constraint**: CHECK(round_r1 = round_r + 1) - adjacent rounds only
- **Task**: T009
- **Indexes**:
  - `idx_alignment_discussion` - discussion and round queries
  - `idx_alignment_display_group` - visual grouping lookups
  - `idx_alignment_clusters` - cluster pair lookups

### 5. **pgvector Extension**
- **Purpose**: Enables vector data type and operations
- **Action**: CREATE EXTENSION IF NOT EXISTS vector
- **Vectors**: 384-dimensional (SBERT all-MiniLM-L6-v2)
- **Operations**: Cosine similarity for alignment matching

---

## Prerequisites

### System Requirements
- PostgreSQL 15+ with `pgvector` extension available
- Python 3.11+
- Alembic 1.13+ (already configured in project)
- AsyncPG driver (for async database operations)

### Environment Setup
Ensure the following environment variables are configured in `.env`:

```bash
# Database connection (supports async URL format)
DATABASE_URL=postgresql+asyncpg://opendiscuss:opendiscuss_dev@localhost:5432/opendiscuss

# Optional: override via environment
export DATABASE_URL="postgresql+asyncpg://user:password@host:5432/db"
```

### Database Accessibility Verification

**Before running migrations, verify database connectivity:**

```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend

# Test database connection
python -c "
import asyncio
from src.config import settings
from sqlalchemy.ext.asyncio import create_async_engine

async def test_db():
    engine = create_async_engine(str(settings.database_url), echo=False)
    async with engine.connect() as conn:
        result = await conn.execute(__import__('sqlalchemy').text('SELECT 1'))
        print('✓ Database connection successful')
    await engine.dispose()

asyncio.run(test_db())
"
```

**If database is NOT accessible:**
- Do NOT run migrations
- Document the connection issue
- See "Manual SQL Execution" section below

---

## Running Migrations

### Option 1: Using Alembic (Recommended)

#### Standard Upgrade (Apply Latest Migration)

```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend

# Upgrade to the latest migration (013_create_spec004_clustering)
alembic upgrade head
```

**Expected Output:**
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 012_summary_indexes -> 013_create_spec004_clustering
```

#### Upgrade to Specific Migration

```bash
# If you only want to run up to a specific migration:
alembic upgrade 013_create_spec004_clustering
```

#### Verify Migration History

```bash
# Check applied migrations
alembic current
```

**Expected Output:**
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
013_create_spec004_clustering
```

### Option 2: Offline Migration (Generate SQL Without Executing)

**Use this to review SQL before applying:**

```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend

# Generate SQL without executing
alembic upgrade head --sql > migration_spec004.sql

# Review the generated SQL
cat migration_spec004.sql
```

**Expected output sample:**
```sql
-- Upgrade from 012_summary_indexes to 013_create_spec004_clustering

CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE embeddings (...)
CREATE INDEX idx_embeddings_model_version ON embeddings(model_version)
...
```

---

## Manual SQL Execution (If Database Unavailable)

If the database is not accessible during CI/CD or development, you can prepare and execute the SQL manually.

### Step 1: Extract SQL Script

```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend

# Generate the migration SQL
alembic upgrade head --sql > /tmp/spec004_migration.sql
```

### Step 2: Execute Manually via psql

```bash
# Connect to PostgreSQL and execute the script
psql postgresql://user:password@host:5432/db < /tmp/spec004_migration.sql
```

### Step 3: Record Migration in Alembic History

After manual execution, record the migration in Alembic's tracking table:

```bash
# Connect to database
psql postgresql://user:password@host:5432/db

-- Inside psql:
INSERT INTO alembic_version (version_num)
VALUES ('013_create_spec004_clustering');

-- Verify
SELECT * FROM alembic_version ORDER BY version_num;
```

---

## Verification

### 1. Verify Tables Were Created

```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend

python -c "
import asyncio
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from src.config import settings

async def verify():
    engine = create_async_engine(str(settings.database_url))
    async with engine.begin() as conn:
        inspector = inspect(conn.sync_engine)
        tables = inspector.get_table_names()
        required = ['embeddings', 'clusters', 'cluster_members', 'alignment_maps']
        for table in required:
            if table in tables:
                print(f'✓ {table} table exists')
            else:
                print(f'✗ {table} table MISSING')
    await engine.dispose()

asyncio.run(verify())
"
```

**Expected Output:**
```
✓ embeddings table exists
✓ clusters table exists
✓ cluster_members table exists
✓ alignment_maps table exists
```

### 2. Verify pgvector Extension

```bash
psql postgresql://user:password@host:5432/db -c "
SELECT * FROM pg_extension WHERE extname = 'vector';
"
```

**Expected Output:**
```
 oid | extname | extowner | extnamespace | extrelocatable | extversion | extconfig | extcondition
-----+---------+----------+--------------+----------------+------------+-----------+--------------
...  | vector  | 10      | 2200        | t              | 0.5.0      |           |
```

### 3. Verify Table Schemas

```bash
psql postgresql://user:password@host:5432/db

-- Check embeddings table
\d embeddings

-- Check clusters table with pgvector column
\d clusters

-- Check indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename IN ('embeddings', 'clusters', 'cluster_members', 'alignment_maps')
ORDER BY tablename, indexname;
```

### 4. Verify Constraints

```bash
psql postgresql://user:password@host:5432/db

-- Check primary keys
SELECT constraint_name, table_name, constraint_type
FROM information_schema.table_constraints
WHERE table_name IN ('embeddings', 'clusters', 'cluster_members', 'alignment_maps')
ORDER BY table_name, constraint_name;

-- Check foreign keys
SELECT constraint_name, table_name
FROM information_schema.table_constraints
WHERE constraint_type = 'FOREIGN KEY'
AND table_name IN ('embeddings', 'clusters', 'cluster_members', 'alignment_maps');
```

---

## Rollback

If you need to rollback the migration (useful for testing):

### Rollback to Previous Migration

```bash
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend

# Downgrade to previous migration (012_summary_indexes)
alembic downgrade 012_summary_indexes
```

**Expected Output:**
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
Running downgrade 013_create_spec004_clustering -> 012_summary_indexes
```

### Rollback All Custom Migrations

```bash
# Go back to base (drops all Spec 004 tables plus previous specs)
alembic downgrade base
```

**⚠️ WARNING**: This will drop ALL tables created by all migrations!

---

## Data Model Validation

### Constraint Validation Queries

After migration, run these queries to validate the data model:

#### 1. Verify user_pct Sum Constraint (FR-019, SC-005)

```sql
-- For each round, user_pct should sum to 1.0 ± 0.0001
SELECT
  round_id,
  COUNT(*) as cluster_count,
  SUM(user_pct) as total_pct,
  CASE
    WHEN SUM(user_pct) BETWEEN 0.9999 AND 1.0001 THEN '✓ VALID'
    ELSE '✗ INVALID - must sum to 1.0'
  END as status
FROM clusters
GROUP BY round_id;
```

#### 2. Verify 100% Participant Coverage (FR-016, SC-003)

```sql
-- All approved summaries in a round must be assigned to exactly one cluster
SELECT
  c.round_id,
  COUNT(DISTINCT cm.user_id) as assigned_users,
  (SELECT COUNT(DISTINCT participant_id)
   FROM summaries
   WHERE round_id = c.round_id AND status = 'approved') as total_users,
  CASE
    WHEN COUNT(DISTINCT cm.user_id) =
         (SELECT COUNT(DISTINCT participant_id)
          FROM summaries
          WHERE round_id = c.round_id AND status = 'approved')
    THEN '✓ 100% COVERAGE'
    ELSE '✗ COVERAGE INCOMPLETE'
  END as status
FROM clusters c
LEFT JOIN cluster_members cm ON c.cluster_id = cm.cluster_id
GROUP BY c.round_id;
```

#### 3. Verify Medoid Is Cluster Member (FR-024)

```sql
-- label_summary_id must be a member of its cluster
SELECT
  c.cluster_id,
  c.label_summary_id,
  CASE
    WHEN EXISTS(
      SELECT 1 FROM cluster_members cm
      WHERE cm.cluster_id = c.cluster_id
      AND cm.summary_id = c.label_summary_id
    ) THEN '✓ VALID - medoid is member'
    ELSE '✗ INVALID - medoid not in cluster'
  END as status
FROM clusters c;
```

#### 4. Verify Alignment Round Adjacency (FR-029)

```sql
-- round_r1 must equal round_r + 1
SELECT
  alignment_id,
  round_r,
  round_r1,
  CASE
    WHEN round_r1 = round_r + 1 THEN '✓ VALID - adjacent'
    ELSE '✗ INVALID - rounds not adjacent'
  END as status
FROM alignment_maps;
```

#### 5. Verify User Per Cluster Constraint (SC-003)

```sql
-- Each user_id should appear in exactly one cluster per round
SELECT
  c.round_id,
  cm.user_id,
  COUNT(*) as cluster_count,
  CASE
    WHEN COUNT(*) = 1 THEN '✓ VALID'
    WHEN COUNT(*) = 0 THEN '✗ USER NOT ASSIGNED'
    ELSE '✗ USER IN MULTIPLE CLUSTERS'
  END as status
FROM clusters c
INNER JOIN cluster_members cm ON c.cluster_id = cm.cluster_id
GROUP BY c.round_id, cm.user_id
HAVING COUNT(*) != 1;
```

---

## Performance Considerations

### Indexes for Clustering Operations

The migration creates specialized indexes for optimal performance:

1. **IVFFlat Index on centroid_vector** (100 lists)
   - Used for: Cross-round alignment similarity search
   - Operation: Cosine distance for centroid matching
   - Performance: O(log n) for nearest neighbor queries on 384D vectors

2. **Composite Index (discussion_id, round_r, round_r1)**
   - Used for: Fetching alignment maps for a discussion
   - Performance: O(log n) for range queries

3. **Index on display_group_id**
   - Used for: Visual grouping lookups in Sankey visualization
   - Performance: O(log n) for grouping queries

### Vector Operations Performance

For optimal pgvector performance:

```bash
# Analyze tables after data insertion
ANALYZE embeddings;
ANALYZE clusters;

# Reindex if performance degrades after many updates
REINDEX INDEX idx_clusters_centroid;
```

---

## Integration with Services

### Embedding Service (Spec 004 User Story 1)

After migration, the embedding service can persist vectors:

```python
from src.models import Embedding
import numpy as np

# Create embedding
embedding = await Embedding.create(
    db_session,
    summary_id=summary_id,
    embedding_vector=normalized_384d_vector,
    model_version="all-MiniLM-L6-v2"
)
await db_session.commit()
```

### Clustering Service (Spec 004 User Story 1)

After migration, clusters can be persisted:

```python
from src.models import Cluster, ClusterMember

# Create cluster
cluster = Cluster(
    cluster_id=uuid.uuid4(),
    round_id=round_id,
    user_count=3,
    user_pct=0.3,
    label_summary_id=medoid_id,
    centroid_vector=centroid_384d,
)
db_session.add(cluster)

# Add members
for user_id, summary_id in members:
    member = ClusterMember(
        cluster_id=cluster.cluster_id,
        summary_id=summary_id,
        user_id=user_id
    )
    db_session.add(member)

await db_session.commit()
```

### Alignment Service (Spec 004 User Story 4)

After migration, alignments can be recorded:

```python
from src.models import AlignmentMap

# Record alignment between clusters in adjacent rounds
alignment = AlignmentMap(
    alignment_id=uuid.uuid4(),
    discussion_id=discussion_id,
    round_r=1,
    round_r1=2,
    cluster_r_id=cluster_r_id,
    cluster_r1_id=cluster_r1_id,
    similarity_score=0.85,
    display_group_id=group_id
)
db_session.add(alignment)
await db_session.commit()
```

---

## Troubleshooting

### Issue: "pgvector extension not installed"

**Symptom**: Migration fails with `feature not supported`

**Solution**:
```bash
# Install pgvector extension on PostgreSQL server
# If you have superuser access:
psql -U postgres -d opendiscuss -c "CREATE EXTENSION vector;"

# If you don't have superuser access, ask your DBA to install it:
# They should run: CREATE EXTENSION vector;
```

### Issue: "Foreign key constraint violation"

**Symptom**: Migration fails because dependencies don't exist

**Solution**:
- Ensure all previous migrations have been applied
- Check that Spec 003 summary tables exist
- Verify that discussions and rounds tables exist

```bash
# Check migration status
alembic current

# If not on 012_summary_indexes, upgrade first
alembic upgrade 012_summary_indexes
```

### Issue: "Permission denied" on CREATE EXTENSION

**Symptom**: Migration fails with permission error for pgvector

**Solution**:
- Ensure database user has CREATEEXT privilege
- Ask DBA to grant privilege:
  ```sql
  ALTER USER opendiscuss CREATEDB;  -- May require superuser
  ```
- Or ask DBA to pre-install pgvector extension

### Issue: Alembic can't find migration

**Symptom**: `version not found` error

**Solution**:
```bash
# Ensure you're in the backend directory
cd /mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend

# Check that migration file exists
ls alembic/versions/013_*.py

# Verify it's readable
cat alembic/versions/013_create_spec004_clustering_tables.py | head -20
```

---

## Summary

**T010 Completion Checklist**:

- [x] Migration file created: `013_create_spec004_clustering_tables.py`
- [x] Migration includes pgvector extension creation
- [x] Migration creates embeddings table with 384D vector support
- [x] Migration creates clusters table with centroid vectors and display_group_id
- [x] Migration creates cluster_members join table with user/cluster uniqueness
- [x] Migration creates alignment_maps table with adjacent round constraint
- [x] All indexes created for performance (round, label, centroid IVFFlat, display_group)
- [x] Foreign keys established (dependencies on summaries, rounds, discussions)
- [x] Check constraints in place (user_count > 0, user_pct ∈ (0,1], round adjacency)
- [x] Migration instructions documented

**Migration Status**: ✓ READY TO EXECUTE

**Next Steps**:
1. Verify database is accessible
2. Run: `alembic upgrade head`
3. Verify tables exist and schemas are correct
4. Proceed with T011-T018 (entity models and services)

---

## References

- **Spec 004 Spec**: `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/specs/004-clustering-alignment/spec.md`
- **Database Schema SQL**: `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/models/database_schema.sql`
- **Alembic Configuration**: `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/alembic.ini`
- **Entity Models**:
  - Embedding: `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/models/embedding.py`
  - Cluster: `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/models/cluster.py`
  - ClusterMember: `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/models/cluster_member.py`
  - AlignmentMap: `/mnt/c/Users/Guayaba/apps/opendiscuss_v00/backend/src/models/alignment.py`

---

**Document Version**: 1.0
**Last Updated**: 2026-02-02
**Migration Type**: Schema Creation (DDL)
**Complexity**: Medium (pgvector, multiple tables with indexes and constraints)
