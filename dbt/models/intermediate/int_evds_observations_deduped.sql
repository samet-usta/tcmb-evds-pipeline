-- One row per (series_code, observation_date). The latest file wins.
-- Null values stay here: int_observations_unioned needs them for source priority.

with observations as (

    select * from {{ ref('stg_evds__observations') }}

),

ranked as (

    select
        *,
        row_number() over (
            partition by series_code, observation_date
            order by ingested_at desc, dt desc
        ) as row_num
    from observations

),

final as (

    select
        series_code,
        observation_date,
        value,
        source,
        group_name,
        dt,
        ingested_at
    from ranked
    where row_num = 1

)

select * from final
