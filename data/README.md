# Data sources

## `landing/HRDataset_v14.csv`
**Human Resources Data Set (v14)**, by Dr. Rich Huebner and Dr. Carla Patalano (New England College of Business),
published on Kaggle for teaching HR analytics.

- Fictional data: it does not describe real people.
- 311 rows (one per employee), 36 columns.
- Used here unchanged, as the "raw export from the HR system" that the pipeline ingests.

`landing/` plays the role of the drop folder where an HR system would deliver its exports.
The ingestion step loads each new file into the `raw` schema only once.

## `reference/`
Small lookup tables created for this project (added in step 2).
