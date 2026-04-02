import copy
import json
import re

from core.common_semantic import COMMON_ALLOWED_VALUES, COMMON_DATE_DIMENSIONS
from core.llm_gcp import generate_text


def _sanitize_sql(sql: str) -> str:
    s = (sql or "").strip()
    s = re.sub(r"^\s*```(?:sql)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```+\s*$", "", s)
    s = re.sub(r"^\s*(here(’|')?s|here is)\s+the\s+sql\s*:\s*", "", s, flags=re.IGNORECASE)
    return s.strip()


def _remove_trailing_limit(sql: str) -> str:
    return re.sub(r"\s+limit\s+\d+\s*;?\s*$", ";", sql.strip(), flags=re.IGNORECASE)


def _slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def _col_only(field_expr: str) -> str:
    if not field_expr:
        return field_expr
    return field_expr.split(".", 1)[-1].strip()


def _qualify(col: str, alias: str | None) -> str:
    return f"{alias}.{col}" if alias else col


def _get_only_table_and_fqn(semantic: dict):
    tables = semantic.get("tables", {}) or {}
    if len(tables) != 1:
        raise ValueError("Semantic model must contain exactly one table for single-table mode.")
    table_name = next(iter(tables.keys()))
    table_cfg = tables[table_name] or {}
    fqn = table_cfg.get("fully_qualified_name")
    if not fqn:
        raise ValueError(f"Missing fully_qualified_name for table '{table_name}'.")
    return table_name, fqn


def _get_time_dimension_expr(semantic: dict) -> str | None:
    defaults = semantic.get("defaults", {}) or {}
    time_dim_name = defaults.get("time_dimension")
    if not time_dim_name:
        return None

    for dim in semantic.get("dimensions", []) or []:
        if isinstance(dim, dict) and dim.get("name") == time_dim_name:
            return dim.get("expr")
    return None


def _merge_common_semantic(semantic: dict) -> dict:
    merged = copy.deepcopy(semantic)
    dimensions = merged.get("dimensions", []) or []

    # Attach common allowed_values by dimension name if not already present
    for dim in dimensions:
        if not isinstance(dim, dict):
            continue
        dim_name = dim.get("name")
        if not dim_name:
            continue

        if dim_name in COMMON_ALLOWED_VALUES and not dim.get("allowed_values"):
            dim["allowed_values"] = COMMON_ALLOWED_VALUES[dim_name]

    # Add common derived date dimensions if time dimension exists
    existing_names = {d.get("name") for d in dimensions if isinstance(d, dict)}
    time_expr = _get_time_dimension_expr(merged)

    if time_expr:
        for common_dim in COMMON_DATE_DIMENSIONS:
            if common_dim["name"] not in existing_names:
                dimensions.append(
                    {
                        "name": common_dim["name"],
                        "expr": common_dim["expr_template"].format(date_expr=time_expr),
                        "type": common_dim["type"],
                        "description": common_dim["description"],
                    }
                )

    merged["dimensions"] = dimensions
    return merged


def _normalize_dimension_filter_value(semantic: dict, field_name: str, value):
    if value is None:
        return value

    for dim in semantic.get("dimensions", []) or []:
        if not isinstance(dim, dict):
            continue
        if dim.get("name") != field_name:
            continue

        allowed_values = dim.get("allowed_values", {}) or {}
        if not isinstance(allowed_values, dict):
            return value

        value_str = str(value).strip().lower()

        for canonical, synonyms in allowed_values.items():
            candidates = [canonical] + list(synonyms or [])
            for candidate in candidates:
                if str(candidate).strip().lower() == value_str:
                    return canonical

    return value


def _normalize_filters(semantic: dict, filters: list) -> list:
    normalized = []

    for f in filters or []:
        item = dict(f)
        field_name = item.get("field")

        if isinstance(field_name, str):
            field_name = field_name.split(".")[-1].strip()

        op = (item.get("op") or "").upper().strip()
        value = item.get("value")

        if op == "IN" and isinstance(value, list):
            item["value"] = [
                _normalize_dimension_filter_value(semantic, field_name, v)
                for v in value
            ]
        else:
            item["value"] = _normalize_dimension_filter_value(semantic, field_name, value)

        normalized.append(item)

    return normalized


def _metric_expr_from_semantic(metric_name: str, semantic: dict) -> str | None:
    metrics = semantic.get("metrics", {}) or {}
    metric_cfg = metrics.get(metric_name)
    if isinstance(metric_cfg, dict):
        return metric_cfg.get("expr")
    return None


def _metric_label(metric_name: str, semantic: dict) -> str:
    metrics = semantic.get("metrics", {}) or {}
    metric_cfg = metrics.get(metric_name) or {}
    return metric_cfg.get("label") or metric_name


def _dimension_expr_from_semantic(dim_name: str, semantic: dict) -> str | None:
    for dim in semantic.get("dimensions", []) or []:
        if isinstance(dim, dict) and dim.get("name") == dim_name:
            return dim.get("expr")
    return None


def _build_simple_where(filters: list) -> str:
    if not filters:
        return ""

    clauses = []
    for f in filters:
        field_raw = f.get("field")
        op = (f.get("op") or "").upper().strip()
        val = f.get("value")

        if not field_raw or not op:
            continue

        field = str(field_raw)

        if op == "BETWEEN" and isinstance(val, (list, tuple)) and len(val) == 2:
            a, b = val
            clauses.append(f"{field} BETWEEN {json.dumps(a)} AND {json.dumps(b)}")
        elif op == "IN" and isinstance(val, (list, tuple)):
            clauses.append(f"{field} IN ({', '.join(json.dumps(v) for v in val)})")
        elif op in ["=", "!=", ">", "<", ">=", "<=", "LIKE"]:
            clauses.append(f"{field} {op} {json.dumps(val)}")

    if not clauses:
        return ""
    return "WHERE " + " AND ".join(clauses)


