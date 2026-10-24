-- One row per employee: who they are (descriptive attributes only, no measures).
select
    row_number() over (order by e.emp_id)::int as employee_key,
    e.emp_id,
    e.first_name,
    e.last_name,
    e.full_name,
    e.gender,
    e.birth_date,
    e.marital_status,
    e.citizenship,
    e.is_hispanic_latino,
    e.race,
    e.state_code,
    s.state_name,
    s.census_region,
    e.zip
from {{ ref('stg_hr_employees') }} e
left join {{ ref('us_states') }} s using (state_code)
