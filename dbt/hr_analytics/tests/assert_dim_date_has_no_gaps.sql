-- The calendar must start on 2006-01-01, end on 2019-12-31 and contain every day in between.
-- (This test caught a real bug: a time-zone change once dropped 2019-12-31.)
select min(full_date) as first_day, max(full_date) as last_day, count(*) as days
from {{ ref('dim_date') }}
having min(full_date) <> '2006-01-01'
    or max(full_date) <> '2019-12-31'
    or count(*) <> max(full_date) - min(full_date) + 1
