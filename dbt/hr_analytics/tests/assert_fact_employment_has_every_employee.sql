-- No employee lost in the joins: fact_employment has exactly as many rows as staging.
select (select count(*) from {{ ref('fact_employment') }}) as fact_rows,
       (select count(*) from {{ ref('stg_hr_employees') }}) as staging_rows
where (select count(*) from {{ ref('fact_employment') }})
   <> (select count(*) from {{ ref('stg_hr_employees') }})
