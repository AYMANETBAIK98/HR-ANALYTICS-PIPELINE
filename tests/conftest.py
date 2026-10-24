"""Shared test setup.

Tests run against a separate database, hr_test, so they never touch your real data.
It is created automatically the first time.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TEST_DB = "hr_test"


def _dsn(dbname: str) -> str:
    return (
        f"host={os.getenv('WAREHOUSE_HOST', 'localhost')} port={os.getenv('WAREHOUSE_PORT', '5434')} "
        f"dbname={dbname} user={os.getenv('WAREHOUSE_USER', 'hr')} "
        f"password={os.getenv('WAREHOUSE_PASSWORD', 'hr')}"
    )


@pytest.fixture
def test_dsn() -> str:
    """A clean, empty hr_test database for each test."""
    try:
        admin = psycopg2.connect(_dsn(os.getenv("WAREHOUSE_DB", "hr")))
    except psycopg2.OperationalError:
        pytest.skip("warehouse not reachable (start it with: docker compose up -d)")
    admin.autocommit = True  # CREATE DATABASE cannot run inside a transaction
    with admin.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,))
        if cur.fetchone() is None:
            cur.execute(f"CREATE DATABASE {TEST_DB}")
    admin.close()

    dsn = _dsn(TEST_DB)
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS raw CASCADE; DROP SCHEMA IF EXISTS monitoring CASCADE;")
    return dsn


@pytest.fixture
def landing(tmp_path) -> Path:
    """An empty, temporary landing folder."""
    folder = tmp_path / "landing"
    folder.mkdir()
    return folder


@pytest.fixture
def source_file() -> Path:
    return ROOT / "data" / "landing" / "HRDataset_v14.csv"
