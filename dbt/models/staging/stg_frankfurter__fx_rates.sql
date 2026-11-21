-- Grain: 1 row = (group_name, dt, observation_date, base_currency, quote_currency)
-- No dedup here. Mapping to EVDS series codes is in intermediate.

with landing as (
    select
        group_name,
        dt,
        source,
        ingested_at,
        items
    from {{ source('raw', 'evds_landing') }}
    where source = 'frankfurter'
),

rates as (
    select
        landing.group_name,
        landing.dt,
        landing.source,
        landing.ingested_at,
        rate_item.item
    from landing
    cross join lateral jsonb_array_elements(landing.items) as rate_item(item)
),

final as (
    select
        group_name,
        dt,
        source,
        ingested_at,
        cast(item ->> 'date' as date) as observation_date,
        item ->> 'base' as base_currency,
        item ->> 'quote' as quote_currency,
        cast(item ->> 'rate' as numeric) as value
    from rates
)

select * from final
