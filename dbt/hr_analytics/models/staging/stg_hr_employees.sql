{#
  STAGING: one clean, typed row per employee.
  Applies the cleaning rules R01-R13 from docs/cleaning_rules.md (rule numbers in comments).
  No business logic here (no joins, no keys): just making the source trustworthy.
#}

with

-- Each HR export is a FULL snapshot of the company, so we only read the most recent one.
latest_export as (
    select *
    from {{ source('raw', 'hr_employees') }}
    where _loaded_at = (select max(_loaded_at) from {{ source('raw', 'hr_employees') }})
),

cleaned as (
    select
        -- identity ------------------------------------------------------------
        trim(empid)::int                                              as emp_id,            -- R13
        -- R01 + R04: collapse inner spaces, then split "Last, First M"
        trim(split_part(regexp_replace(trim(employee_name), '\s+', ' ', 'g'), ',', 2)) as first_name,
        trim(split_part(regexp_replace(trim(employee_name), '\s+', ' ', 'g'), ',', 1)) as last_name,

        -- personal ------------------------------------------------------------
        case trim(sex) when 'F' then 'Female' when 'M' then 'Male' end as gender,           -- R02
        -- R06: 'MM/DD/YY' -> force the 19xx century (2-digit years 00-68 would become 20xx)
        to_date(left(trim(dob), 6) || '19' || right(trim(dob), 2), 'MM/DD/YYYY') as birth_date,
        trim(maritaldesc)                                             as marital_status,
        trim(citizendesc)                                             as citizenship,
        lower(trim(hispaniclatino)) = 'yes'                           as is_hispanic_latino, -- R03
        trim(racedesc)                                                as race,
        trim(state)                                                   as state_code,
        lpad(trim(zip), 5, '0')                                       as zip,               -- R12

        -- job (labels only: the numeric codes are unreliable and dropped) ------
        trim(department)                                              as department_name,   -- R01
        trim(position)                                                as position_title,
        trim(managername)                                             as manager_name,      -- R11
        trim(salary)::numeric(12, 2)                                  as salary,

        -- employment lifecycle ------------------------------------------------
        to_date(trim(dateofhire), 'MM/DD/YYYY')                       as hire_date,         -- R05
        to_date(trim(dateoftermination), 'MM/DD/YYYY')                as termination_date,  -- R05, R09
        nullif(trim(termreason), 'N/A-StillEmployed')                 as term_reason,       -- R07
        trim(termd) = '1'                                             as is_terminated,     -- R10
        trim(employmentstatus)                                        as employment_status,
        case trim(employmentstatus)
            when 'Voluntarily Terminated' then 'Voluntary'
            when 'Terminated for Cause'   then 'Involuntary'
        end                                                           as termination_type,  -- R10

        -- recruitment ---------------------------------------------------------
        trim(recruitmentsource)                                       as recruitment_source,

        -- performance & engagement --------------------------------------------
        trim(performancescore)                                        as performance_score,
        case trim(performancescore)
            when 'Exceeds'           then 4
            when 'Fully Meets'       then 3
            when 'Needs Improvement' then 2
            when 'PIP'               then 1
        end                                                           as performance_rank,
        trim(engagementsurvey)::numeric(3, 2)                         as engagement_score,
        trim(empsatisfaction)::int                                    as satisfaction_score,
        trim(specialprojectscount)::int                               as special_projects_count,
        to_date(trim(lastperformancereview_date), 'MM/DD/YYYY')       as last_review_date,  -- R05
        trim(dayslatelast30)::int                                     as days_late_last_30,
        trim(absences)::int                                           as absences,

        -- lineage -------------------------------------------------------------
        _source_file,
        _loaded_at
    from latest_export
)

select
    *,
    first_name || ' ' || last_name                                    as full_name          -- R04
from cleaned
