# base: runtime image. dev: base + test tools.
FROM apache/airflow:3.1.8-python3.12 AS base

# Constraints keep Airflow dependency versions compatible.
ARG CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-3.1.8/constraints-3.12.txt"

COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir \
    "apache-airflow==${AIRFLOW_VERSION}" \
    -r /requirements.txt \
    --constraint "${CONSTRAINT_URL}"

FROM base AS dev

COPY requirements-dev.txt /requirements-dev.txt
RUN pip install --no-cache-dir \
    "apache-airflow==${AIRFLOW_VERSION}" \
    -r /requirements-dev.txt \
    --constraint "${CONSTRAINT_URL}"
