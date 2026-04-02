from core.guardrails import validate_sql


def run(ctx: dict) -> dict:
    sql = ctx.get("sql", "")
    semantic = ctx.get("semantic", {}) or {}

    tables = semantic.get("tables", {}) or {}
    allowed_tables = [
        tbl_cfg.get("fully_qualified_name")
        for tbl_cfg in tables.values()
        if isinstance(tbl_cfg, dict) and tbl_cfg.get("fully_qualified_name")
    ]

    validate_sql(sql, allowed_tables)
    return {}