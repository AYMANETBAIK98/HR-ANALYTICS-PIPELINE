-- R07, R09, R10 - business rule: a terminated employee has a termination date, a reason
-- and a type; an active employee has none of them. And nobody leaves before being hired.
select emp_id, is_terminated, termination_date, term_reason, termination_type
from {{ ref('stg_hr_employees') }}
where is_terminated <> (termination_date is not null)
   or is_terminated <> (term_reason is not null)
   or is_terminated <> (termination_type is not null)
   or termination_date < hire_date
