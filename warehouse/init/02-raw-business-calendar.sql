-- Business calendar for the Soda gap rule (P4-A6-S6).
-- Filled by src/load/calendar_loader.py from business_calendar.py.
CREATE TABLE IF NOT EXISTS raw.business_calendar (
    dt              date    NOT NULL,
    is_business_day boolean NOT NULL,
    CONSTRAINT pk_business_calendar PRIMARY KEY (dt)
);
