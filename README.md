# Talk to the Data + Semantic Model Generator

This project contains **two agents in the same Streamlit application**:

1. **Talk to Data**  
   Lets users ask natural-language questions against BigQuery tables using a semantic model.

2. **Semantic Model Generator**  
   Lets users generate semantic models from:
   - a **local SQL model**
   - a **single BigQuery table**
   - or **all tables in a BigQuery dataset**  
   The generated semantic models can then be used by the Talk to Data agent.

---

## Project Goals

The project is designed to provide an end-to-end workflow for natural language analytics:

- select a BigQuery dataset and table
- use a matching semantic model
- generate SQL from user questions
- validate and repair SQL if needed
- execute queries on BigQuery
- render results, insights, and charts
- generate semantic models when one does not exist

---

## Features

### Talk to Data
- dataset dropdown
- table dropdown based on selected dataset
- semantic model auto-matched by table name
- technical details view for:
  - planner output
  - generated SQL
- SQL repair loop for invalid BigQuery SQL
- results table
- auto charting
- insights generation
- chart improvements for:
  - trends over time
  - correlation / relationship questions
  - grouped categorical analysis

### Semantic Model Generator
- local SQL model input
- BigQuery single-table semantic model generation
- BigQuery whole-dataset generation
- generates **one semantic model per table** for dataset mode
- preview generated YAML before save
- save only when user clicks **Save Semantic Model**
- supports integration with Talk to Data workflow when no semantic model exists for a selected table

---

## Current Architecture

### Agent 1: `talk_to_data`
Located under:

```text
skills/talk_to_data/