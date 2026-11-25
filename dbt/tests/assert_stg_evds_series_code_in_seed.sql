-- Staging'deki her series_code, series_metadata seed'inde olmalı.
-- Seed'de olmayan kod = config/series.yaml ile veri uyumsuz.
select distinct s.series_code
from {{ ref('stg_evds__observations') }} as s
left join {{ ref('series_metadata') }} as m
    on s.series_code = m.series_code
where m.series_code is null
