---
name: SQL Repair
description: Repairs invalid BigQuery SQL using the user question, semantic model, broken SQL, and the SQL error message.
user-invocable: false
metadata:
  tool: sql_repair
  owner: talk_to_data
inputs:
  - question
  - semantic
  - sql
  - sql_error
  - model
outputs:
  - sql
---

# SQL Repair

## Purpose
Repair broken BigQuery SQL without changing the intended business meaning.

## Inputs
- `question`: original user question
- `semantic`: selected semantic model
- `sql`: broken SQL
- `sql_error`: validator or BigQuery error message
- `model`: LLM model name

## Output
- `sql`: corrected BigQuery SQL

## Requirements
- Return only valid BigQuery Standard SQL
- Do not add explanations
- Do not add markdown fences
- Do not change the meaning of the query
- Do not add `LIMIT`
- Preserve the selected table(s) from the semantic model
- Use metric and dimension expressions from the semantic model when relevant

## BigQuery-specific reminders
- If using division with integer semantics, use `DIV(X, Y)` not infix `X DIV Y`
- Fully qualified table names containing hyphens must be wrapped in backticks
- Never emit `AS` without a valid alias after it
- Non-aggregated selected fields must be grouped correctly
- Keep aliases readable and SQL-safe

## Examples of issues to repair
- Invalid BigQuery syntax
- Missing alias after `AS`
- Missing backticks around fully-qualified table names
- Incorrect grouping
- Incorrect derived date expressions such as week-of-month