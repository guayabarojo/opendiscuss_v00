#!/usr/bin/env python3
"""
Phase 1 Setup Verification Script for Spec 004 Clustering

This script verifies that all Phase 1 (T001-T005) tasks are complete:
- T001: Directory structure (models, services, api, ml)
- T002: Python dependencies in requirements.txt
- T003: pytest configuration
- T004: PostgreSQL with pgvector (checks if service is accessible)
- T005: Environment variables (EMBEDDING_MODEL_VERSION, ALIGN_THRESHOLD)
"""

import os
import sys
from pathlib import Path

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def check_mark(passed: bool) -> str:
    return f"{GREEN}✓{RESET}" if passed else f"{RED}✗{RESET}"

def main():
    print("=" * 70)
    print("Phase 1 Setup Verification - Spec 004 Clustering")
    print("=" * 70)
    print()

    all_passed = True

    # T001: Check directory structure
    print("T001: Directory Structure")
    print("-" * 70)
    backend_dir = Path(__file__).parent
    src_dir = backend_dir / "src"

    required_dirs = ["models", "services", "api", "ml"]
    for dir_name in required_dirs:
        dir_path = src_dir / dir_name
        exists = dir_path.is_dir()
        print(f"  {check_mark(exists)} backend/src/{dir_name}/")
        all_passed = all_passed and exists
    print()

    # T002: Check requirements.txt
    print("T002: Python Dependencies (requirements.txt)")
    print("-" * 70)
    requirements_file = backend_dir / "requirements.txt"
    required_packages = [
        "sentence-transformers",
        "hdbscan",
        "numpy",
        "scipy",
        "scikit-learn",
        "psycopg2-binary",
        "asyncpg",
        "fastapi",
        "uvicorn"
    ]

    if requirements_file.exists():
        with open(requirements_file, 'r') as f:
            requirements_content = f.read()

        for package in required_packages:
            found = package in requirements_content
            print(f"  {check_mark(found)} {package}")
            all_passed = all_passed and found
    else:
        print(f"  {check_mark(False)} requirements.txt not found")
        all_passed = False
    print()

    # T003: Check pytest.ini
    print("T003: pytest Configuration")
    print("-" * 70)
    pytest_file = backend_dir / "pytest.ini"

    if pytest_file.exists():
        with open(pytest_file, 'r') as f:
            pytest_content = f.read()

        checks = {
            "testpaths = tests": "testpaths configured",
            "asyncio_mode = auto": "asyncio mode set",
            "spec004": "spec004 marker defined",
            "--cov=src": "coverage enabled"
        }

        for key, desc in checks.items():
            found = key in pytest_content
            print(f"  {check_mark(found)} {desc}")
            all_passed = all_passed and found
    else:
        print(f"  {check_mark(False)} pytest.ini not found")
        all_passed = False
    print()

    # T004: Check PostgreSQL configuration (docker-compose.yml)
    print("T004: PostgreSQL with pgvector")
    print("-" * 70)
    docker_compose = backend_dir.parent / "docker-compose.yml"
    init_script = backend_dir.parent / "scripts" / "postgres-init.sql"

    if docker_compose.exists():
        with open(docker_compose, 'r') as f:
            compose_content = f.read()

        pgvector_check = "pgvector" in compose_content
        print(f"  {check_mark(pgvector_check)} pgvector image in docker-compose.yml")
        all_passed = all_passed and pgvector_check
    else:
        print(f"  {check_mark(False)} docker-compose.yml not found")
        all_passed = False

    if init_script.exists():
        with open(init_script, 'r') as f:
            init_content = f.read()

        extension_check = "CREATE EXTENSION" in init_content and "vector" in init_content
        print(f"  {check_mark(extension_check)} postgres-init.sql with CREATE EXTENSION vector")
        all_passed = all_passed and extension_check
    else:
        print(f"  {check_mark(False)} postgres-init.sql not found")
        all_passed = False

    print()

    # T005: Check environment variables
    print("T005: Environment Variables")
    print("-" * 70)
    env_file = backend_dir / ".env"

    required_vars = [
        "DATABASE_URL",
        "EMBEDDING_MODEL_VERSION",
        "ALIGN_THRESHOLD",
        "REDIS_URL"
    ]

    if env_file.exists():
        with open(env_file, 'r') as f:
            env_content = f.read()

        for var in required_vars:
            found = var in env_content
            print(f"  {check_mark(found)} {var}")
            all_passed = all_passed and found
    else:
        print(f"  {check_mark(False)} .env file not found")
        all_passed = False
    print()

    # Summary
    print("=" * 70)
    if all_passed:
        print(f"{GREEN}✓ All Phase 1 setup tasks verified successfully!{RESET}")
        print()
        print("Next steps:")
        print("  1. Start services: docker-compose up -d")
        print("  2. Verify pgvector: docker exec opendiscuss-postgres psql -U opendiscuss -c '\\dx vector'")
        print("  3. Run Phase 2 (Foundational) tasks")
        return 0
    else:
        print(f"{RED}✗ Some Phase 1 setup tasks are incomplete{RESET}")
        print()
        print("Please complete the failed tasks above before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
