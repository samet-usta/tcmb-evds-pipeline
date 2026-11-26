"""Daily EVDS pipeline: ingest, land, load, dbt, soda."""
from datetime import date, timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG, task

GROUPS = [
    "fx_rates",
    "deposit_rates",
    "loan_rates",
    "loan_volumes",
    "deposit_volumes",
    "policy_rate",
    "funding_cost",
]

# Grup başına geriye bakma süresi (gün). Frekansa göre seçildi.
GROUP_LOOKBACK_DAYS = {
    "fx_rates": 14,
    "funding_cost": 14,
    "deposit_rates": 35,
    "loan_rates": 35,
    "loan_volumes": 56,
    "deposit_volumes": 56,
    "policy_rate": 90,
}
# Container içinde dbt çalıştırma komutu (prod target)
DBT = "cd /opt/pipeline/dbt && DBT_TARGET=prod /opt/dbt-venv/bin/dbt"

# Ortak ayarlar. Task bazında override edilir.
default_args = {
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "execution_timeout": timedelta(minutes=10),
}

@task
def select_groups(**context):
    """Return groups that have data on the run date (available_from <= ds)."""
    from src.ingestion.series_config import get_group_config

    run_date = date.fromisoformat(context["ds"])
    selected_groups = []

    for group_name in GROUPS:
        group_config = get_group_config(group_name)
        available_from = date.fromisoformat(group_config["available_from"])
        if available_from <= run_date:
            selected_groups.append(group_name)

    return selected_groups

@task.short_circuit
def check_business_day(**context):
    """Return False on weekends and public holidays. Downstream tasks skip."""
    from src.ingestion.business_calendar import is_business_day

    run_date = date.fromisoformat(context["ds"])
    return is_business_day(run_date)

@task(
    retries=3,
    retry_delay=timedelta(minutes=5),
    retry_exponential_backoff=True,
    max_retry_delay=timedelta(minutes=30),
    execution_timeout=timedelta(minutes=15),
)

def ingest_land(group_name, **context):
    """Fetch one group and write it to S3 landing."""
    from src.ingestion.ingest import fetch_with_fallback
    from src.ingestion.series_config import get_group_config
    from src.landing.s3_writer import write_landing

    dt = context["ds"]
    end_date = date.fromisoformat(dt)
    lookback_days = GROUP_LOOKBACK_DAYS[group_name]
    group_config = get_group_config(group_name)
    available_from = date.fromisoformat(group_config["available_from"])

    # Veri olmayan tarihi isteme: pencere başı available_from'dan önce olamaz.
    start_date = max(available_from, end_date - timedelta(days=lookback_days))

    envelope = fetch_with_fallback(group_name, start_date, end_date)
    write_landing(envelope, end_date)


@task
def load(group_name, **context):
    """Load one group from S3 landing into raw.evds_landing."""
    from src.load.postgres_loader import load_landing

    load_landing(group_name, date.fromisoformat(context["ds"]))


with DAG (
    dag_id="evds_daily",
    schedule="0 17 * * 1-5",
    start_date=pendulum.datetime(2026,11,1,tz="Europe/Istanbul"),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    dagrun_timeout=timedelta(hours=2),
    is_paused_upon_creation=True,
    tags=["evds"],
) as dag:
    business_day_check = check_business_day()
    selected_groups = select_groups()
    business_day_check >> selected_groups
    ingest = ingest_land.expand(group_name=selected_groups)
    load_raw = load.expand(group_name=selected_groups)

    dbt_freshness = BashOperator(
        task_id="dbt_source_freshness",
        bash_command=f"{DBT} source freshness",
        retries=0,
    )

    soda_contract = BashOperator(
        task_id="soda_contract",
        bash_command="cd /opt/pipeline && bash soda/run_contract.sh ",
        retries=0,
    )

    dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command=f"{DBT} seed",
        retries=1,
        execution_timeout=timedelta(minutes=20),
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=DBT + """ run --vars '{"as_of_date": "{{ ds }}"}'""",
        retries=1,
        execution_timeout=timedelta(minutes=20),
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"{DBT} test",
        retries=0,
    )

    ingest >> load_raw >> dbt_freshness >> soda_contract >> dbt_seed >> dbt_run >> dbt_test

