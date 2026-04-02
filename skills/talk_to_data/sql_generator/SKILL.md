---
name: talk-to-data-sql-generator
description: Use when translating a validated analytics plan into executable BigQuery Standard SQL for the talk_to_data agent. Honors the selected semantic context, allowed tables, joins, metric expressions, dimension expressions, and row limits.
user-invocable: false
metadata:
  author: OpenAI
---
# Talk to Data SQL Generator

This skill converts the planner output into BigQuery Standard SQL.

## Responsibilities
- Build SQL only from the provided semantic context.
- Use table names exactly as defined in `semantic.tables`.
- Use joins only from `semantic.joins`.
- Use metric expressions exactly as defined in `semantic.metrics`.
- Use dimension expressions exactly as defined in `semantic.dimensions`.
- Always include the requested limit.

## SQL Rules
- Output only BigQuery Standard SQL.
- Generate `SELECT` queries only.
- Do not reference undeclared tables, columns, joins, or expressions.
- Preserve metric expressions exactly.
- Preserve dimension expressions exactly.
- If a time filter is required, ensure it is present.
- End with a semicolon.

## Safety Constraints
- Never emit DDL or DML.
- Never use wildcard table expansion unless the semantic model explicitly provides it.
- Never add inferred joins not present in `semantic.joins`.
- Never exceed `plan.limit`.

## Completion Checklist
1. Query is `SELECT` only.
2. All referenced tables are whitelisted.
3. All joins come from the semantic configuration.
4. All selected metrics and dimensions map to approved expressions.
5. A `LIMIT` clause is present.
