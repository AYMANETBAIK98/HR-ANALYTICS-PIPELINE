"""DAG integrity tests. Skipped automatically when Airflow is not installed
(the tools container has no Airflow; run them inside the Airflow container):

    docker compose exec airflow pytest /opt/airflow/project/tests/test_dag.py -v
"""
from pathlib import Path

import pytest

pytest.importorskip("airflow")
from airflow.models import DagBag  # noqa: E402

DAGS = Path(__file__).resolve().parent.parent / "dags"


@pytest.fixture(scope="module")
def dag():
    bag = DagBag(dag_folder=str(DAGS), include_examples=False)
    assert bag.import_errors == {}, bag.import_errors
    return bag.get_dag("hr_pipeline")


def test_dag_is_found(dag):
    assert dag is not None


def test_task_order(dag):
    chain = ["check_landing", "ingest_raw", "new_data_or_forced", "dbt_seed",
             "dbt_build_staging", "dbt_build_marts", "summary"]
    for upstream, downstream in zip(chain, chain[1:]):
        assert downstream in dag.get_task(upstream).downstream_task_ids, f"{upstream} -> {downstream}"


def test_staging_is_built_before_marts(dag):
    """If cleaning tests fail, the marts used by Power BI must not be rebuilt."""
    assert "dbt_build_staging" in dag.get_task("dbt_build_marts").upstream_task_ids


def test_retries(dag):
    assert dag.get_task("ingest_raw").retries == 2
    assert dag.get_task("dbt_build_marts").retries == 0


def test_monthly_schedule(dag):
    assert str(dag.timetable.summary) == "0 7 1 * *"
