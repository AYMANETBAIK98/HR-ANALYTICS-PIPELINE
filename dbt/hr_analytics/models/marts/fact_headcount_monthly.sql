-- FACT: one row per employee per month in which they were employed for at least one day
-- (grain = employee x month). Built from only two dates: hire date and termination date.
--
--   headcount at month end   = rows where is_active_at_month_end
--   hires in a month         = rows where is_hire_month
--   terminations in a month  = rows where is_termination_month
--
-- Limitation (see docs/data_model.md): the source only knows each employee's CURRENT
-- department / position / manager, so we assume they never changed.
{% set as_of = "'" ~ var('as_of_date') ~ "'::date" %}

with employees as (
    select
        emp_id,
        department_name,
        position_title,
        manager_name,
        hire_date,
        termination_date,
        date_trunc('month', hire_date)::date                             as first_month,
        date_trunc('month', coalesce(termination_date, {{ as_of }}))::date as last_month
    from {{ ref('stg_hr_employees') }}
),

-- one row per employee per month: we add 0, 1, 2 ... months to the first month
-- (integer month offsets, not a timestamp series, so time zones cannot shift a month)
employee_months as (
    select
        e.*,
        (e.first_month + make_interval(months => n))::date as month_start
    from employees e
    cross join lateral generate_series(
        0,
        (extract(year  from age(e.last_month, e.first_month)) * 12
       + extract(month from age(e.last_month, e.first_month)))::int
    ) as n
),

flagged as (
    select
        *,
        (month_start + interval '1 month - 1 day')::date                   as month_end,
        date_trunc('month', hire_date)::date = month_start                 as is_hire_month,
        coalesce(date_trunc('month', termination_date)::date = month_start, false) as is_termination_month
    from employee_months
)

select
    to_char(f.month_end, 'YYYYMMDD')::int          as month_end_date_key,
    emp.employee_key,
    dep.department_key,
    pos.position_key,
    mgr.manager_key,
    f.is_hire_month,
    f.is_termination_month,
    -- still there on the last day of the month? (leaving on the 31st = gone at month end)
    (f.termination_date is null or f.termination_date > f.month_end) as is_active_at_month_end
from flagged f
join {{ ref('dim_employee') }}   emp on emp.emp_id          = f.emp_id
join {{ ref('dim_department') }} dep on dep.department_name = f.department_name
join {{ ref('dim_position') }}   pos on pos.position_title  = f.position_title
join {{ ref('dim_manager') }}    mgr on mgr.manager_name    = f.manager_name
