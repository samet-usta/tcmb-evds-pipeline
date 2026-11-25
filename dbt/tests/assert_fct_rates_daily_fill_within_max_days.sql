-- Doldurulan günün kaynak tarihten uzaklığı max_fill_days değerini aşmamalı.
select
    f.series_code,
    f.date_day,
    f.filled_from_date,
    f.date_day::date - f.filled_from_date::date as fill_gap_days,
    d.max_fill_days
from {{ ref('fct_rates_daily') }} as f
inner join {{ ref('dim_series') }} as d
    on f.series_code = d.series_code
where f.is_filled
  and f.date_day::date - f.filled_from_date::date > d.max_fill_days
