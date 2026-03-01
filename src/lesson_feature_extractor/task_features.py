"""任务复杂度特征提取。"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Dict

from .constants import TASK_FEATURE_COLUMNS
from .utils import load_jsonl, parse_task_id


def count_prompt_words(prompt: str) -> int:
    """统计 prompt 的单词数。"""
    return len(re.findall(r"\S+", prompt))


def count_loc(source_code: str) -> int:
    """统计代码非空行数。"""
    return sum(1 for line in source_code.splitlines() if line.strip())


def count_ast_nodes(source_code: str) -> int:
    """统计 AST 节点数。"""
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return 0
    return sum(1 for _ in ast.walk(tree))


def build_task_feature_map(humaneval_jsonl_path: Path, encoding: str) -> Dict[int, Dict[str, Any]]:
    """构建 task_id 到任务复杂度特征的映射。"""
    rows = load_jsonl(humaneval_jsonl_path, encoding)
    task_feature_map: Dict[int, Dict[str, Any]] = {}
    for row in rows:
        task_id: int = parse_task_id(row["task_id"])
        prompt: str = str(row.get("prompt", ""))
        canonical_solution: str = str(row.get("canonical_solution", ""))
        full_correct_code: str = prompt + canonical_solution
        task_feature_map[task_id] = {
            TASK_FEATURE_COLUMNS[0]: count_prompt_words(prompt),
            TASK_FEATURE_COLUMNS[1]: count_loc(canonical_solution),
            TASK_FEATURE_COLUMNS[2]: count_ast_nodes(full_correct_code),
        }
    return task_feature_map

