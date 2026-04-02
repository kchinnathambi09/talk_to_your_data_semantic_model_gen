import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class SemanticModel:
    raw: Dict[str, Any]


_VAR_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _expand_env_vars(text: str) -> str:
    def repl(m):
        key = m.group(1)
        return os.environ.get(key, m.group(0))
    return _VAR_PATTERN.sub(repl, text)


def load_semantic_model(path: str) -> SemanticModel:
    with open(path, "r", encoding="utf-8") as f:
        content = _expand_env_vars(f.read())
    return SemanticModel(raw=yaml.safe_load(content))


def list_semantic_model_files(folder_path: str) -> List[str]:
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        return []

    semantic_files = [
        str(path).replace('\\', '/')
        for path in sorted(folder.rglob('*'))
        if path.is_file() and path.suffix.lower() in {'.yaml', '.yml'}
    ]
    return semantic_files


def find_semantic_model_for_table(folder_path: str, table_name: str) -> Optional[str]:
    if not table_name:
        return None

    table_name = table_name.strip().lower()
    for path_str in list_semantic_model_files(folder_path):
        path = Path(path_str)
        if path.stem.strip().lower() == table_name:
            return path_str
    return None