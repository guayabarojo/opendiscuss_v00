-- PostgreSQL Initialization Script
-- This script runs when the PostgreSQL container is first created

-- Enable pgvector extension for vector similarity search (Spec 004: Clustering)
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify extension is installed
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
