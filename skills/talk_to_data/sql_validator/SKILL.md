---
name: talk-to-data-sql-validator
description: Use when validating generated BigQuery SQL for the talk_to_data agent before execution. Enforces deterministic guardrails such as SELECT-only behavior, allowed-table usage, and required LIMIT clauses.
user-invocable: false
metadata:
  author: OpenAI
---
# Talk to Data SQL Validator

This skill performs deterministic validation on generated SQL before execution.

## Validation Checks
- Query must be `SELECT` only.
- Query must reference only approved tables.
- Query must include a `LIMIT` clause.

## Failure Handling
- Reject the SQL if any validation check fails.
- Return actionable error details from the guardrail layer.
- Do not attempt to repair the SQL inside this skill.

## Completion Standard
Execution can proceed only when all deterministic checks pass.
