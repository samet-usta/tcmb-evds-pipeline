{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key=['series_code', 'date_day'],
        on_schema_change='fail'
    )
}}

{#- Airflow passes as_of_date via --vars. Default is for manual runs only. -#}
{%- set as_of_date_var = var('as_of_date', none) -%}
{%- if as_of_date_var is none -%}
    {%- set as_of_date = 'current_date' -%}
{%- else -%}
    {%- set as_of_date = "cast('" ~ as_of_date_var ~ "' as date)" -%}
{%- endif -%}

with

{% if is_incremental() %}

target_state as (
    select
        max(date_day) as max_date_day,
        max(dbt_updated_at) as max_updated_at
    from {{ this }}
),

changed_observations as (
    select
        min(fct_rates.observation_date) as min_changed_date
    from {{ ref('fct_rates') }} as fct_rates
    cross join target_state
    where fct_rates.dbt_updated_at > target_state.max_updated_at
),

window_bounds as (
    -- Recalculate from the earliest changed observation or from the last loaded day.
    select
        case
            when target_state.max_date_day is null then cast('1900-01-01' as date)
            when changed_observations.min_changed_date < target_state.max_date_day
                then changed_observations.min_changed_date
            else target_state.max_date_day
        end as window_start
    from target_state
    cross join changed_observations
),

{% else %}

window_bounds as (
    select cast('1900-01-01' as date) as window_start
),

{% endif %}

series_bounds as (
    -- anchor_date: last observation before the window. Fill starts from it.
    select
        fct_rates.series_code,
        min(fct_rates.observation_date) as first_observation_date,
        max(
            case
                when fct_rates.observation_date < window_bounds.window_start
                    then fct_rates.observation_date
            end
        ) as anchor_date
    from {{ ref('fct_rates') }} as fct_rates
    cross join window_bounds
    group by fct_rates.series_code
),

grid as (
    select
        series_bounds.series_code,
        dim_date.date_day
    from series_bounds
    inner join {{ ref('dim_date') }} as dim_date
        on dim_date.date_day >= coalesce(series_bounds.anchor_date, series_bounds.first_observation_date)
        and dim_date.date_day <= {{ as_of_date }}
),

observations_on_grid as (
    select
        grid.series_code,
        grid.date_day,
        fct_rates.observation_date,
        fct_rates.value,
        fct_rates.source
    from grid
    left join {{ ref('fct_rates') }} as fct_rates
        on fct_rates.series_code = grid.series_code
        and fct_rates.observation_date = grid.date_day
),

grouped as (
    -- Each observation starts a new group. Days without observation stay in the previous group.
    select
        series_code,
        date_day,
        observation_date,
        value,
        source,
        count(observation_date) over (
            partition by series_code
            order by date_day
            rows between unbounded preceding and current row
        ) as fill_group
    from observations_on_grid
),

last_observation as (
    select
        series_code,
        date_day,
        value,
        max(observation_date) over (partition by series_code, fill_group) as last_observation_date,
        max(value) over (partition by series_code, fill_group) as last_value,
        max(source) over (partition by series_code, fill_group) as last_source
    from grouped
),

with_limit as (
    select
        last_observation.series_code,
        last_observation.date_day,
        last_observation.value,
        last_observation.last_observation_date,
        last_observation.last_value,
        last_observation.last_source,
        case
            when {{ dbt.datediff('last_observation.last_observation_date', 'last_observation.date_day', 'day') }}
                <= dim_series.max_fill_days
                then true
            else false
        end as is_within_limit
    from last_observation
    inner join {{ ref('dim_series') }} as dim_series
        on dim_series.series_code = last_observation.series_code
),

final as (
    select
        with_limit.series_code,
        with_limit.date_day,
        with_limit.value,
        case when with_limit.is_within_limit then with_limit.last_value end as value_filled,
        case
            when with_limit.value is null and with_limit.is_within_limit then true
            else false
        end as is_filled,
        case when with_limit.is_within_limit then with_limit.last_observation_date end as filled_from_date,
        case when with_limit.is_within_limit then with_limit.last_source end as source,
        {{ dbt.current_timestamp() }} as dbt_updated_at
    from with_limit
    cross join window_bounds
    where with_limit.date_day >= window_bounds.window_start
)

select * from final
