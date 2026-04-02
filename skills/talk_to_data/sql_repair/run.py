import json
import re
from core.llm_gcp import generate_text


def _sanitize_sql(sql: str) -> str:
    s = (sql or "").strip()
    s = re.sub(r"^\s*```(?:sql)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```+\s*$", "", s)
    return s.strip()


def run(ctx: dict) -> dict:
    question = ctx.get("question", "")
    semantic = ctx.get("semantic", {})
    sql = ctx.get("sql", "")
    error_message = ctx.get("sql_error", "")

    prompt = f"""You are fixing BigQuery GoogleSQL.

User question:
{question}

Semantic model:
{json.dumps(semantic, indent=2)}

Broken SQL:
{sql}

BigQuery error:
{error_message}

Rules:
- Return ONLY corrected BigQuery SQL.
- Use valid BigQuery syntax.
- Do not change the intended meaning.
- Do not add LIMIT.
- If using DIV, use DIV(X, Y), not infix DIV.
- Never return incomplete SQL.
- Never emit AS without an alias.
- If a fully qualified table name contains hyphens, wrap it in backticks.
"""

    fixed_sql = generate_text(prompt, model=ctx["model"], temperature=0.0, max_output_tokens=1200)
    fixed_sql = _sanitize_sql(fixed_sql)
    fixed_sql = fixed_sql.rstrip(";").strip() + ";"
    return {"sql": fixed_sql}