# 🧑‍💼 HR Analytics Pipeline

> End-to-end data pipeline: a raw HR system export goes through **Python ingestion**, **dbt transformations**
> and a **PostgreSQL star schema**, and ends up in a **Power BI dashboard**. Orchestrated with **Airflow**, runs in **Docker**.

🚧 **Work in progress.** Built step by step; see the roadmap below.

## Business questions
- How many employees do we have, and how has headcount changed over time?
- Who leaves, why, and from which department or manager?
- Which recruitment source brings employees who stay longer and perform better?
- Are engagement, absences and attrition related?

## Architecture

```
HR export (CSV) ─┐
Reference CSVs ──┤  ① Extract + Load (Python)
                 ▼
PostgreSQL:  raw ──② dbt──▶ staging ──▶ marts (star schema) ──③ dbt tests
                                              │
                                              ▼  ④
                                       Power BI dashboard
Airflow orchestrates ①②③ · everything runs in Docker
```

## Roadmap
- [x] **0. Setup:** repo structure, Dockerised PostgreSQL warehouse, toolbox container
- [x] **1. Data discovery:** [profiling report](docs/profiling_report.md) (22 issues) and [cleaning rules](docs/cleaning_rules.md)
- [x] **2. Data modeling:** [star schema and data dictionary](docs/data_model.md), reference files
- [x] **3. Extract + Load:** idempotent ingestion into `raw` (schema check, all-or-nothing, 8 tests)
- [x] **4. Transform:** dbt staging + 7 dimensions + 2 facts, 91 data tests (incl. reconciliation with the source)
- [ ] **5. Orchestration:** Airflow DAG
- [ ] **6. Power BI:** 4-page dashboard
- [ ] **7. Documentation and demo**

## Project structure
```
├── data/landing/      # incoming HR exports (source files)
├── data/reference/    # small lookup files (regions, reason categories)
├── ingestion/         # Python: extract + load into raw
├── dbt/               # dbt project: staging, marts, tests
├── dags/              # Airflow DAG
├── powerbi/           # .pbix dashboard + screenshots
├── sql/init/          # warehouse bootstrap (schemas)
├── scripts/           # helper scripts
├── docs/              # profiling report, data dictionary, diagrams
└── tests/
```

## Quick start
Requirements: Docker Desktop.
```bash
git clone https://github.com/AYMANETBAIK98/HR-ANALYTICS-PIPELINE.git
cd HR-ANALYTICS-PIPELINE
docker compose up -d                                       # start the warehouse
docker compose run --rm tools python scripts/check_setup.py   # check everything is ready
docker compose run --rm tools python -m ingestion.load_raw     # load data/landing/*.csv into raw
docker compose run --rm tools dbt build                        # seeds + models + data tests
docker compose run --rm tools pytest -v                        # run the Python tests
```

Warehouse connection (DBeaver, Power BI): host `localhost`, port `5434`, database `hr`, user `hr`, password `hr`.

## Data
[Human Resources Data Set](data/README.md) by Dr. Rich Huebner and Dr. Carla Patalano: a **fictional** dataset
created for teaching HR analytics (311 employees, 36 columns).
