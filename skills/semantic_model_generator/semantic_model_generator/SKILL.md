---
name: Semantic Model Generator
description: Generates the final semantic model YAML in the project format from a semantic planning payload.
user-invocable: false
metadata:
  agent: semantic_model_generator
inputs:
  - plan
outputs:
  - semantic_yaml
---

# Semantic Model Generator

Generate final YAML for the project semantic model format.

Required output shape:
- model_name
- default_dataset
- tables
- metrics
- dimensions
- defaults