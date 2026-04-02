import json
from datetime import date, datetime

import pandas as pd
from core.llm_gcp import generate_text


def _json_safe(value):
    if value is None:
        return None

    if isinstance(value, (date, datetime, pd.Timestamp)):
        return value.isoformat()

    # pandas missing values
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]

    # numpy / pandas scalars
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except Exception:
            pass

    return value


def _df_preview(df: pd.DataFrame, max_rows: int = 12) -> list[dict]:
    if df is None or df.empty:
        return []

    preview = df.head(max_rows).copy()
    records = preview.to_dict(orient="records")
    return [_json_safe(r) for r in records]


def _numeric_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]


def _categorical_cols(df: pd.DataFrame) -> list[str]:
    numeric = set(_numeric_cols(df))
    return [c for c in df.columns if c not in numeric]


def _compute_basic_stats(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {}

    stats = {
        "row_count": int(len(df)),
        "columns": list(df.columns),
    }

    numeric = _numeric_cols(df)
    if numeric:
        stats["numeric_summary"] = {}
        for col in numeric[:5]:
            series = df[col].dropna()
            if not series.empty:
                stats["numeric_summary"][col] = {
                    "min": series.min(),
                    "max": series.max(),
                    "mean": float(series.mean()),
                }

    if len(df.columns) >= 2 and len(numeric) >= 2:
        x, y = numeric[0], numeric[1]
        tmp = df[[x, y]].dropna()
        if len(tmp) >= 2:
            corr = tmp[x].corr(tmp[y])
            if pd.notna(corr):
                stats["correlation"] = {
                    "x": x,
                    "y": y,
                    "value": float(corr),
                }

    return _json_safe(stats)


def _is_incomplete_text(text: str) -> bool:
    if not text:
        return True

    stripped = text.strip()
    if len(stripped) < 20:
        return True

    bad_endings = [
        " an", " a", " the", " with", " by", " for", " of",
        " in", " to", " and", " or", " but", ":", ",", "(", "-"
    ]
    lower = stripped.lower()
    if any(lower.endswith(x) for x in bad_endings):
        return True

    if stripped[-1].isalnum():
        if "\n" not in stripped and len(stripped.split()) < 8:
            return True

    return False


def _corr_text(corr_value: float, x: str, y: str) -> str:
    strength = abs(corr_value)
    if strength >= 0.7:
        strength_text = "strong"
    elif strength >= 0.4:
        strength_text = "moderate"
    elif strength >= 0.2:
        strength_text = "weak"
    else:
        strength_text = "little to no"

    if corr_value > 0.1:
        direction = "positive"
    elif corr_value < -0.1:
        direction = "negative"
    else:
        direction = "no clear linear"

    if direction == "no clear linear":
        return f"There is {strength_text} to no clear linear relationship between {x} and {y} (correlation {corr_value:.2f})."
    return f"There is a {strength_text} {direction} relationship between {x} and {y} (correlation {corr_value:.2f})."


def _fallback_insights(df: pd.DataFrame, question: str = "") -> str:
    if df is None or df.empty:
        return "No rows were returned for this question."

    lines = []
    row_count = len(df)
    lines.append(f"The query returned {row_count} row{'s' if row_count != 1 else ''}.")

    numeric = _numeric_cols(df)
    categorical = _categorical_cols(df)

    if row_count == 1 and numeric:
        parts = []
        row = df.iloc[0]
        for col in numeric[:3]:
            parts.append(f"{col} = {_json_safe(row[col])}")
        if parts:
            lines.append("Key result: " + ", ".join(parts) + ".")

    if len(categorical) >= 1 and len(numeric) >= 1 and row_count > 1:
        cat = categorical[0]
        num = numeric[0]
        top_row = df.sort_values(by=num, ascending=False).iloc[0]
        lines.append(f"The highest {num} is for {cat} = {_json_safe(top_row[cat])} with value {_json_safe(top_row[num])}.")

    if len(numeric) >= 2 and row_count > 1:
        x, y = numeric[0], numeric[1]
        tmp = df[[x, y]].dropna()
        if len(tmp) >= 2:
            corr = tmp[x].corr(tmp[y])
            if pd.notna(corr):
                lines.append(_corr_text(float(corr), x, y))

    return "\n".join(f"- {line}" for line in lines)


def run(ctx: dict) -> dict:
    df = ctx.get("df")
    question = ctx.get("question", "")
    sql = ctx.get("sql", "")

    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return {"insights": "No results were returned, so there are no insights to summarize."}

    preview = _df_preview(df, max_rows=12)
    stats = _compute_basic_stats(df)

    prompt = f"""You are writing concise business insights from a SQL result.

User question:
{question}

SQL used:
{sql}

Result metadata:
{json.dumps(stats, indent=2)}

Result preview:
{json.dumps(preview, indent=2)}

Instructions:
- Write 3 to 5 short bullet points.
- Every bullet must be a complete sentence.
- Do not repeat raw SQL.
- Mention the most important numeric finding.
- If there are 2 numeric measures and a relationship is visible, mention the correlation/relationship.
- If there is a ranking, mention the top performer.
- If the result is a single KPI, explain it plainly.
- Keep it crisp and readable.
- Return plain text bullets only.
"""

    insights = generate_text(
        prompt,
        model=ctx["model"],
        temperature=0.2,
        max_output_tokens=500,
    ).strip()

    if _is_incomplete_text(insights):
        insights = _fallback_insights(df, question)

    return {"insights": insights}