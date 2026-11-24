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

volume_series as (

    select series_code
    from {{ ref('dim_series') }}
    where measure_type = 'volume'

),

{% if is_incremental() %}
-- Mevcut satırlar: dbt_updated_at değişmediyse korunur
existing as (

    select
        series_code,
        observation_date,
        value,
        source,
        dbt_updated_at
    from {{ this }}

),
{% endif %}

final as (

    select
        observations.series_code,
        observations.observation_date,
        observations.value,
        observations.source,
        observations.dt,
        observations.ingested_at,
        {% if is_incremental() %}
        -- value ve source int_observations_unioned içinde null olmaz; <> yeterli
        case
            when existing.series_code is null then {{ dbt.current_timestamp() }}
            when existing.value <> observations.value then {{ dbt.current_timestamp() }}
            when existing.source <> observations.source then {{ dbt.current_timestamp() }}
            else existing.dbt_updated_at
        end as dbt_updated_at
        {% else %}
        {{ dbt.current_timestamp() }} as dbt_updated_at
        {% endif %}
    from observations
    inner join volume_series
        on observations.series_code = volume_series.series_code
    {% if is_incremental() %}
    left join existing
        on observations.series_code = existing.series_code
        and observations.observation_date = existing.observation_date
    {% endif %}

)

select * from final
