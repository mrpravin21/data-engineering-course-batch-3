from datetime import datetime
from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="my_first_working_dag",
    start_date=datetime(2026, 8, 25),
    schedule=None,
    catchup=False,
) as dag:

    hello_task = BashOperator(
        task_id="say_hello",
        bash_command="echo 'Hello from my local Airflow cluster!'"
    )
