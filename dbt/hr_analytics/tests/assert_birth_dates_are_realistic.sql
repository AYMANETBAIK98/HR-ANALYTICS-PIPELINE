-- R06: after fixing the century, nobody is born after being hired,
-- and everybody is hired between 16 and 75 years old.
-- A dbt "singular test" passes when the query returns ZERO rows.
select emp_id, birth_date, hire_date
from {{ ref('stg_hr_employees') }}
where birth_date >= hire_date
   or extract(year from age(hire_date, birth_date)) not between 16 and 75
