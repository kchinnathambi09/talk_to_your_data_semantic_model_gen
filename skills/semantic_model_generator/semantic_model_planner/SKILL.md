---
name: Semantic Model Planner
description: Creates a structured semantic-model plan from analyzed SQL or schema input using semantic-layer best practices.
user-invocable: false
metadata:
  agent: semantic_model_generator
inputs:
  - source_type
  - model_input
  - analysis
  - model
outputs:
  - plan
---

# Semantic Model Planner

Create a plan for a semantic model in the project's YAML format.

The plan should identify:
- model_name
- base table
- primary key
- dimensions
- metrics
- defaults
- recommended time dimension

Use semantic-layer best practices:
- clear business names
- stable dimensions
- additive numeric metrics where appropriate
- cautious handling of IDs