-- value_filled null ise gün için değer yok demektir.
-- Bu satırda filled_from_date ve source de null olmalı.
select
    series_code,
    date_day,
    value_filled,
    filled_from_date,
    source
from {{ ref('fct_rates_daily') }}
where value_filled is null
  and (filled_from_date is not null or source is not null)
