-- One row per (series_code, observation_date). The latest file wins.
-- One Frankfurter rate maps to two EVDS series (buying A and selling S) with the same value.

with rates as (

    select * from {{ ref('stg_frankfurter__fx_rates') }}

),

fallback_series as (

    select
        series_code,
        fallback_base_currency,
        fallback_quote_currency
    from {{ ref('series_metadata') }}
    where fallback_source = 'frankfurter'

),

ranked as (

    select
        *,
        row_number() over (
            partition by base_currency, quote_currency, observation_date
            order by ingested_at desc, dt desc
        ) as row_num
    from rates

),

deduped as (

    select * from ranked
    where row_num = 1

),

final as (

    select
        fallback_series.series_code,
        deduped.observation_date,
        deduped.value,
        deduped.source,
        deduped.group_name,
        deduped.dt,
        deduped.ingested_at
    from deduped
    inner join fallback_series
        on deduped.base_currency = fallback_series.fallback_base_currency
        and deduped.quote_currency = fallback_series.fallback_quote_currency

)

select * from final
