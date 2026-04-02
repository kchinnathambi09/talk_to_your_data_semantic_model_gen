from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
from google.cloud import bigquery


def _client(project_id: str | None = None) -> bigquery.Client:
    return bigquery.Client(project=project_id) if project_id else bigquery.Client()


def run_query(sql: str, project_id: str | None = None) -> pd.DataFrame:
    client = _client(project_id)
    job = client.query(sql)
    return job.result().to_dataframe()


def list_datasets(project_id: str | None = None) -> List[str]:
    client = _client(project_id)
    datasets = sorted({ds.dataset_id for ds in client.list_datasets()})
    return datasets


def list_tables(dataset_id: str, project_id: str | None = None) -> List[str]:
    client = _client(project_id)

    # Allow dataset_id to be passed as either "dataset" or "project.dataset"
    dataset_ref = dataset_id
    if "." in dataset_id:
        parts = dataset_id.split(".")
        dataset_ref = parts[-1]

    tables = []
    for tbl in client.list_tables(dataset_ref):
        if tbl.table_type in {"TABLE", "VIEW", "EXTERNAL"}:
            tables.append(tbl.table_id)
    return sorted(tables)


def get_table_schema(dataset_id: str, table_id: str, project_id: str | None = None) -> List[Dict[str, Any]]:
    client = _client(project_id)

    # Normalize dataset_id if passed as "project.dataset"
    dataset_ref = dataset_id
    if "." in dataset_id:
        parts = dataset_id.split(".")
        dataset_ref = parts[-1]

    # Allow either plain table_id or fully qualified table ref
    if table_id.count(".") >= 2:
        table_ref = table_id
    else:
        table_ref = f"{client.project}.{dataset_ref}.{table_id}"

    table = client.get_table(table_ref)

    return [
        {
            "name": field.name,
            "type": field.field_type,
            "mode": field.mode,
            "description": field.description or "",
        }
        for field in table.schema
    ]