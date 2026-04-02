# NL → BigQuery Insights (Talk to Data)

This project uses a skills-style agent called `talk_to_data`.

## Updated skill layout
Each capability now lives under the agent folder:
- `skills/talk_to_data/planner/SKILL.md`
- `skills/talk_to_data/sql_generator/SKILL.md`
- `skills/talk_to_data/sql_validator/SKILL.md`
- `skills/talk_to_data/narrator/SKILL.md`

Each `SKILL.md` now follows the dbt-agent-skills style template with YAML front matter plus structured markdown guidance.

## UI behavior
The Streamlit sidebar now supports:
- dataset selection
- table selection within the chosen dataset
- switching between a dynamic single-table semantic context and the configured semantic model

Dynamic table mode reads the selected BigQuery table schema and builds a lightweight semantic context so the user can ask questions against that table directly.


## Updated UI behavior

The sidebar now has three explicit dropdowns:
- Dataset
- Table
- Semantic model (loaded from the local `semantic_models/` folder)

The app no longer auto-generates a semantic model from the selected table schema. The selected local semantic model file is the only semantic context used during planning and SQL generation.