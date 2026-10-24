-- Reconciliation: the monthly table must tell the same story as the source.
--   every employee has exactly 1 hire month, every leaver exactly 1 termination month,
--   and the headcount on the as-of date equals the number of active employees.
with per_employee as (
    select employee_key,
           count(*) filter (where is_hire_month)        as hire_months,
           count(*) filter (where is_termination_month) as termination_months
    from {{ ref('fact_headcount_monthly') }}
    group by 1
)
select 'hire month count' as check_name, employee_key::text as detail
from per_employee where hire_months <> 1
union all
select 'termination month count', p.employee_key::text
from per_employee p join {{ ref('fact_employment') }} f using (employee_key)
where p.termination_months <> case when f.is_terminated then 1 else 0 end
union all
select 'headcount on as-of date', count(*)::text
from {{ ref('fact_headcount_monthly') }}
where month_end_date_key = to_char('{{ var("as_of_date") }}'::date, 'YYYYMMDD')::int
  and is_active_at_month_end
having count(*) <> (select count(*) from {{ ref('stg_hr_employees') }} where not is_terminated)
