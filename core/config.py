import os
import yaml
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class AppConfig:
    raw: Dict[str, Any]

def load_config(path: str = "config/config.yaml") -> AppConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return AppConfig(raw=raw)

def apply_config_to_env(cfg: AppConfig) -> None:
    raw = cfg.raw
    gcp = raw.get("gcp", {})
    bq = raw.get("bigquery", {})
    llm = raw.get("llm", {})
    tables = (bq.get("tables") or {})

    project_id = gcp.get("project_id", "")
    location = gcp.get("location", "us-central1")
    dataset = bq.get("dataset", "")

    if project_id:
        os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
    os.environ["GOOGLE_CLOUD_LOCATION"] = location

    # Build project.dataset
    if project_id and dataset:
        os.environ["BQ_DEFAULT_DATASET"] = f"{project_id}.{dataset}"
    elif dataset and "BQ_DEFAULT_DATASET" not in os.environ:
        # allow user to set full project.dataset via env as fallback
        os.environ["BQ_DEFAULT_DATASET"] = dataset

    # Table env vars used in semantic YAML
    os.environ["BQ_CUSTOMERS_TABLE"] = tables.get("customers", "customers_min")
    os.environ["BQ_PRODUCTS_TABLE"] = tables.get("products", "products_min")
    os.environ["BQ_ORDERS_TABLE"] = tables.get("orders", "orders_min")

    # LLM model
    if llm.get("model"):
        os.environ["GEMINI_MODEL"] = llm["model"]
