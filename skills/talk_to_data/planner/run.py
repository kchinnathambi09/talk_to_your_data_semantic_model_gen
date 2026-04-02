import json
import re
from core.llm_gcp import generate_text


def safe_int(value, default):
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _user_asked_for_limit(question: str) -> bool:
    q = (question or "").lower()
    return any([
        re.search(r"\blimit\s+\d+\b", q),
        re.search(r"\btop\s+\d+\b", q),
        re.search(r"\bshow\s+\d+\b", q),
        re.search(r"\bdisplay\s+\d+\b", q),
        re.search(r"\bsample\s+\d+\b", q),
        re.search(r"\bfirst\s+\d+\b", q),
        re.search(r"\blast\s+\d+\b", q),
        re.search(r"\b\d+\s+rows\b", q),
    ])


def _dim_expr_map(semantic: dict) -> dict:
    m = {}
    for d in (semantic.get("dimensions") or []):
        if isinstance(d, dict) and d.get("name") and d.get("expr"):
            m[d["name"]] = d["expr"]
    return m


def _extract_json_object(text: str) -> str | None:
    if not text:
        return None
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _safe_json_loads(text: str) -> dict:
    raw = (text or "").strip()
    raw = re.sub(r"^\s*```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```+\s*$", "", raw)

    obj = _extract_json_object(raw) or raw
    obj = re.sub(r",\s*([}\]])", r"\1", obj)
    return json.loads(obj)


def _base_plan() -> dict:
    return {
        "intent": "unknown",
        "metrics": [],
        "dimensions": [],
        "filters": [],
        "order_by": [],
        "limit": None,
        "notes": ""
    }


def run(ctx: dict) -> dict:
    semantic = ctx["semantic"]
    defaults = semantic.get("defaults", {}) or {}

    default_days = safe_int(defaults.get("time_filter_default_days"), 30)
    require_time = bool(defaults.get("require_time_filter", True))
    time_dim_name = defaults.get("time_dimension") or "purchase_date"

    dims = [d.get("name") for d in (semantic.get("dimensions") or []) if isinstance(d, dict) and d.get("name")]
    mets = list((semantic.get("metrics") or {}).keys())

    question = ctx.get("question", "") or ""
    q = question.lower()

    prompt = f"""Return ONLY valid JSON. No markdown. No extra text.

You MUST use only these metric names (if you use metrics): {mets}
You MUST use only these dimension names (if you use dimensions/filters): {dims}

LIMIT POLICY:
- Do NOT set a limit unless the user explicitly asked for top N / limit N / show N / sample N / first N / last N / "N rows".

If defaults.require_time_filter={require_time} and a time filter is needed but not provided,
you may assume last {default_days} days using the time dimension '{time_dim_name}'.

Return JSON exactly with this shape:
{{
  "intent": "string",
  "metrics": [],
  "dimensions": [],
  "filters": [],
  "order_by": [],
  "limit": null,
  "notes": ""
}}

User question:
{question}
"""
    text = generate_text(prompt, model=ctx["model"], temperature=0.1, max_output_tokens=1200)

    plan = _base_plan()
    try:
        plan = _safe_json_loads(text)
        for k in ["intent", "metrics", "dimensions", "filters", "order_by", "limit", "notes"]:
            plan.setdefault(k, _base_plan()[k])
    except Exception:
        plan = _base_plan()
        plan["notes"] = "Planner returned invalid JSON; used fallback plan."

    if not _user_asked_for_limit(question):
        plan["limit"] = None

    dim_map = _dim_expr_map(semantic)
    time_dim_expr = dim_map.get(time_dim_name) or time_dim_name
    has_date_language = ("date" in q) or (time_dim_name.lower() in q)

    if has_date_language and (("first" in q or "earliest" in q) and ("last" in q or "latest" in q)):
        plan["intent"] = "date_range"
        plan["select_type"] = "aggregate"
        plan["aggregations"] = [
            {"func": "MIN", "field": time_dim_expr, "alias": f"first_{time_dim_name}"},
            {"func": "MAX", "field": time_dim_expr, "alias": f"last_{time_dim_name}"},
        ]
        plan["metrics"] = []
        plan["dimensions"] = []
        plan["filters"] = plan.get("filters", []) or []
        plan["order_by"] = []
        plan["limit"] = None
        plan["notes"] = (plan.get("notes", "") + f" Forced MIN+MAX for first/last {time_dim_name}.").strip()

    elif has_date_language and ("last" in q or "latest" in q or "most recent" in q):
        plan["intent"] = "latest_date"
        plan["select_type"] = "aggregate"
        plan["aggregations"] = [
            {"func": "MAX", "field": time_dim_expr, "alias": f"last_{time_dim_name}"},
        ]
        plan["metrics"] = []
        plan["dimensions"] = []
        plan["filters"] = plan.get("filters", []) or []
        plan["order_by"] = []
        plan["limit"] = None
        plan["notes"] = (plan.get("notes", "") + f" Forced MAX for {time_dim_name}.").strip()

    elif has_date_language and ("first" in q or "earliest" in q):
        plan["intent"] = "earliest_date"
        plan["select_type"] = "aggregate"
        plan["aggregations"] = [
            {"func": "MIN", "field": time_dim_expr, "alias": f"first_{time_dim_name}"},
        ]
        plan["metrics"] = []
        plan["dimensions"] = []
        plan["filters"] = plan.get("filters", []) or []
        plan["order_by"] = []
        plan["limit"] = None
        plan["notes"] = (plan.get("notes", "") + f" Forced MIN for {time_dim_name}.").strip()

    return {"plan": plan}