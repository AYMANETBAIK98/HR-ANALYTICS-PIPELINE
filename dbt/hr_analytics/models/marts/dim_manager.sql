-- One row per manager, identified by name (rule R11: the source ManagerID is unreliable).
select
    row_number() over (order by manager_name)::int as manager_key,
    manager_name
from (select distinct manager_name from {{ ref('stg_hr_employees') }}) m
