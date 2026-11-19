{#
  Retention by recruitment source over a FIXED window: 1, 2 and 3 years after hire.
  One row per recruitment source x horizon.

  Why: "still employed today" favours sources that hired recently (their hires had less time to leave).
  Here every hire is judged on the same window:
    - eligible = hired at least N years before the as-of date (we can know the outcome)
    - retained = still employed N years after the hire date
  (Suggested in a LinkedIn comment on the project: thank you Diego.)
#}
{% set as_of = "'" ~ var('as_of_date') ~ "'::date" %}

with hires as (
    select
        src.recruitment_source_key,
        e.hire_date,
        e.termination_date
    from {{ ref('stg_hr_employees') }}        e
    join {{ ref('dim_recruitment_source') }}  src on src.recruitment_source = e.recruitment_source
),

horizons as (
    select generate_series(1, 3) as horizon_years
),

judged as (
    select
        h.recruitment_source_key,
        hz.horizon_years,
        h.hire_date + make_interval(years => hz.horizon_years) <= {{ as_of }}         as is_eligible,
        h.termination_date is null
            or h.termination_date >= h.hire_date + make_interval(years => hz.horizon_years)
                                                                                      as is_retained
    from hires h
    cross join horizons hz
)

select
    s.recruitment_source_key,
    s.recruitment_source,
    s.recruitment_channel,
    j.horizon_years,
    count(*)                                                       as hires,
    count(*) filter (where j.is_eligible)                          as eligible_hires,
    count(*) filter (where j.is_eligible and j.is_retained)        as retained_hires,
    round(
        count(*) filter (where j.is_eligible and j.is_retained)::numeric
        / nullif(count(*) filter (where j.is_eligible), 0), 4)     as retention_rate
from judged j
join {{ ref('dim_recruitment_source') }} s using (recruitment_source_key)
group by 1, 2, 3, 4
