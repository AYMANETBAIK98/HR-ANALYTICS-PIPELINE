# Power BI guide: connecting to the warehouse and building the model

Prerequisites: Power BI Desktop (free, Microsoft Store), and the warehouse running (`docker compose up -d`)
with the marts built (`dbt build` or the Airflow DAG).

## 1. Connect (Import mode)
1. **Home > Get data > PostgreSQL database**
2. Server: `localhost:5434` · Database: `hr` · Data connectivity mode: **Import**
3. Credentials, **Database** tab: user `hr`, password `hr`
   - If you get an *encryption / SSL* error: click OK to connect without encryption
     (or **File > Options > Data source settings > Edit permissions > untick Encrypt connections**).
4. In the Navigator, tick the **9 tables of the `marts` schema** (`marts.dim_*`, `marts.fact_*`) > **Load**.

**Why Import and not DirectQuery?** The data is small (~19k rows) and only changes monthly. Import copies it
into Power BI, so visuals are instant and DAX is unrestricted. Click **Refresh** after each pipeline run.

## 2. Rename the tables
Power BI names them `marts dim_date`, etc. Rename each one (double-click in the Data pane) to drop the
`marts ` prefix, so the names match `powerbi/measures.dax`: `dim_date`, `fact_employment`, …

## 3. Relationships (Model view)
Power BI auto-detects some links. Check them against this list, delete anything else, add what is missing.
All are **many-to-one (*:1), single direction** (filters flow from the dimension to the fact).

| From (many) | To (one) | Active? |
|---|---|---|
| fact_employment[employee_key] | dim_employee[employee_key] | ✅ |
| fact_employment[department_key] | dim_department[department_key] | ✅ |
| fact_employment[position_key] | dim_position[position_key] | ✅ |
| fact_employment[manager_key] | dim_manager[manager_key] | ✅ |
| fact_employment[recruitment_source_key] | dim_recruitment_source[recruitment_source_key] | ✅ |
| fact_employment[term_reason_key] | dim_term_reason[term_reason_key] | ✅ |
| fact_employment[hire_date_key] | dim_date[date_key] | ❌ inactive |
| fact_employment[termination_date_key] | dim_date[date_key] | ❌ inactive |
| fact_employment[last_review_date_key] | dim_date[date_key] | ❌ inactive |
| fact_headcount_monthly[month_end_date_key] | dim_date[date_key] | ✅ |
| fact_headcount_monthly[employee_key] | dim_employee[employee_key] | ✅ |
| fact_headcount_monthly[department_key] | dim_department[department_key] | ✅ |
| fact_headcount_monthly[position_key] | dim_position[position_key] | ✅ |
| fact_headcount_monthly[manager_key] | dim_manager[manager_key] | ✅ |

**Why are the 3 date links of `fact_employment` inactive?** `dim_date` plays three roles for an employee
(hire, termination, review date): a *role-playing dimension*. Power BI allows only one active path between
two tables. Keeping them inactive means the date slicer drives the **time-based** measures (headcount,
hires, terminations, attrition) and leaves the **snapshot** measures (salary, engagement…) unchanged.
The measures `Leavers by Termination Date` and `Hires by Hire Date` switch one on with `USERELATIONSHIP`.

## 4. Model settings
- **dim_date**: select the table > *Table tools* > **Mark as date table** > column `full_date`.
- **dim_date[month_name]**: *Column tools* > **Sort by column** > `month`. Same for `month_short`.
- **dim_term_reason[term_reason_category]**: fine as is ("Not applicable" will appear for active employees).
- Hide every `*_key` column (right-click > Hide in report view): report users should see names, not IDs.

## 5. Measures
Create a table for measures: **Home > Enter data** > name it `_Measures` > Load.
Then add every measure from [`powerbi/measures.dax`](../powerbi/measures.dax) (**New measure**, paste, Enter).
Format `Attrition Rate`, `% Left`, `Retention Rate`, `Voluntary Share` as **Percentage** (1 decimal),
and `Avg Salary` as **Currency**.

## 6. Check your measures against the warehouse
Put these in a table visual with `dim_date[year]` and compare. They were computed in SQL on the marts.

| Year | Hires | Terminations | Headcount | Attrition Rate |
|---|---|---|---|---|
| 2011 | 83 | 3 | 101 | 4.3 % |
| 2014 | 60 | 13 | 216 | 6.7 % |
| 2015 | 36 | 23 | 229 | 9.6 % |
| 2016 | 14 | 22 | 221 | 9.9 % |
| 2018 | 1 | 13 | 207 | 6.1 % |

Snapshot cards (no filter): Employees **311**, Active **207**, Leavers **104**, Avg Salary **69,021**,
Avg Tenure **4.82** years, Avg Engagement **4.11**, Voluntary Share **84.6 %**.
