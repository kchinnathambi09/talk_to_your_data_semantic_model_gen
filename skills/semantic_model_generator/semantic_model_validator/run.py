import yaml


def run(ctx: dict) -> dict:
    semantic_yaml = ctx.get("semantic_yaml", "")
    payload = yaml.safe_load(semantic_yaml)

    required = ["model_name", "tables", "metrics", "dimensions", "defaults"]
    missing = [k for k in required if k not in payload]

    if missing:
        raise ValueError(f"Generated semantic model missing required sections: {missing}")

    return {"semantic_yaml": semantic_yaml}