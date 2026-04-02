---
name: Model Analyzer
description: Analyzes a local SQL model or a BigQuery table schema and extracts semantic clues such as grain, candidate keys, dimensions, metrics, and time columns.
user-invocable: false
metadata:
  agent: semantic_model_generator
inputs:
  - source_type
  - model_input
  - model
outputs:
  - analysis
---

# Model Analyzer

Analyze the provided SQL model text or BigQuery table schema.

Focus on:
- likely grain
- candidate primary key
- likely time dimension
- likely numeric metric candidates
- likely categorical dimensions
- business meaning inferred from names

Return a concise structured analysis as plain text.