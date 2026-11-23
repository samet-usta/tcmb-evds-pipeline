{% set end_date_expr = dbt.dateadd('day', 1, dbt.dateadd('year', 1, 'current_date')) %}

with date_spine as (

    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('1950-01-01' as date)",
        end_date="cast(" ~ end_date_expr ~ " as date)"
    ) }}

),

date_parts as (

    select
        cast(date_day as date) as date_day,
        cast(extract(year from date_day) as integer) as year,
        cast(extract(quarter from date_day) as integer) as quarter,
        cast(extract(month from date_day) as integer) as month,
        cast(extract(week from date_day) as integer) as week_of_year,
        cast(extract(isodow from date_day) as integer) as day_of_week
    from date_spine

),

date_names as (

    select
        date_day,
        year,
        quarter,
        month,
        case month
            when 1 then 'January'
            when 2 then 'February'
            when 3 then 'March'
            when 4 then 'April'
            when 5 then 'May'
            when 6 then 'June'
            when 7 then 'July'
            when 8 then 'August'
            when 9 then 'September'
            when 10 then 'October'
            when 11 then 'November'
            when 12 then 'December'
        end as month_name,
        week_of_year,
        day_of_week,
        case day_of_week
            when 1 then 'Monday'
            when 2 then 'Tuesday'
            when 3 then 'Wednesday'
            when 4 then 'Thursday'
            when 5 then 'Friday'
            when 6 then 'Saturday'
            when 7 then 'Sunday'
        end as day_name,
        day_of_week in (6, 7) as is_weekend
    from date_parts

),

tr_holidays as (

    select
        holiday_date,
        holiday_name
    from {{ ref('tr_holidays') }}

),

final as (

    select
        date_names.date_day,
        date_names.year,
        date_names.quarter,
        date_names.month,
        date_names.month_name,
        date_names.week_of_year,
        date_names.day_of_week,
        date_names.day_name,
        date_names.is_weekend,
        (tr_holidays.holiday_date is not null) as is_holiday,
        tr_holidays.holiday_name,
        (not date_names.is_weekend and tr_holidays.holiday_date is null) as is_business_day
    from date_names
    left join tr_holidays
        on date_names.date_day = tr_holidays.holiday_date

)

select * from final
