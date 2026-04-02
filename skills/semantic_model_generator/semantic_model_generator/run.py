from core.semantic_model_builder import semantic_dict_to_yaml_text


def run(ctx: dict) -> dict:
    plan = ctx.get("plan", {}) or {}

    if plan.get("mode") == "dataset":
        payload = {
            "model_name": plan.get("model_name", ""),
            "default_dataset": plan.get("dataset_name", ""),
            "tables": plan.get("tables", {}),
            "joins": plan.get("joins", []),
            "metrics": {
                m.get("name"): {
                    "description": m.get("description", ""),
                    "label": m.get("label", m.get("name")),
                    "expr": m.get("expr", ""),
                }
                for m in plan.get("metrics", [])
            },
            "dimensions": plan.get("dimensions", []),
            "defaults": plan.get(
                "defaults",
                {
                    "time_dimension": "",
                    "max_rows": 200,
                    "require_time_filter": False,
                    "time_filter_default_days": 30,
                },
            ),
        }
        semantic_yaml = semantic_dict_to_yaml_text(payload)
        return {"semantic_yaml": semantic_yaml}

    fully_qualified_name = plan.get("fully_qualified_name", "")
    fq_parts = fully_qualified_name.split(".")
    default_dataset = fq_parts[1] if len(fq_parts) >= 2 else ""

    table_name = plan.get("table_name", "")
    primary_key = plan.get("primary_key", "")

    dimensions = []
    for d in plan.get("dimensions", []):
        dimensions.append(
            {
                "name": d.get("name"),
                "expr": d.get("expr"),
                "type": d.get("type", "STRING"),
                "description": d.get("description", ""),
            }
        )

    metrics = {}
    for m in plan.get("metrics", []):
        metrics[m.get("name")] = {
            "description": m.get("description", ""),
            "label": m.get("label", m.get("name")),
            "expr": m.get("expr", ""),
        }

    payload = {
        "model_name": plan.get("model_name", table_name),
        "default_dataset": default_dataset,
        "tables": {
            table_name: {
                "description": f"Semantic model for {table_name}",
                "fully_qualified_name": fully_qualified_name,
                "primary_key": primary_key,
                "columns": {},
            }
        },
        "metrics": metrics,
        "dimensions": dimensions,
        "defaults": plan.get(
            "defaults",
            {
                "time_dimension": "",
                "max_rows": 200,
                "require_time_filter": False,
                "time_filter_default_days": 30,
            },
        ),
    }

    semantic_yaml = semantic_dict_to_yaml_text(payload)
    return {"semantic_yaml": semantic_yaml}