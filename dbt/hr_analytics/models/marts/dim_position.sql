-- One row per job title.
select
    row_number() over (order by position_title)::int as position_key,
    position_title
from (select distinct position_title from {{ ref('stg_hr_employees') }}) p
