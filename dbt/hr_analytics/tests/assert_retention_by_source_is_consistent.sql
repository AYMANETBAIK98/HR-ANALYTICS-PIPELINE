-- mart_retention_by_source must be consistent:
--   * one row per source and horizon
--   * retained <= eligible <= hires, and the rate is between 0 and 1
--   * no hire younger than the horizon is judged (eligible = hired at least N years before the as-of date)
-- Returns the rows that break a rule.
{% set as_of = "'" ~ var('as_of_date') ~ "'::date" %}

with expected_eligible as (
    select src.recruitment_source_key, hz.n as horizon_years, count(*) as eligible_hires
    from {{ ref('stg_hr_employees') }} e
    join {{ ref('dim_recruitment_source') }} src using (recruitment_source)
    cross join generate_series(1, 3) as hz(n)
    where e.hire_date <= {{ as_of }} - make_interval(years => hz.n)
    group by 1, 2
),

duplicates as (
    select recruitment_source_key, horizon_years
    from {{ ref('mart_retention_by_source') }}
    group by 1, 2
    having count(*) > 1
)

select 'duplicate grain' as problem, recruitment_source_key, horizon_years
from duplicates
union all
select 'counts out of order', recruitment_source_key, horizon_years
from {{ ref('mart_retention_by_source') }}
where not (retained_hires <= eligible_hires and eligible_hires <= hires)
   or retention_rate < 0 or retention_rate > 1
union all
select 'wrong eligible count', m.recruitment_source_key, m.horizon_years
from {{ ref('mart_retention_by_source') }} m
left join expected_eligible x using (recruitment_source_key, horizon_years)
where m.eligible_hires <> coalesce(x.eligible_hires, 0)
