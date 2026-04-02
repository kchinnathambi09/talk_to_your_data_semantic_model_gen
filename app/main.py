import os
import sys
from pathlib import Path

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

import pandas as pd
import streamlit as st

from semantic_model_generator_tab import (
    generate_semantic_model_for_selected_table,
    render_semantic_model_generator_tab,
)
from core.bigquery_exec import list_datasets, list_tables
from core.charting import render_chart
from core.config import apply_config_to_env, load_config
from core.guardrails import SQLValidationError
from core.orchestrator import SkillsOrchestrator
from core.semantic_loader import (
    find_semantic_model_for_table,
    list_semantic_model_files,
    load_semantic_model,
)
from core.semantic_model_builder import save_generated_semantic_model


def normalize_dataset_name(dataset_value: str) -> str:
    if not dataset_value:
        return dataset_value
    parts = dataset_value.split(".")
    return parts[-1].strip()


cfg = load_config("config/config.yaml")
apply_config_to_env(cfg)

project_id = cfg.raw.get("gcp", {}).get("project_id") or os.environ.get("GOOGLE_CLOUD_PROJECT")
default_dataset = normalize_dataset_name(
    os.environ.get("BQ_DEFAULT_DATASET", cfg.raw.get("bigquery", {}).get("dataset", ""))
)
semantic_models_dir = cfg.raw.get("app", {}).get("semantic_models_dir", "semantic_models")
generated_semantic_models_dir = cfg.raw.get("app", {}).get("generated_semantic_models_dir", "semantic_models/generated")
default_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
smg_skills_dir = cfg.raw.get("agents", {}).get("semantic_model_generator", {}).get(
    "skills_dir", "skills/semantic_model_generator"
)

st.set_page_config(page_title="Talk to the Data", layout="wide")
st.title("📊 Talk to the Data")

talk_to_data_tab, semantic_model_generator_tab = st.tabs(
    ["Talk to Data", "Semantic Model Generator"]
)

