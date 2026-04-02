import os
import sys
from pathlib import Path

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

import streamlit as st

from core.bigquery_exec import get_table_schema, list_datasets, list_tables
from core.config import load_config
from core.semantic_model_builder import (
    build_basic_schema_payload_from_bq_columns,
    build_dataset_schema_payload,
    list_local_sql_models,
    load_sql_model_file,
    save_generated_semantic_model,
)
from core.skill_runtime import load_skill


def normalize_dataset_name(dataset_value: str) -> str:
    if not dataset_value:
        return dataset_value
    parts = dataset_value.split(".")
    return parts[-1].strip()


def run_semantic_model_generator_pipeline(
    source_type: str,
    model_input: dict,
    skills_dir: str,
    llm_model: str,
):
    ctx = {
        "source_type": source_type,
        "model_input": model_input,
        "model": llm_model,
    }

    ctx.update(load_skill(skills_dir, "model_analyzer").run(ctx))
    ctx.update(load_skill(skills_dir, "semantic_model_planner").run(ctx))
    ctx.update(load_skill(skills_dir, "semantic_model_generator").run(ctx))
    ctx.update(load_skill(skills_dir, "semantic_model_validator").run(ctx))
    return ctx


def generate_semantic_model_for_selected_table(
    project_id: str,
    dataset_name: str,
    table_name: str,
    llm_model: str,
    skills_dir: str,
):
    fully_qualified_name = f"{project_id}.{dataset_name}.{table_name}"
    columns = get_table_schema(dataset_name, table_name, project_id=project_id)

    model_input = build_basic_schema_payload_from_bq_columns(
        table_name=table_name,
        fully_qualified_name=fully_qualified_name,
        columns=columns,
    )

    ctx = run_semantic_model_generator_pipeline(
        source_type="BigQuery",
        model_input=model_input,
        skills_dir=skills_dir,
        llm_model=llm_model,
    )
    return ctx


