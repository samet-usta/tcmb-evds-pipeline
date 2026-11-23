{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key=['series_code', 'observation_date'],
        on_schema_change='fail'
    )
}}

with observations as (

    select
        series_code,
        observation_date,
        value,
        source,
        dt,
        ingested_at
    from {{ ref('int_observations_unioned') }}

    {% if is_incremental() %}
    -- Revizyon ve geç veri yeni ingested_at ile gelir; lookback bu veriyi yakalar
    -- coalesce: tablo boşsa max null olur ve hiç satır gelmez
    where ingested_at >= (
        select {{ dbt.dateadd('day', -1 * var('incremental_lookback_days', 3), "coalesce(max(ingested_at), cast('1900-01-01' as timestamp))") }}
        from {{ this }}
    )
    {% endif %}

),

rate_series as (

    select series_code
    from {{ ref('dim_series') }}
    where measure_type = 'rate'

),

final as (

    select
        observations.series_code,
        observations.observation_date,
        observations.value,
        observations.source,
        observations.dt,
        observations.ingested_at,
        {{ dbt.current_timestamp() }} as dbt_updated_at
    from observations
    inner join rate_series
        on observations.series_code = rate_series.series_code

)

select * from final
