import json

from core.llm_gcp import generate_text


def run(ctx: dict) -> dict:
    source_type = ctx.get("source_type", "")
    model_input = ctx.get("model_input", {})

    prompt = f"""You are analyzing a source model for semantic model generation.

Source type:
{source_type}

Model input:
{json.dumps(model_input, indent=2, default=str)}

If the input mode is dataset:
- identify likely fact tables
- identify likely dimension tables
- identify possible joins using shared keys such as *_id
- identify likely grain for each table
- identify candidate primary keys and time dimensions

If the input mode is single table or SQL model:
- identify likely grain
- identify candidate primary key
- identify likely time dimension
- identify likely dimensions
- identify likely metrics

Return a concise analysis as plain text.
"""
    analysis = generate_text(
        prompt,
        model=ctx["model"],
        temperature=0.1,
        max_output_tokens=1000,
    ).strip()

    return {"analysis": analysis}