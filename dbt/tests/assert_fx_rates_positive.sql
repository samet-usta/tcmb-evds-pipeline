-- Kur (fx_rates) sıfır veya negatif olamaz.
select
    f.series_code,
    f.date_day,
    f.value,
    f.value_filled
from {{ ref('fct_rates_daily') }} as f
inner join {{ ref('dim_series') }} as d
    on f.series_code = d.series_code
where d.group_name = 'fx_rates'
  and (f.value <= 0 or f.value_filled <= 0)