with talk_to_data_tab:
    if "app_initialized" not in st.session_state:
        st.session_state.app_initialized = True
        st.session_state.chat_history = []

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if "inline_smg_yaml" not in st.session_state:
        st.session_state.inline_smg_yaml = ""
    if "inline_smg_model_name" not in st.session_state:
        st.session_state.inline_smg_model_name = ""
    if "inline_smg_analysis" not in st.session_state:
        st.session_state.inline_smg_analysis = ""
    if "inline_smg_plan" not in st.session_state:
        st.session_state.inline_smg_plan = None
    if "inline_smg_saved_path" not in st.session_state:
        st.session_state.inline_smg_saved_path = ""

    def render_technical_details(plan, sql):
        with st.expander("View Technical Details", expanded=False):
            tab1, tab2 = st.tabs(["Planning", "Generated SQL"])

            with tab1:
                if plan is not None:
                    st.json(plan)
                else:
                    st.info("No planning details available.")

            with tab2:
                if sql:
                    st.code(sql, language="sql")
                else:
                    st.info("No SQL generated.")

    with st.sidebar:
        st.header("Selections")

        try:
            available_datasets = list_datasets(project_id=project_id)
        except Exception:
            available_datasets = [default_dataset] if default_dataset else []

        available_datasets = [normalize_dataset_name(ds) for ds in available_datasets]
        available_datasets = sorted(set(available_datasets))

        if default_dataset and default_dataset not in available_datasets:
            available_datasets = [default_dataset] + available_datasets

        selected_dataset = st.selectbox(
            "Dataset",
            options=available_datasets or [default_dataset or ""],
            index=(available_datasets.index(default_dataset) if default_dataset in available_datasets else 0),
        )

        try:
            available_tables = list_tables(selected_dataset, project_id=project_id) if selected_dataset else []
        except Exception:
            available_tables = []

        selected_table = st.selectbox(
            "Table",
            options=available_tables or [""],
            index=0,
            help="Tables refresh based on the selected dataset.",
        )

        _semantic_model_files = list_semantic_model_files(semantic_models_dir)
        matched_semantic_model = find_semantic_model_for_table(semantic_models_dir, selected_table)

        if matched_semantic_model:
            selected_semantic_model = st.selectbox(
                "Semantic model",
                options=[matched_semantic_model],
                index=0,
                disabled=True,
                help="Auto-selected from the local semantic_models folder using the selected table name.",
            )
            st.caption(f"Matched semantic model: {Path(matched_semantic_model).name}")
        else:
            selected_semantic_model = ""
            st.selectbox(
                "Semantic model",
                options=["No matching semantic model found"],
                index=0,
                disabled=True,
            )
            if selected_table:
                st.warning("No semantic model found for this table.")

    if selected_table and not selected_semantic_model:
        st.info("No semantic model found. Want to generate the semantic model using Model Generator?")

        col1, col2 = st.columns(2)
        with col1:
            generate_now = st.button("Yes, Generate Semantic Model")
        with col2:
            st.button("No")

        if generate_now:
            try:
                ctx = generate_semantic_model_for_selected_table(
                    project_id=project_id,
                    dataset_name=selected_dataset,
                    table_name=selected_table,
                    llm_model=default_model,
                    skills_dir=smg_skills_dir,
                )

                generated_yaml = ctx.get("semantic_yaml", "")
                if not generated_yaml:
                    st.error("Semantic model generation returned no YAML.")
                else:
                    st.session_state.inline_smg_yaml = generated_yaml
                    st.session_state.inline_smg_model_name = selected_table
                    st.session_state.inline_smg_analysis = ctx.get("analysis", "")
                    st.session_state.inline_smg_plan = ctx.get("plan")
                    st.session_state.inline_smg_saved_path = ""
                    st.success("Semantic model generated.")
            except Exception as e:
                st.error(f"Generation failed: {e}")

    if st.session_state.inline_smg_yaml and selected_table and not selected_semantic_model:
        with st.expander("Generated Semantic Model", expanded=True):
            if st.session_state.inline_smg_analysis:
                with st.expander("Technical Details", expanded=False):
                    st.subheader("Analysis")
                    st.write(st.session_state.inline_smg_analysis)
                    if st.session_state.inline_smg_plan:
                        st.subheader("Plan")
                        st.json(st.session_state.inline_smg_plan)

            st.code(st.session_state.inline_smg_yaml, language="yaml")

            if st.button("Save Semantic Model for Selected Table"):
                try:
                    saved_path = save_generated_semantic_model(
                        generated_semantic_models_dir,
                        st.session_state.inline_smg_model_name,
                        st.session_state.inline_smg_yaml,
                    )
                    st.session_state.inline_smg_saved_path = saved_path
                    st.success(f"Saved semantic model to: {saved_path}")
                except Exception as e:
                    st.error(f"Save failed: {e}")

        if st.session_state.inline_smg_saved_path:
            st.info("Semantic model saved. Move or copy it into the main semantic_models folder if you want Talk to Data to pick it up immediately.")

    for item in st.session_state.chat_history:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])

            if item["role"] == "assistant" and (item.get("plan") is not None or item.get("sql")):
                render_technical_details(item.get("plan"), item.get("sql"))

            if isinstance(item.get("df"), pd.DataFrame):
                st.subheader("Results")
                st.dataframe(item["df"], use_container_width=True)
                render_chart(item["df"], question=item.get("question", ""))

            if item.get("insights"):
                st.subheader("Insights")
                st.markdown(item["insights"])

    prompt = st.chat_input("Ask a question about the selected table")

    if prompt:
        st.session_state.chat_history.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        if not selected_dataset or not selected_table:
            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": "Please select a dataset and table first.",
                    "question": prompt,
                }
            )
            st.rerun()

        if not selected_semantic_model:
            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": (
                        f"No matching semantic model found for the selected table '{selected_table}'. "
                        f"Generate one using the Model Generator section above."
                    ),
                    "question": prompt,
                }
            )
            st.rerun()

        orchestrator = SkillsOrchestrator(skills_dir="skills/talk_to_data")
        plan = None
        sql = ""

        try:
            semantic = load_semantic_model(selected_semantic_model).raw

            ctx = orchestrator.plan_and_generate_sql(
                prompt,
                semantic,
                model=default_model,
            )

            plan = ctx.get("plan")
            sql = ctx.get("sql", "")

            try:
                orchestrator.validate_sql(ctx)
                ctx = orchestrator.execute_and_narrate(ctx, project_id=project_id)
            except Exception as first_error:
                ctx = orchestrator.repair_sql(ctx, str(first_error))
                plan = ctx.get("plan", plan)
                sql = ctx.get("sql", sql)
                orchestrator.validate_sql(ctx)
                ctx = orchestrator.execute_and_narrate(ctx, project_id=project_id)

            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": "Here’s what I found.",
                    "question": prompt,
                    "plan": ctx.get("plan", {}),
                    "sql": ctx.get("sql", ""),
                    "df": ctx.get("df"),
                    "insights": ctx.get("insights", ""),
                }
            )
            st.rerun()

        except SQLValidationError as e:
            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": f"SQL validation failed: {e}",
                    "question": prompt,
                    "plan": plan,
                    "sql": sql,
                    "df": None,
                    "insights": "",
                }
            )
            st.rerun()

        except Exception as e:
            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": f"Error: {e}",
                    "question": prompt,
                    "plan": plan,
                    "sql": sql,
                    "df": None,
                    "insights": "",
                }
            )
            st.rerun()

with semantic_model_generator_tab:
    render_semantic_model_generator_tab()