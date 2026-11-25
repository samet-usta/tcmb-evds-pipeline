-- weekly_friday serilerde gözlem tarihi Cuma olmalı (isodow: Pazartesi=1, Cuma=5).
select
    f.series_code,
    f.observation_date,
    extract(isodow from f.observation_date) as day_of_week
from {{ ref('fct_rates') }} as f
inner join {{ ref('dim_series') }} as d
    on f.series_code = d.series_code
where d.frequency = 'weekly_friday'
  and extract(isodow from f.observation_date) <> 5
