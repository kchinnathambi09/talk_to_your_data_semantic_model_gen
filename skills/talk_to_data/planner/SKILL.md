---
name: talk-to-data-planner
description: Use when converting a natural-language analytics question into a constrained execution plan for the talk_to_data agent. Produces a structured JSON plan using only the selected table context, allowed dimensions, allowed metrics, and configured defaults.
user-invocable: false
metadata:
  author: OpenAI
---
# Talk to Data Planner

This skill turns a user question into a compact execution plan for downstream SQL generation.

## Responsibilities
- Interpret the user’s question in business terms.
- Select only valid metrics and dimensions from the supplied semantic context.
- Add a default time filter when required by the semantic defaults.
- Keep the requested row limit within the configured maximum.

## Required Output
Return a JSON object with these keys:
- `intent`
- `metrics`
- `dimensions`
- `filters`
- `order_by`
- `limit`
- `notes`

## Planning Rules
- Use only metric names defined in `semantic.metrics`.
- Use only dimension names defined in `semantic.dimensions`.
- Filters must reference valid dimension names.
- `limit` must never exceed `semantic.defaults.max_rows`.
- If `semantic.defaults.require_time_filter` is true and the user did not specify a time range, add a default filter using `semantic.defaults.time_dimension` for the last `semantic.defaults.time_filter_default_days` days.
- Prefer the fewest fields needed to answer the question.

## Handling Ambiguity
- If the question is broad, prefer a safe preview-style plan with a modest limit.
- Do not invent metrics, dimensions, joins, or filters.
- If the question asks for unsupported logic, keep the plan minimal and explain the constraint in `notes`.

## Validation Expectations
Before handing off to SQL generation:
1. Ensure every metric and dimension is allowed.
2. Ensure every filter references an allowed dimension.
3. Ensure the plan is JSON-serializable.
4. Ensure the limit is within bounds.
