"""Tests for ingestion/load_raw.py - each test proves one promise of the script.

    docker compose run --rm tools pytest -v
"""
import shutil

import psycopg2
import pytest

from ingestion import load_raw


def query(dsn, sql):
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def test_loads_every_row_of_the_file(test_dsn, landing, source_file):
    shutil.copy(source_file, landing)
    results = load_raw.run(landing, test_dsn)
    assert results[0].status == "loaded" and results[0].rows == 311
    assert query(test_dsn, "SELECT COUNT(*) FROM raw.hr_employees") == [(311,)]


def test_values_are_stored_exactly_as_in_the_file(test_dsn, landing, source_file):
    """RAW = AS-IS: spaces, leading zeros and placeholders must survive untouched."""
    shutil.copy(source_file, landing)
    load_raw.run(landing, test_dsn)
    row = query(test_dsn, "SELECT department, sex, zip, dob, termreason, dateoftermination "
                          "FROM raw.hr_employees WHERE empid = '10026'")[0]
    assert row == ("Production       ", "M ", "01960", "07/10/83", "N/A-StillEmployed", None)


def test_running_twice_loads_once(test_dsn, landing, source_file):
    """IDEMPOTENT: the second run skips the file."""
    shutil.copy(source_file, landing)
    load_raw.run(landing, test_dsn)
    second = load_raw.run(landing, test_dsn)
    assert second[0].status == "skipped"
    assert query(test_dsn, "SELECT COUNT(*) FROM raw.hr_employees") == [(311,)]
    assert query(test_dsn, "SELECT COUNT(*) FROM monitoring.ingestion_log") == [(1,)]


def test_same_content_under_another_name_is_skipped(test_dsn, landing, source_file):
    """The fingerprint is based on content, not on the file name."""
    shutil.copy(source_file, landing / "export_a.csv")
    shutil.copy(source_file, landing / "export_b.csv")
    results = load_raw.run(landing, test_dsn)
    assert [r.status for r in results] == ["loaded", "skipped"]


def test_a_new_export_is_loaded(test_dsn, landing, source_file):
    """A file with different content (next month's export) is loaded on top."""
    shutil.copy(source_file, landing / "export_jan.csv")
    load_raw.run(landing, test_dsn)
    lines = source_file.read_text(encoding="utf-8-sig").splitlines()
    (landing / "export_feb.csv").write_text("\n".join(lines[:11]) + "\n", encoding="utf-8")  # header + 10 rows
    results = load_raw.run(landing, test_dsn)
    assert [(r.file_name, r.status, r.rows) for r in results] == [
        ("export_feb.csv", "loaded", 10), ("export_jan.csv", "skipped", 0)]
    assert query(test_dsn, "SELECT _source_file, COUNT(*) FROM raw.hr_employees GROUP BY 1 ORDER BY 1") == [
        ("export_feb.csv", 10), ("export_jan.csv", 311)]


def test_file_with_a_missing_column_is_rejected(test_dsn, landing, source_file):
    """SCHEMA CHECK: a changed file is refused and nothing is written."""
    lines = source_file.read_text(encoding="utf-8-sig").splitlines()
    broken = [line.replace(",Absences", "") for line in lines[:1]] + lines[1:]
    (landing / "broken.csv").write_text("\n".join(broken), encoding="utf-8")
    with pytest.raises(load_raw.SchemaError, match="Missing: \\['Absences'\\]"):
        load_raw.run(landing, test_dsn)
    assert query(test_dsn, "SELECT COUNT(*) FROM raw.hr_employees") == [(0,)]


def test_failure_during_load_leaves_nothing_behind(test_dsn, landing, source_file, monkeypatch):
    """ALL OR NOTHING: if the log insert fails, the rows are rolled back too."""
    shutil.copy(source_file, landing)
    conn = psycopg2.connect(test_dsn)
    load_raw.create_tables(conn)
    with conn.cursor() as cur:  # sabotage: make the log insert fail
        cur.execute("ALTER TABLE monitoring.ingestion_log ADD CONSTRAINT sabotage CHECK (rows_loaded < 0)")
    conn.commit()
    with pytest.raises(psycopg2.errors.CheckViolation):
        load_raw.load_file(conn, landing / source_file.name)
    conn.close()
    assert query(test_dsn, "SELECT COUNT(*) FROM raw.hr_employees") == [(0,)]


def test_every_row_is_traceable(test_dsn, landing, source_file):
    shutil.copy(source_file, landing)
    load_raw.run(landing, test_dsn)
    rows = query(test_dsn, "SELECT MIN(_row_number), MAX(_row_number), COUNT(DISTINCT _file_hash) "
                           "FROM raw.hr_employees")
    assert rows == [(2, 312, 1)]
