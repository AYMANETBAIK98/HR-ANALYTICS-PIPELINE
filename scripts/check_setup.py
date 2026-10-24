"""Step 0 check: is the environment ready?

    docker compose run --rm tools python scripts/check_setup.py

Checks that:
  1. the warehouse database is reachable
  2. the 4 schemas exist
  3. the HR source file is in data/landing/ and readable
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import psycopg2

ROOT = Path(__file__).resolve().parent.parent
LANDING = ROOT / "data" / "landing"
EXPECTED_SCHEMAS = {"raw", "staging", "marts", "monitoring"}


def dsn() -> str:
    return (
        f"host={os.getenv('WAREHOUSE_HOST', 'localhost')} "
        f"port={os.getenv('WAREHOUSE_PORT', '5434')} "
        f"dbname={os.getenv('WAREHOUSE_DB', 'hr')} "
        f"user={os.getenv('WAREHOUSE_USER', 'hr')} "
        f"password={os.getenv('WAREHOUSE_PASSWORD', 'hr')}"
    )


def main() -> int:
    ok = True

    # 1 + 2: database and schemas
    try:
        with psycopg2.connect(dsn()) as conn, conn.cursor() as cur:
            cur.execute("SELECT version()")
            print(f"[OK]   Database reachable: {cur.fetchone()[0].split(',')[0]}")
            cur.execute("SELECT schema_name FROM information_schema.schemata")
            found = {r[0] for r in cur.fetchall()} & EXPECTED_SCHEMAS
            missing = EXPECTED_SCHEMAS - found
            if missing:
                ok = False
                print(f"[FAIL] Missing schemas: {sorted(missing)}")
            else:
                print(f"[OK]   Schemas present: {sorted(found)}")
    except psycopg2.OperationalError as exc:
        ok = False
        print(f"[FAIL] Cannot connect to the database: {exc}")

    # 3: source file
    files = sorted(LANDING.glob("*.csv"))
    if not files:
        ok = False
        print(f"[FAIL] No CSV file in {LANDING}")
    for f in files:
        df = pd.read_csv(f, encoding="utf-8-sig")
        print(f"[OK]   Source file {f.name}: {len(df)} rows x {len(df.columns)} columns")

    print("\nEnvironment ready. On to step 1!" if ok else "\nSomething is missing, see [FAIL] lines above.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
