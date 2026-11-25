-- fct_rates_daily takvim günü bazında. Her seride ardışık günler arasında boşluk olmamalı.
with gaps as (
    select
        series_code,
        date_day,
        date_day::date - lag(date_day::date) over (
            partition by series_code
            order by date_day
        ) as gap_days
    from {{ ref('fct_rates_daily') }}
)

select
    series_code,
    date_day,
    gap_days
from gaps
where gap_days > 1