def _friendly_metric_alias(metric_name: str, semantic: dict) -> str:
    return _slugify(_metric_label(metric_name, semantic))


def _build_generic_alias(plan: dict, semantic: dict) -> str | None:
    metrics = plan.get("metrics") or []
    dimensions = plan.get("dimensions") or []
    filters = plan.get("filters") or []

    if len(metrics) != 1 or dimensions:
        return None

    base_alias = _friendly_metric_alias(str(metrics[0]), semantic)

    eq_filters = [
        f for f in filters
        if (f.get("op") or "").upper().strip() == "=" and f.get("value") is not None
    ]

    if len(eq_filters) == 1:
        value_slug = _slugify(str(eq_filters[0].get("value")))
        if value_slug:
            return f"{base_alias}_{value_slug}"

    return base_alias


def _qualify_plan_fields_with_dimension_exprs(plan: dict, semantic: dict) -> dict:
    out = copy.deepcopy(plan)

    qualified_filters = []
    for f in out.get("filters", []) or []:
        item = dict(f)
        field_name = item.get("field")
        if isinstance(field_name, str):
            dim_name = field_name.split(".")[-1].strip()
            dim_expr = _dimension_expr_from_semantic(dim_name, semantic)
            if dim_expr:
                item["field"] = dim_expr
        qualified_filters.append(item)
    out["filters"] = qualified_filters

    return out


def _deterministic_single_metric_sql(plan: dict, semantic: dict, base_table_fqn: str) -> str | None:
    metrics = plan.get("metrics") or []
    dimensions = plan.get("dimensions") or []

    if len(metrics) != 1 or dimensions:
        return None

    metric_name = str(metrics[0])
    metric_expr = _metric_expr_from_semantic(metric_name, semantic)
    if not metric_expr:
        return None

    alias_name = _build_generic_alias(plan, semantic)
    select_sql = metric_expr if not alias_name else f"{metric_expr} AS {alias_name}"

    where_clause = _build_simple_where(plan.get("filters", []))

    sql = f"SELECT\n  {select_sql}\nFROM `{base_table_fqn}` AS t\n"
    if where_clause:
        sql += where_clause + "\n"
    sql += ";"

    return _remove_trailing_limit(sql)


def _deterministic_groupby_sql(plan: dict, semantic: dict, base_table_fqn: str) -> str | None:
    metrics = plan.get("metrics") or []
    dimensions = plan.get("dimensions") or []

    if len(metrics) != 1 or not dimensions:
        return None

    metric_name = str(metrics[0])
    metric_expr = _metric_expr_from_semantic(metric_name, semantic)
    if not metric_expr:
        return None

    select_parts = []
    group_by_parts = []
    order_by_parts = []

    for dim_name in dimensions:
        dim_expr = _dimension_expr_from_semantic(str(dim_name), semantic)
        if not dim_expr:
            return None
        dim_alias = _slugify(str(dim_name))
        select_parts.append(f"{dim_expr} AS {dim_alias}")
        group_by_parts.append(dim_expr)
        order_by_parts.append(dim_alias)

    metric_alias = _friendly_metric_alias(metric_name, semantic)
    select_parts.append(f"{metric_expr} AS {metric_alias}")

    where_clause = _build_simple_where(plan.get("filters", []))

    sql = "SELECT\n  " + ",\n  ".join(select_parts) + f"\nFROM `{base_table_fqn}` AS t\n"
    if where_clause:
        sql += where_clause + "\n"
    sql += "GROUP BY\n  " + ",\n  ".join(group_by_parts) + "\n"
    if order_by_parts:
        sql += "ORDER BY\n  " + ",\n  ".join(order_by_parts) + ";\n"
    else:
        sql += ";"

    return _remove_trailing_limit(sql.rstrip())


def run(ctx: dict) -> dict:
    semantic = _merge_common_semantic(ctx["semantic"])
    question = ctx.get("question", "") or ""
    plan = copy.deepcopy(ctx.get("plan", {}) or {})

    _, base_table_fqn = _get_only_table_and_fqn(semantic)

    plan["filters"] = _normalize_filters(semantic, plan.get("filters", []))
    plan = _qualify_plan_fields_with_dimension_exprs(plan, semantic)

    sql = _deterministic_single_metric_sql(plan, semantic, base_table_fqn)
    if sql:
        return {"sql": sql}

    sql = _deterministic_groupby_sql(plan, semantic, base_table_fqn)
    if sql:
        return {"sql": sql}

    prompt = f"""Output ONLY BigQuery Standard SQL.
Constraints:
- Use ONLY tables in semantic.tables[].fully_qualified_name
- Use metric expr EXACTLY as semantic.metrics[*].expr
- Use dimension expr EXACTLY as semantic.dimensions[*].expr
- Use semantic metadata only. Do not assume any table-specific names.
- Common derived date dimensions may exist, such as month_name, day_of_week, year_month, week_of_month.
- Use readable aliases for output columns.
- Never output incomplete SQL.
- Never emit 'AS' without an alias after it.
- Do NOT use markdown.
- Do NOT include explanations.
- Do NOT add LIMIT.
- Return SQL only.

Semantic (JSON):
{json.dumps(semantic, indent=2)}

Plan (JSON):
{json.dumps(plan, indent=2)}

User question:
{question}
"""
    sql = generate_text(prompt, model=ctx["model"], temperature=0.0, max_output_tokens=1400)
    sql = _sanitize_sql(sql)
    sql = _remove_trailing_limit(sql)
    sql = sql.rstrip(";").strip() + ";"
    return {"sql": sql}