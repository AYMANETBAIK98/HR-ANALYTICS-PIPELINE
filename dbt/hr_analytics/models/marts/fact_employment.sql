-- FACT: one row per employee (grain = employee).
-- Foreign keys to every dimension + the measures Power BI will sum / average.
{% set as_of = "'" ~ var('as_of_date') ~ "'::date" %}

select
    -- keys to the dimensions -------------------------------------------------
    emp.employee_key,
    dep.department_key,
    pos.position_key,
    mgr.manager_key,
    src.recruitment_source_key,
    coalesce(trm.term_reason_key, -1)                          as term_reason_key,   -- -1 = still employed
    to_char(e.hire_date, 'YYYYMMDD')::int                      as hire_date_key,
    to_char(e.termination_date, 'YYYYMMDD')::int               as termination_date_key,
    to_char(e.last_review_date, 'YYYYMMDD')::int               as last_review_date_key,

    -- measures and facts ------------------------------------------------------
    e.salary,
    e.performance_score,
    e.performance_rank,
    e.engagement_score,
    e.satisfaction_score,
    e.special_projects_count,
    e.days_late_last_30,
    e.absences,
    e.is_terminated,
    e.termination_type,
    -- tenure: until the termination date, or until the as-of date for active employees
    coalesce(e.termination_date, {{ as_of }}) - e.hire_date    as tenure_days,
    extract(year from age(e.hire_date, e.birth_date))::int     as age_at_hire
from {{ ref('stg_hr_employees') }}        e
join {{ ref('dim_employee') }}            emp on emp.emp_id            = e.emp_id
join {{ ref('dim_department') }}          dep on dep.department_name   = e.department_name
join {{ ref('dim_position') }}            pos on pos.position_title    = e.position_title
join {{ ref('dim_manager') }}             mgr on mgr.manager_name      = e.manager_name
join {{ ref('dim_recruitment_source') }}  src on src.recruitment_source = e.recruitment_source
left join {{ ref('dim_term_reason') }}    trm on trm.term_reason       = e.term_reason
