-- R01, R12: no leading/trailing or double spaces left, and every zip code has 5 digits.
select emp_id
from {{ ref('stg_hr_employees') }}
where full_name       <> trim(regexp_replace(full_name, '\s+', ' ', 'g'))
   or department_name <> trim(department_name)
   or position_title  <> trim(position_title)
   or zip !~ '^\d{5}$'
