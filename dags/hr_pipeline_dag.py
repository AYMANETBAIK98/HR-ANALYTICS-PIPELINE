"""Airflow DAG: HR analytics pipeline.

    check_landing -> ingest_raw -> new_data_or_forced? -> dbt_seed -> dbt_build_staging -> dbt_build_marts -> summary

Runs on the 1st of every month (when the HR system drops its monthly export),
and can be triggered by hand at any time from the Airflow UI.

Key ideas:
  - ingest_raw is idempotent (step 3): re-running it never duplicates data
  - if no new file arrived, the dbt tasks are SKIPPED (nothing to rebuild),
    unless you trigger the DAG with the parameter force_rebuild = true
  - staging is built and tested BEFORE marts: if a cleaning test fails, the marts
    are NOT rebuilt, so Power BI keeps showing the last good data
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import Param, dag, get_current_context, task

# The project root (one level above dags/) holds the ingestion package
PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_DIR))

log = logging.getLogger(__name__)

# dbt lives in its own virtual environment inside the Airflow image (see Dockerfile.airflow)
DBT = os.getenv("DBT_BIN", "/opt/dbt-venv/bin/dbt")
# dbt writes its build artefacts to /tmp, not into the project folder
DBT_FLAGS = "--target-path /tmp/dbt/target --log-path /tmp/dbt/logs"


@dag(
    dag_id="hr_pipeline",
    description="HR export (CSV) -> raw -> dbt staging -> dbt marts (star schema for Power BI)",
    schedule="0 7 1 * *",              # 07:00 UTC on the 1st day of every month
    start_date=datetime(2026, 10, 1),
    catchup=False,                     # do not replay the months before start_date
    max_active_runs=1,                 # never two runs at the same time
    default_args={
        "owner": "ayman",
        "retries": 0,                  # data problems need a human, not a retry
        "execution_timeout": timedelta(minutes=30),
    },
    params={
        "force_rebuild": Param(False, type="boolean",
                               description="Rebuild the dbt models even if no new file was loaded"),
    },
    tags=["portfolio", "hr", "dbt"],
)
def hr_pipeline():

    @task
    def check_landing() -> list[str]:
        """Fail early, with a clear message, if the drop folder is empty."""
        files = sorted(p.name for p in (PROJECT_DIR / "data" / "landing").glob("*.csv"))
        if not files:
            raise FileNotFoundError("No CSV file in data/landing/: has the HR export been delivered?")
        log.info("Files in landing: %s", files)
        return files

    @task(retries=2, retry_delay=timedelta(minutes=2))  # a database hiccup is worth a retry
    def ingest_raw() -> int:
        """EXTRACT + LOAD (step 3). Returns the number of rows loaded (0 if nothing new)."""
        from ingestion import load_raw
        results = load_raw.run()
        for r in results:
            log.info("%-25s %-8s %d rows", r.file_name, r.status, r.rows)
        return sum(r.rows for r in results)

    @task.short_circuit
    def new_data_or_forced(rows_loaded: int) -> bool:
        """Returns True -> continue. Returns False -> skip every task after this one."""
        forced = get_current_context()["params"]["force_rebuild"]
        if rows_loaded:
            log.info("%d new rows loaded: rebuilding the models", rows_loaded)
            return True
        if forced:
            log.info("No new file, but force_rebuild = true: rebuilding anyway")
            return True
        log.info("No new file and no force_rebuild: nothing to do, skipping dbt")
        return False

    dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command=f"{DBT} seed {DBT_FLAGS}",
    )

    # build + test the cleaning layer first (only the tests whose inputs are all staging)
    dbt_build_staging = BashOperator(
        task_id="dbt_build_staging",
        bash_command=f"{DBT} build --select staging --indirect-selection cautious {DBT_FLAGS}",
    )

    # then the star schema + its tests (incl. reconciliation with the source)
    dbt_build_marts = BashOperator(
        task_id="dbt_build_marts",
        bash_command=f"{DBT} build --select marts {DBT_FLAGS}",
    )

    @task
    def summary() -> dict:
        """Log the size of every Power BI table, so each run leaves a readable trace."""
        import psycopg2
        from ingestion.load_raw import get_dsn
        tables = ["fact_employment", "fact_headcount_monthly", "dim_employee", "dim_department",
                  "dim_position", "dim_manager", "dim_recruitment_source", "dim_term_reason", "dim_date"]
        with psycopg2.connect(get_dsn()) as conn, conn.cursor() as cur:
            counts = {}
            for t in tables:
                cur.execute(f"SELECT COUNT(*) FROM marts.{t}")
                counts[t] = cur.fetchone()[0]
        for t, n in counts.items():
            log.info("marts.%-24s %7d rows", t, n)
        return counts

    files = check_landing()
    rows = ingest_raw()
    gate = new_data_or_forced(rows)
    files >> rows
    gate >> dbt_seed >> dbt_build_staging >> dbt_build_marts >> summary()


hr_pipeline()
