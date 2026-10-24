-- Calendar: one row per day from 2006-01-01 to 2019-12-31 (covers every hire, termination and
-- review date). Generated, not read from the source. Power BI needs it for time intelligence.
--
-- We count DAYS (integers) instead of stepping a timestamp by "1 day": a timestamp series follows
-- the session time zone, and daylight-saving changes (e.g. Africa/Casablanca) can drop a day.
with days as (
    select ('2006-01-01'::date + n) as d
    from generate_series(0, '2019-12-31'::date - '2006-01-01'::date) as n
)
select
    to_char(d, 'YYYYMMDD')::int                       as date_key,
    d                                                 as full_date,
    extract(year    from d)::int                      as year,
    extract(quarter from d)::int                      as quarter,
    extract(month   from d)::int                      as month,
    trim(to_char(d, 'Month'))                         as month_name,
    to_char(d, 'Mon')                                 as month_short,
    to_char(d, 'YYYY-MM')                             as year_month,
    extract(isodow  from d)::int                      as day_of_week,     -- 1 = Monday
    trim(to_char(d, 'Day'))                           as day_name,
    d = (date_trunc('month', d) + interval '1 month - 1 day')::date as is_month_end
from days
