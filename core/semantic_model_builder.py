from pathlib import Path
from typing import Any, Dict, List

import yaml


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_sql_model_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def list_local_sql_models(folder_path: str) -> List[str]:
    folder = Path(folder_path)
    if not folder.is_absolute():
        folder = _project_root() / folder

    if not folder.exists() or not folder.is_dir():
        return []

    return [
        str(p).replace("\\", "/")
        for p in sorted(folder.rglob("*"))
        if p.is_file() and p.suffix.lower() == ".sql"
    ]


def save_generated_semantic_model(output_dir: str, model_name: str, semantic_yaml_text: str) -> str:
    out_dir = Path(output_dir)
    if not out_dir.is_absolute():
        out_dir = _project_root() / out_dir

    out_dir.mkdir(parents=True, exist_ok=True)

    safe_name = model_name.strip().replace(" ", "_")
    out_path = out_dir / f"{safe_name}.yaml"

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(semantic_yaml_text)

    return str(out_path.resolve()).replace("\\", "/")


def build_basic_schema_payload_from_bq_columns(
    table_name: str,
    fully_qualified_name: str,
    columns: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "mode": "single_table",
        "table_name": table_name,
        "fully_qualified_name": fully_qualified_name,
        "columns": columns,
    }


def build_dataset_schema_payload(
    dataset_name: str,
    project_id: str,
    tables: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "mode": "dataset",
        "dataset_name": dataset_name,
        "project_id": project_id,
        "tables": tables,
    }


def semantic_dict_to_yaml_text(payload: Dict[str, Any]) -> str:
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)