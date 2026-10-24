"""EXTRACT + LOAD: copy the HR exports from data/landing/ into raw.hr_employees.

    docker compose run --rm tools python -m ingestion.load_raw

Rules this script guarantees:
  1. RAW = AS-IS     every value is stored as TEXT, exactly as in the file (cleaning is dbt's job)
  2. IDEMPOTENT      a file already loaded is skipped, so running the script 10 times = running it once
  3. SCHEMA CHECK    a file whose columns differ from what we expect is rejected before loading
  4. ALL OR NOTHING  rows + log entry are written in ONE transaction: a crash never leaves half a file
  5. TRACEABLE       every row knows which file it came from; every file run is logged
"""
from __future__ import annotations

import csv
import hashlib
import io
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg2

log = logging.getLogger("ingestion")

ROOT = Path(__file__).resolve().parent.parent
LANDING_DIR = ROOT / "data" / "landing"
RAW_TABLE = "raw.hr_employees"

# The 36 columns we expect, in the source's own spelling.
# If the HR system adds, removes or renames a column, we want to KNOW, not guess.
EXPECTED_COLUMNS = [
    "Employee_Name", "EmpID", "MarriedID", "MaritalStatusID", "GenderID", "EmpStatusID", "DeptID",
    "PerfScoreID", "FromDiversityJobFairID", "Salary", "Termd", "PositionID", "Position", "State",
    "Zip", "DOB", "Sex", "MaritalDesc", "CitizenDesc", "HispanicLatino", "RaceDesc", "DateofHire",
    "DateofTermination", "TermReason", "EmploymentStatus", "Department", "ManagerName", "ManagerID",
    "RecruitmentSource", "PerformanceScore", "EngagementSurvey", "EmpSatisfaction",
    "SpecialProjectsCount", "LastPerformanceReview_Date", "DaysLateLast30", "Absences",
]
# In PostgreSQL we use lower-case column names (no quotes needed in SQL): "DateofHire" -> dateofhire
DB_COLUMNS = [c.lower() for c in EXPECTED_COLUMNS]


class SchemaError(ValueError):
    """The file does not have the columns we expect."""


@dataclass
class LoadResult:
    file_name: str
    status: str          # loaded / skipped
    rows: int = 0


def get_dsn() -> str:
    return (
        f"host={os.getenv('WAREHOUSE_HOST', 'localhost')} "
        f"port={os.getenv('WAREHOUSE_PORT', '5434')} "
        f"dbname={os.getenv('WAREHOUSE_DB', 'hr')} "
        f"user={os.getenv('WAREHOUSE_USER', 'hr')} "
        f"password={os.getenv('WAREHOUSE_PASSWORD', 'hr')}"
    )


# ---------------------------------------------------------------- setup
def create_tables(conn) -> None:
    """Create the raw table and the ingestion log if they do not exist yet."""
    data_columns = ",\n    ".join(f"{c} TEXT" for c in DB_COLUMNS)
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS raw; CREATE SCHEMA IF NOT EXISTS monitoring;")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {RAW_TABLE} (
                {data_columns},
                _source_file  TEXT        NOT NULL,   -- which file the row came from
                _file_hash    TEXT        NOT NULL,   -- fingerprint of that file
                _row_number   INT         NOT NULL,   -- line number in the file
                _loaded_at    TIMESTAMPTZ NOT NULL DEFAULT now()
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS monitoring.ingestion_log (
                ingestion_id  BIGSERIAL   PRIMARY KEY,
                file_name     TEXT        NOT NULL,
                file_hash     TEXT        NOT NULL UNIQUE,   -- UNIQUE = the same content can never be logged twice
                target_table  TEXT        NOT NULL,
                rows_loaded   INT         NOT NULL,
                loaded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
            )""")
    conn.commit()


# ---------------------------------------------------------------- extract
def file_fingerprint(path: Path) -> str:
    """SHA-256 of the file content. Same content => same fingerprint, whatever the file name."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv_as_text(path: Path) -> list[list[str]]:
    """Read the file with the standard csv module: no type guessing, values stay exactly as written.
    Returns the data rows; raises SchemaError if the header is not the expected one."""
    with path.open(encoding="utf-8-sig", newline="") as f:   # utf-8-sig removes the invisible BOM
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            raise SchemaError(f"{path.name} is empty")
        check_header(path.name, header)
        rows = [row for row in reader if row]                # skip fully blank lines
    for i, row in enumerate(rows, start=2):
        if len(row) != len(EXPECTED_COLUMNS):
            raise SchemaError(f"{path.name} line {i}: {len(row)} values, expected {len(EXPECTED_COLUMNS)}")
    return rows


def check_header(file_name: str, header: list[str]) -> None:
    missing = [c for c in EXPECTED_COLUMNS if c not in header]
    extra = [c for c in header if c not in EXPECTED_COLUMNS]
    if missing or extra:
        raise SchemaError(f"{file_name}: unexpected columns. Missing: {missing or 'none'}. Extra: {extra or 'none'}")
    if header != EXPECTED_COLUMNS:
        raise SchemaError(f"{file_name}: columns are in a different order than expected")


# ---------------------------------------------------------------- load
def already_loaded(conn, file_hash: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM monitoring.ingestion_log WHERE file_hash = %s", (file_hash,))
        return cur.fetchone() is not None


def load_file(conn, path: Path) -> LoadResult:
    file_hash = file_fingerprint(path)
    if already_loaded(conn, file_hash):
        log.info("SKIP  %s (same content already loaded)", path.name)
        return LoadResult(path.name, "skipped")

    rows = read_csv_as_text(path)

    # Build an in-memory CSV with the 36 values + our 3 tracking columns, then COPY it in one go.
    # COPY is PostgreSQL's bulk loader: much faster than one INSERT per row.
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for line_number, row in enumerate(rows, start=2):          # line 1 is the header
        values = [v if v != "" else None for v in row]         # empty cell -> NULL
        writer.writerow([*values, path.name, file_hash, line_number])
    buffer.seek(0)

    columns = ", ".join([*DB_COLUMNS, "_source_file", "_file_hash", "_row_number"])
    try:
        with conn.cursor() as cur:
            cur.copy_expert(f"COPY {RAW_TABLE} ({columns}) FROM STDIN WITH (FORMAT csv)", buffer)
            cur.execute(
                """INSERT INTO monitoring.ingestion_log (file_name, file_hash, target_table, rows_loaded)
                   VALUES (%s, %s, %s, %s)""",
                (path.name, file_hash, RAW_TABLE, len(rows)),
            )
        conn.commit()      # rows and log entry become visible TOGETHER...
    except Exception:
        conn.rollback()    # ...or not at all
        raise

    log.info("LOAD  %s: %d rows -> %s", path.name, len(rows), RAW_TABLE)
    return LoadResult(path.name, "loaded", len(rows))


def run(landing_dir: Path = LANDING_DIR, dsn: str | None = None) -> list[LoadResult]:
    files = sorted(landing_dir.glob("*.csv"))
    if not files:
        log.warning("No CSV file found in %s", landing_dir)
        return []
    conn = psycopg2.connect(dsn or get_dsn())
    try:
        create_tables(conn)
        return [load_file(conn, f) for f in files]
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    try:
        results = run()
    except SchemaError as exc:
        log.error("REJECTED: %s", exc)
        sys.exit(1)
    loaded = sum(r.rows for r in results)
    print(f"\nDone: {sum(r.status == 'loaded' for r in results)} file(s) loaded ({loaded} rows), "
          f"{sum(r.status == 'skipped' for r in results)} skipped.")
