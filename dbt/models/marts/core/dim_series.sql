with series_metadata as (

    select
        series_code,
        series_name,
        group_name,
        frequency,
        unit,
        measure_type,
        max_fill_days,
        available_from,
        fallback_source
    from {{ ref('series_metadata') }}

),

final as (

    select
        series_code,
        series_name,
        group_name,
        frequency,
        unit,
        measure_type,
        max_fill_days,
        available_from,
        (fallback_source is not null) as has_fallback,
        fallback_source
    from series_metadata

)

select * from final
