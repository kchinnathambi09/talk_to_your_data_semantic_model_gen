from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Callable
import yaml

@dataclass
class SkillMeta:
    skill_id: str
    name: str
    description: str
    inputs: list[str]
    outputs: list[str]

@dataclass
class Skill:
    meta: SkillMeta
    folder: Path
    run: Callable[[Dict[str, Any]], Dict[str, Any]]
    instructions: str

def _read_frontmatter(md_text: str) -> dict:
    if not md_text.startswith("---"):
        return {}
    end = md_text.find("\n---", 3)
    if end == -1:
        return {}
    fm = md_text[3:end]
    return yaml.safe_load(fm) or {}

def discover_skills(skills_dir: str | Path) -> Dict[str, SkillMeta]:
    skills_dir = Path(skills_dir)
    metas: Dict[str, SkillMeta] = {}
    for folder in skills_dir.iterdir():
        if not folder.is_dir():
            continue
        md = folder / "SKILL.md"
        if not md.exists():
            continue
        text = md.read_text(encoding="utf-8")
        fm = _read_frontmatter(text)
        if not fm:
            continue
        inferred_skill_id = folder.name
        metas[inferred_skill_id] = SkillMeta(
            skill_id=inferred_skill_id,
            name=fm.get("name", inferred_skill_id),
            description=fm.get("description",""),
            inputs=fm.get("inputs", []),
            outputs=fm.get("outputs", []),
        )
    return metas

def load_skill(skills_dir: str | Path, skill_id: str) -> Skill:
    skills_dir = Path(skills_dir)
    folder = skills_dir / skill_id
    md = folder / "SKILL.md"
    run_py = folder / "run.py"
    if not md.exists() or not run_py.exists():
        raise FileNotFoundError(f"Skill '{skill_id}' missing SKILL.md or run.py")

    md_text = md.read_text(encoding="utf-8")
    fm = _read_frontmatter(md_text)
    instructions = md_text.split("---", 2)[-1].strip() if md_text.startswith("---") else md_text.strip()

    import importlib.util
    spec = importlib.util.spec_from_file_location(f"skill_{skill_id}", str(run_py))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore
    if not hasattr(mod, "run"):
        raise AttributeError(f"Skill '{skill_id}' run.py must expose run(ctx)->dict")

    meta = SkillMeta(
        skill_id=skill_id,
        name=fm.get("name", skill_id),
        description=fm.get("description",""),
        inputs=fm.get("inputs", []),
        outputs=fm.get("outputs", []),
    )
    return Skill(meta=meta, folder=folder, run=mod.run, instructions=instructions)