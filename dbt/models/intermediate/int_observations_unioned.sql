-- One row per (series_code, observation_date) from all sources.
-- Priority: EVDS. Frankfurter is used only when EVDS has no row for that day.
-- An EVDS row with a null value blocks Frankfurter, then the null filter removes it.

with evds as (

    select * from {{ ref('int_evds_observations_deduped') }}

),

frankfurter as (

    select * from {{ ref('int_frankfurter_fx_rates_mapped') }}

),

series as (

    select
        series_code,
        frequency
    from {{ ref('series_metadata') }}

),

frankfurter_only as (

    select frankfurter.*
    from frankfurter
    left join evds
        on frankfurter.series_code = evds.series_code
        and frankfurter.observation_date = evds.observation_date
    where evds.series_code is null

),

unioned as (

    select
        series_code,
        observation_date,
        value,
        source,
        group_name,
        dt,
        ingested_at
    from evds

    union all

    select
        series_code,
        observation_date,
        value,
        source,
        group_name,
        dt,
        ingested_at
    from frankfurter_only

),

final as (

    select
        unioned.series_code,
        series.frequency,
        unioned.observation_date,
        unioned.value,
        unioned.source,
        unioned.group_name,
        unioned.dt,
        unioned.ingested_at
    from unioned
    left join series
        on unioned.series_code = series.series_code
    where unioned.value is not null

)

select * from final
