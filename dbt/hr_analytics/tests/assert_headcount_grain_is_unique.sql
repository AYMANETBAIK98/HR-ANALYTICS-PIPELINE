-- Grain check: one employee appears at most once per month.
select month_end_date_key, employee_key, count(*)
from {{ ref('fact_headcount_monthly') }}
group by 1, 2
having count(*) > 1
