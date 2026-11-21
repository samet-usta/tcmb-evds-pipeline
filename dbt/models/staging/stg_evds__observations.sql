-- Grain: 1 row = (group_name, dt, observation_date, series_code)
-- No dedup here. Overlapping windows are deduplicated in intermediate.

with landing as (
    select
        group_name,
        dt,
        source,
        ingested_at,
        items
    from {{ source('raw', 'evds_landing') }}
    where source = 'evds'
),

days as (
    select
        landing.group_name,
        landing.dt,
        landing.source,
        landing.ingested_at,
        day_item.item
    from landing
    cross join lateral jsonb_array_elements(landing.items) as day_item(item)
),

observations as (
    select
        days.group_name,
        days.dt,
        days.source,
        days.ingested_at,
        days.item ->> 'Tarih' as observation_date_raw,
        series_value.key as series_column,
        series_value.value as value_raw
    from days
    cross join lateral jsonb_each_text(days.item) as series_value(key, value)
    -- Item attributes, not series. YEARWEEK: weekly groups only
    where series_value.key not in ('Tarih', 'UNIXTIME', 'YEARWEEK')
),

final as (
    select
        group_name,
        dt,
        source,
        ingested_at,
        case
            -- Daily and weekly: dd-mm-yyyy
            when observation_date_raw ~ '^[0-9]{2}-[0-9]{2}-[0-9]{4}$'
                then to_date(observation_date_raw, 'DD-MM-YYYY')
            -- Monthly: yyyy-m -> first day of month
            when observation_date_raw ~ '^[0-9]{4}-[0-9]{1,2}$'
                then to_date(observation_date_raw || '-1', 'YYYY-MM-DD')
        end as observation_date,
        -- EVDS response column: TP_DK_USD_A_YTL -> TP.DK.USD.A.YTL
        replace(series_column, '_', '.') as series_code,
        cast(value_raw as numeric) as value
    from observations
)

select * from final
