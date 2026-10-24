-- One row per termination reason (from the reference file, so every known reason exists
-- even if nobody left for it yet) + a "Not applicable" member with key -1 for active employees.
select
    row_number() over (order by term_reason_category, term_reason)::int as term_reason_key,
    term_reason,
    term_reason_category
from {{ ref('term_reason_categories') }}

union all

select -1, 'Not applicable', 'Not applicable (still employed)'
