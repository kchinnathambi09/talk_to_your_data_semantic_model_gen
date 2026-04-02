from typing import Any, Dict

from core.bigquery_exec import run_query
from core.skill_runtime import load_skill


class SkillsOrchestrator:
    def __init__(self, skills_dir: str = "skills/talk_to_data"):
        self.skills_dir = skills_dir

    def plan_and_generate_sql(
        self,
        question: str,
        semantic_raw: dict,
        model: str,
    ) -> Dict[str, Any]:
        ctx: Dict[str, Any] = {
            "question": question,
            "semantic": semantic_raw,
            "model": model,
        }

        ctx.update(load_skill(self.skills_dir, "planner").run(ctx))
        ctx.update(load_skill(self.skills_dir, "sql_generator").run(ctx))
        return ctx

    def validate_sql(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        load_skill(self.skills_dir, "sql_validator").run(ctx)
        return ctx

    def repair_sql(self, ctx: Dict[str, Any], error_message: str) -> Dict[str, Any]:
        ctx["sql_error"] = error_message
        ctx.update(load_skill(self.skills_dir, "sql_repair").run(ctx))
        return ctx

    def execute_and_narrate(
        self,
        ctx: Dict[str, Any],
        project_id: str | None = None,
    ) -> Dict[str, Any]:
        ctx["df"] = run_query(ctx["sql"], project_id=project_id)
        ctx.update(load_skill(self.skills_dir, "narrator").run(ctx))
        return ctx

    def run_pipeline(
        self,
        question: str,
        semantic_raw: dict,
        model: str,
        project_id: str | None = None,
    ) -> Dict[str, Any]:
        ctx = self.plan_and_generate_sql(question, semantic_raw, model)

        try:
            self.validate_sql(ctx)
            self.execute_and_narrate(ctx, project_id=project_id)
            return ctx
        except Exception as first_error:
            ctx = self.repair_sql(ctx, str(first_error))
            self.validate_sql(ctx)
            self.execute_and_narrate(ctx, project_id=project_id)
            return ctx