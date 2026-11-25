-- is_filled = true ise value null ve value_filled dolu olmalı.
-- is_filled = false ise bu durum olmamalı.
select
    series_code,
    date_day,
    value,
    value_filled,
    is_filled
from {{ ref('fct_rates_daily') }}
where is_filled is distinct from (value is null and value_filled is not null)
