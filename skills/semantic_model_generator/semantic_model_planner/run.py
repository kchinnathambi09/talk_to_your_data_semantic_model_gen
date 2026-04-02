import json
import re
from typing import Any, Dict, List

from core.llm_gcp import generate_text


def _extract_json_block(text: str) -> str:
    raw = (text or "").strip()
    raw = re.sub(r"^\s*```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```+\s*$", "", raw)

    start = raw.find("{")
    if start == -1:
        raise ValueError("No JSON object found in planner output.")

    depth = 0
    in_string = False
    escape = False
    end = None

    for i in range(start, len(raw)):
        ch = raw[i]

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if end is None:
        raise ValueError("Incomplete JSON object in planner output.")

    return raw[start:end]


def _cleanup_json_text(text: str) -> str:
    cleaned = text
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    cleaned = cleaned.replace("“", '"').replace("”", '"').replace("’", "'")
    return cleaned


def _safe_json_load(text: str) -> dict:
    block = _extract_json_block(text)
    block = _cleanup_json_text(block)
    return json.loads(block)


def _guess_type(col_type: str) -> str:
    t = (col_type or "").upper()
    if t in {"DATE", "DATETIME", "TIMESTAMP"}:
        return "DATE"
    if t in {"STRING", "BOOL", "BOOLEAN"}:
        return "STRING"
    if t in {"INT64", "INTEGER", "FLOAT64", "NUMERIC", "BIGNUMERIC", "DECIMAL"}:
        return t
    return "STRING"


def _is_metric_candidate(col_name: str, col_type: str) -> bool:
    name = (col_name or "").lower()
    typ = (col_type or "").upper()

    if typ not in {"INT64", "INTEGER", "FLOAT64", "NUMERIC", "BIGNUMERIC", "DECIMAL"}:
        return False

    blocked = ["id", "_id", "zip", "postal", "phone"]
    return not any(b in name for b in blocked)


def _find_primary_key(columns: List[Dict[str, Any]]) -> str:
    names = [c.get("name", "") for c in columns]
    lowered = {n.lower(): n for n in names}

    preferred = [
        "order_line_id",
        "order_id",
        "id",
        "customer_id",
        "product_id",
        "transaction_id",
        "record_id",
    ]
    for p in preferred:
        if p in lowered:
            return lowered[p]

    for n in names:
        if n.lower().endswith("_id"):
            return n

    return names[0] if names else ""


def _find_time_dimension(columns: List[Dict[str, Any]]) -> str:
    names = [c.get("name", "") for c in columns]
    lowered = {n.lower(): n for n in names}

    preferred = [
        "purchase_date",
        "order_date",
        "created_at",
        "created_date",
        "event_date",
        "transaction_date",
        "date",
    ]
    for p in preferred:
        if p in lowered:
            return lowered[p]

    for c in columns:
        typ = (c.get("type", "") or "").upper()
        if typ in {"DATE", "DATETIME", "TIMESTAMP"}:
            return c.get("name", "")

    return ""


def _single_table_plan(table_name: str, fully_qualified_name: str, columns: List[Dict[str, Any]]) -> dict:
    primary_key = _find_primary_key(columns)
    time_dimension = _find_time_dimension(columns)

    dimensions = []
    metrics = []

    for c in columns:
        name = c.get("name", "")
        col_type = c.get("type", "STRING")
        description = c.get("description", "") or f"{name} column"

        if name == primary_key:
            continue

        if _is_metric_candidate(name, col_type):
            metric_name = f"total_{name}" if not name.startswith("total_") else name
            metrics.append(
                {
                    "name": metric_name,
                    "expr": f"SUM(t.{name})",
                    "label": metric_name.replace("_", " "),
                    "description": f"Total {name.replace('_', ' ')}",
                }
            )
        else:
            dimensions.append(
                {
                    "name": "state" if name.lower() == "customer_state" else name,
                    "expr": f"t.{name}",
                    "type": _guess_type(col_type),
                    "description": description,
                }
            )

    if primary_key:
        metrics.insert(
            0,
            {
                "name": f"total_{table_name.replace('fct_', '').replace('dim_', '')}" if table_name else "total_rows",
                "expr": f"COUNT(DISTINCT t.{primary_key})",
                "label": "total rows" if not table_name else f"total {table_name.replace('_', ' ')}",
                "description": f"Distinct count of {primary_key}",
            },
        )

    return {
        "mode": "single_table",
        "model_name": table_name,
        "table_name": table_name,
        "fully_qualified_name": fully_qualified_name,
        "primary_key": primary_key,
        "dimensions": dimensions,
        "metrics": metrics,
        "defaults": {
            "time_dimension": "state" if time_dimension == "customer_state" else time_dimension,
            "max_rows": 200,
            "require_time_filter": False,
            "time_filter_default_days": 30,
        },
    }


