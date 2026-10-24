# Cleaning rules (decision log)

Every problem found in the [profiling report](profiling_report.md) gets a rule.
The rules are implemented in the dbt **staging** model (step 4), and each one is checked by a **test**.

## Columns: keep or drop

**Drop (8 numeric codes):** `DeptID`, `PositionID`, `ManagerID`, `EmpStatusID`, `PerfScoreID`, `GenderID`,
`MaritalStatusID`, `MarriedID`.
**Why:** they duplicate a text label, and 5 of them are inconsistent (e.g. `Production` coded 5 and 6,
`Active` coded 1, 2 and 3, `Fully Meets` coded 3 and 1). The labels are consistent, so the labels are the
source of truth. The warehouse generates its own clean keys (step 2).

**Drop (redundant flag):** `FromDiversityJobFairID`. It equals `RecruitmentSource = 'Diversity Job Fair'`
on all 311 rows (verified).

**Keep:** everything else (27 columns), renamed to `snake_case`.

## Rules

| # | Column(s) | Problem | Rule | Test that proves it |
|---|---|---|---|---|
| R01 | all text columns | Leading/trailing spaces (`'M '`, `'Production       '`) | `TRIM`, and collapse double spaces inside names | no value differs from its trimmed version |
| R02 | `Sex` | `'M '` / `'F'` | trim, then map `F` → `Female`, `M` → `Male` | accepted values = {Female, Male} |
| R03 | `HispanicLatino` | `Yes`/`yes`/`No`/`no` | lower-case, then convert to boolean `is_hispanic_latino` | not null, boolean |
| R04 | `Employee_Name` | `'Last, First  M'` in one column | split on the comma into `last_name` and `first_name`, keep `full_name` as "First Last" | first_name and last_name not null |
| R05 | `DateofHire`, `DateofTermination`, `LastPerformanceReview_Date` | US dates stored as text (`7/5/2011`) | parse as `MM/DD/YYYY` into DATE | parses on every non-empty row |
| R06 | `DOB` | 2-digit year: default parsing puts 42 people in 2051–2068 | year = `19` + yy (verified: gives births 1951–1992, age at hire 19–63) | birth date < hire date, age at hire between 16 and 75 |
| R07 | `TermReason` | Placeholder `'N/A-StillEmployed'` on 207 rows | replace with NULL | NULL if and only if employee is active |
| R08 | `TermReason` | 17 free-text reasons, some odd (`'Fatal attraction'`) | map each reason to a category (career, compensation, conduct, personal…) via a reference file | every reason has a category |
| R09 | `DateofTermination` | 207 empty values | **Not an error**: empty = still employed. Keep NULL. | NULL if and only if `Termd = 0` (verified: always true) |
| R10 | `Termd`, `EmploymentStatus` | `0/1` flag + 3 text statuses | `is_terminated` boolean; `termination_type` = Voluntary / Involuntary / NULL | is_terminated matches termination date |
| R11 | `ManagerName` | 8 empty `ManagerID`, managers with 2 IDs | identify managers by **name** only (the ID is dropped) | every employee has a manager |
| R12 | `Zip` | `01960` would become `1960` as a number | keep as TEXT, left-pad to 5 digits | length = 5 |
| R13 | `EmpID` | Business key | keep as is; must stay unique | unique, not null |

## Business rules verified on the source (all OK)
- `Termd = 1` ⇔ `DateofTermination` filled ⇔ `EmploymentStatus` ≠ `Active` (311/311 rows)
- No termination date before the hire date
- Every name contains exactly one comma (safe to split)
