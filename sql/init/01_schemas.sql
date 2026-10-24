-- Runs automatically the first time the warehouse container starts.
-- Layers of the warehouse:
--   raw        : source files loaded as-is (all text), never modified
--   staging    : cleaned and typed data            (built by dbt)
--   marts      : star schema used by Power BI       (built by dbt)
--   monitoring : ingestion log (which file was loaded, when, how many rows)
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;
CREATE SCHEMA IF NOT EXISTS monitoring;
