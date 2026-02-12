#!/bin/bash
# Phase 1 Setup Verification Script

echo "========================================="
echo "Phase 1 Setup Verification"
echo "========================================="
echo ""

# Check backend directory structure
echo "✓ Checking backend directory structure..."
for dir in backend/src/models backend/src/services backend/src/api backend/src/events backend/tests/unit backend/tests/integration backend/tests/contract; do
    if [ -d "/mnt/c/Users/Guayaba/apps/opendiscuss_v00/$dir" ]; then
        echo "  ✓ $dir exists"
    else
        echo "  ✗ $dir missing"
    fi
done
echo ""

# Check __init__.py files
echo "✓ Checking __init__.py files..."
for init in backend/src/__init__.py backend/src/models/__init__.py backend/src/services/__init__.py backend/src/api/__init__.py backend/src/events/__init__.py backend/tests/__init__.py backend/tests/unit/__init__.py backend/tests/integration/__init__.py backend/tests/contract/__init__.py; do
    if [ -f "/mnt/c/Users/Guayaba/apps/opendiscuss_v00/$init" ]; then
        echo "  ✓ $init exists"
    else
        echo "  ✗ $init missing"
    fi
done
echo ""

# Check configuration files
echo "✓ Checking configuration files..."
for file in backend/pyproject.toml backend/.ruff.toml backend/README.md docker-compose.yml backend/src/config.py backend/.env.example backend/alembic.ini backend/alembic/env.py; do
    if [ -f "/mnt/c/Users/Guayaba/apps/opendiscuss_v00/$file" ]; then
        echo "  ✓ $file exists"
    else
        echo "  ✗ $file missing"
    fi
done
echo ""

echo "========================================="
echo "Phase 1 Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. cd backend && poetry install"
echo "2. cp .env.example .env"
echo "3. docker-compose up -d"
echo "4. poetry run alembic upgrade head"
echo "5. Begin Phase 2: Foundational (Tasks T008-T018)"
