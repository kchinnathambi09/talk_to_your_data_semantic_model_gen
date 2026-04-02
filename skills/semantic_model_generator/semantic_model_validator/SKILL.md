---
name: Semantic Model Validator
description: Validates that the generated semantic model YAML has required project fields.
user-invocable: false
metadata:
  agent: semantic_model_generator
inputs:
  - semantic_yaml
outputs:
  - semantic_yaml
---

# Semantic Model Validator

Validate the generated semantic model.

Checks:
- model_name exists
- tables exists
- metrics exists
- dimensions exists
- defaults exists

Raise an error if required sections are missing.