-- Every hire, termination and review date must exist in dim_date, otherwise Power BI loses rows.
with all_dates as (
    select hire_date as d from {{ ref('stg_hr_employees') }}
    union select termination_date from {{ ref('stg_hr_employees') }} where termination_date is not null
    union select last_review_date from {{ ref('stg_hr_employees') }}
)
select d from all_dates
where d not in (select full_date from {{ ref('dim_date') }})
