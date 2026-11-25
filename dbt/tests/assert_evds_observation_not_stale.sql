{{ config(severity='warn') }}

-- Her grubun son gözlem tarihi, frequency eşiğinden eski olmamalı.
-- Eşikler: business_daily 7 gün, weekly_friday 14 gün, monthly 75 gün.
with last_obs as (
    select
        s.group_name,
        m.frequency,
        max(s.observation_date) as last_observation
    from {{ ref('stg_evds__observations') }} as s
    inner join {{ ref('series_metadata') }} as m
        on s.series_code = m.series_code
    where s.value is not null
    group by 1, 2
),

aged as (
    select
        group_name,
        frequency,
        last_observation,
        current_date - last_observation::date as age_days,
        case frequency
            when 'business_daily' then 7
            when 'weekly_friday' then 14
            when 'monthly' then 75
        end as max_age_days
    from last_obs
)

select *
from aged
where age_days > max_age_days
   or max_age_days is null
