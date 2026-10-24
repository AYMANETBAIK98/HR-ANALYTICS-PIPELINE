-- One row per recruitment source, enriched with its channel from the reference file (seed).
select
    row_number() over (order by s.recruitment_source)::int as recruitment_source_key,
    s.recruitment_source,
    coalesce(c.recruitment_channel, 'Other')              as recruitment_channel
from (select distinct recruitment_source from {{ ref('stg_hr_employees') }}) s
left join {{ ref('recruitment_source_channels') }} c using (recruitment_source)
