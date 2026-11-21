-- Raw landing table. One row = one S3 file (group_name, dt).
-- Other tables are created by dbt.
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.evds_landing (
    group_name      text        NOT NULL,
    dt              date        NOT NULL,
    source          text        NOT NULL,
    ingested_at     timestamptz NOT NULL,
    fallback_reason text,
    s3_key          text        NOT NULL,
    request_params  jsonb       NOT NULL,
    items           jsonb       NOT NULL,
    loaded_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_evds_landing PRIMARY KEY (group_name, dt)
);