def render_semantic_model_generator_tab():
    cfg = load_config("config/config.yaml")

    project_id = cfg.raw.get("gcp", {}).get("project_id") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    default_dataset = normalize_dataset_name(
        os.environ.get("BQ_DEFAULT_DATASET", cfg.raw.get("bigquery", {}).get("dataset", ""))
    )
    llm_model = cfg.raw.get("llm", {}).get("model", "gemini-2.5-flash")

    local_sql_models_dir = cfg.raw.get("app", {}).get("local_sql_models_dir", "sql_models")
    generated_semantic_models_dir = cfg.raw.get("app", {}).get("generated_semantic_models_dir", "semantic_models/generated")
    skills_dir = cfg.raw.get("agents", {}).get("semantic_model_generator", {}).get(
        "skills_dir", "skills/semantic_model_generator"
    )

    if "smg_generated_yaml" not in st.session_state:
        st.session_state.smg_generated_yaml = ""
    if "smg_generated_model_name" not in st.session_state:
        st.session_state.smg_generated_model_name = ""
    if "smg_analysis" not in st.session_state:
        st.session_state.smg_analysis = ""
    if "smg_plan" not in st.session_state:
        st.session_state.smg_plan = None
    if "smg_saved_path" not in st.session_state:
        st.session_state.smg_saved_path = ""

    st.subheader("Semantic Model Generator")
    st.write("Generate a semantic model from a local SQL model, a BigQuery table, or a whole BigQuery dataset.")

    source_type = st.radio(
        "Source",
        options=["Local SQL Model", "BigQuery"],
        horizontal=True,
    )

    model_input = None
    suggested_model_name = ""

    if source_type == "Local SQL Model":
        sql_files = list_local_sql_models(local_sql_models_dir)

        if not sql_files:
            st.warning(f"No SQL files found in {local_sql_models_dir}")
        else:
            selected_sql_file = st.selectbox("SQL model file", sql_files)
            sql_text = load_sql_model_file(selected_sql_file)
            suggested_model_name = Path(selected_sql_file).stem

            with st.expander("Preview SQL model", expanded=False):
                st.code(sql_text, language="sql")

            model_input = {
                "mode": "sql_model",
                "sql_model_path": selected_sql_file,
                "sql_text": sql_text,
                "suggested_model_name": suggested_model_name,
            }

    else:
        generation_scope = st.radio(
            "BigQuery scope",
            options=["Single table", "Whole dataset"],
            horizontal=True,
        )

        datasets = list_datasets(project_id=project_id)
        datasets = [normalize_dataset_name(ds) for ds in datasets]
        datasets = sorted(set(datasets))

        if default_dataset and default_dataset not in datasets:
            datasets = [default_dataset] + datasets

        selected_dataset = st.selectbox(
            "Dataset",
            options=datasets or [default_dataset or ""],
            index=(datasets.index(default_dataset) if default_dataset in datasets else 0),
        )

        if generation_scope == "Single table":
            tables = list_tables(selected_dataset, project_id=project_id) if selected_dataset else []
            selected_table = st.selectbox("Table", options=tables or [""])

            if selected_dataset and selected_table:
                fully_qualified_name = f"{project_id}.{selected_dataset}.{selected_table}"
                columns = get_table_schema(selected_dataset, selected_table, project_id=project_id)
                suggested_model_name = selected_table

                with st.expander("Preview table schema", expanded=False):
                    st.json(columns)

                model_input = build_basic_schema_payload_from_bq_columns(
                    table_name=selected_table,
                    fully_qualified_name=fully_qualified_name,
                    columns=columns,
                )

        else:
            tables = list_tables(selected_dataset, project_id=project_id) if selected_dataset else []
            dataset_tables = []

            for table_name in tables:
                fully_qualified_name = f"{project_id}.{selected_dataset}.{table_name}"
                columns = get_table_schema(selected_dataset, table_name, project_id=project_id)
                dataset_tables.append(
                    {
                        "table_name": table_name,
                        "fully_qualified_name": fully_qualified_name,
                        "columns": columns,
                    }
                )

            suggested_model_name = f"{selected_dataset}_semantic_model" if selected_dataset else "dataset_semantic_model"

            with st.expander("Preview dataset tables", expanded=False):
                st.write(f"Tables found: {len(dataset_tables)}")
                st.json([t["table_name"] for t in dataset_tables])

            if selected_dataset and dataset_tables:
                model_input = build_dataset_schema_payload(
                    dataset_name=selected_dataset,
                    project_id=project_id,
                    tables=dataset_tables,
                )

    model_name = st.text_input("Semantic model name", value=suggested_model_name)

    generate_clicked = st.button("Generate Semantic Model", type="primary")

    if generate_clicked:
        if not model_input:
            st.error("Please select a valid source first.")
            return

        if not model_name.strip():
            st.error("Please enter a semantic model name.")
            return

        try:
            ctx = run_semantic_model_generator_pipeline(
                source_type=source_type,
                model_input=model_input,
                skills_dir=skills_dir,
                llm_model=llm_model,
            )

            generated_yaml = ctx.get("semantic_yaml", "")

            if not generated_yaml:
                st.error("Semantic model generation returned no YAML.")
                return

            st.session_state.smg_generated_yaml = generated_yaml
            st.session_state.smg_generated_model_name = model_name.strip()
            st.session_state.smg_analysis = ctx.get("analysis", "")
            st.session_state.smg_plan = ctx.get("plan")
            st.session_state.smg_saved_path = ""

            st.success("Semantic model generated.")

        except Exception as e:
            st.error(f"Error: {e}")
            return

    if st.session_state.smg_generated_yaml:
        with st.expander("Technical Details", expanded=False):
            if st.session_state.smg_analysis:
                st.subheader("Analysis")
                st.write(st.session_state.smg_analysis)

            if st.session_state.smg_plan:
                st.subheader("Plan")
                st.json(st.session_state.smg_plan)

        st.subheader("Generated Semantic Model")
        st.code(st.session_state.smg_generated_yaml, language="yaml")

        st.caption(f"Save location: {generated_semantic_models_dir}")

        if st.button("Save Semantic Model"):
            try:
                saved_path = save_generated_semantic_model(
                    generated_semantic_models_dir,
                    st.session_state.smg_generated_model_name,
                    st.session_state.smg_generated_yaml,
                )
                st.session_state.smg_saved_path = saved_path
                st.success(f"Saved semantic model to: {saved_path}")
            except Exception as e:
                st.error(f"Save failed: {e}")

    if st.session_state.smg_saved_path:
        st.info(f"Last saved file: {st.session_state.smg_saved_path}")