def _dataset_plan(model_input: dict) -> dict:
    dataset_name = model_input.get("dataset_name", "")
    tables = model_input.get("tables", []) or []

    table_entries = {}
    dimensions = []
    metrics = []
    joins = []

    for table in tables:
        table_name = table.get("table_name", "")
        fully_qualified_name = table.get("fully_qualified_name", "")
        columns = table.get("columns", []) or []

        primary_key = _find_primary_key(columns)

        table_entries[table_name] = {
            "description": f"Semantic model for {table_name}",
            "fully_qualified_name": fully_qualified_name,
            "primary_key": primary_key,
            "columns": {},
        }

        # Basic joins on shared *_id keys
        for other in tables:
            other_name = other.get("table_name", "")
            if other_name == table_name:
                continue

            other_columns = {c.get("name") for c in other.get("columns", [])}
            for c in columns:
                col_name = c.get("name")
                if col_name and col_name.endswith("_id") and col_name in other_columns:
                    joins.append(
                        {
                            "left_table": table_name,
                            "right_table": other_name,
                            "left_key": col_name,
                            "right_key": col_name,
                            "relationship": "many_to_one",
                        }
                    )

        # Add dimensions/metrics for the first fact-like table only as a simple start
        if not metrics and table_name.startswith("fct_"):
            single = _single_table_plan(table_name, fully_qualified_name, columns)
            dimensions = single["dimensions"]
            metrics = single["metrics"]

    # de-duplicate joins
    deduped = []
    seen = set()
    for j in joins:
        key = (j["left_table"], j["right_table"], j["left_key"], j["right_key"])
        if key not in seen:
            seen.add(key)
            deduped.append(j)

    return {
        "mode": "dataset",
        "model_name": f"{dataset_name}_semantic_model",
        "dataset_name": dataset_name,
        "tables": table_entries,
        "joins": deduped,
        "dimensions": dimensions,
        "metrics": metrics,
        "defaults": {
            "time_dimension": "",
            "max_rows": 200,
            "require_time_filter": False,
            "time_filter_default_days": 30,
        },
    }


def _build_plan(model_input: dict) -> dict:
    mode = model_input.get("mode")

    if mode == "dataset":
        return _dataset_plan(model_input)

    if mode == "single_table":
        return _single_table_plan(
            model_input.get("table_name", ""),
            model_input.get("fully_qualified_name", ""),
            model_input.get("columns", []) or [],
        )

    # sql model fallback
    sql_text = model_input.get("sql_text", "") or ""
    model_name = model_input.get("suggested_model_name", "generated_model")
    fqn_match = re.search(r"FROM\s+`([^`]+)`", sql_text, flags=re.IGNORECASE)
    fully_qualified_name = fqn_match.group(1) if fqn_match else ""
    aliases = re.findall(r"\bAS\s+([A-Za-z_][A-Za-z0-9_]*)", sql_text, flags=re.IGNORECASE)
    columns = [{"name": c, "type": "STRING", "description": f"{c} column"} for c in aliases]

    return _single_table_plan(model_name, fully_qualified_name, columns)


def run(ctx: dict) -> dict:
    source_type = ctx.get("source_type", "")
    model_input = ctx.get("model_input", {})
    analysis = ctx.get("analysis", "")

    prompt = f"""You are planning a semantic model in a custom YAML format.

Source type:
{source_type}

Model input:
{json.dumps(model_input, indent=2, default=str)}

Analysis:
{analysis}

Return ONLY valid JSON.
Do not include markdown.
Do not include comments.
Use double quotes for all keys and string values.
Do not truncate the JSON.
"""
    try:
        raw = generate_text(
            prompt,
            model=ctx["model"],
            temperature=0.0,
            max_output_tokens=2200,
        )
        plan = _safe_json_load(raw)
        return {"plan": plan}
    except Exception:
        return {"plan": _build_plan(model_input)}