"""Task complexity feature extraction."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from .constants import MODEL_TO_FILES, TASK_FEATURE_COLUMNS
from .utils import load_csv, load_jsonl, parse_task_id

GROUND_TRUTH_COLUMN: str = "Ground Truth Code (Complete)"


def _vectorize_token_sum(texts: Sequence[str]) -> Tuple[int, List[str]]:
    """Compute token sum and feature names using CountVectorizer."""
    try:
        from sklearn.feature_extraction.text import CountVectorizer
    except ModuleNotFoundError as error:
        raise ModuleNotFoundError(
            "scikit-learn is required for prompt token counting. "
            "Please install in LESSON env: conda run -n LESSON python -m pip install scikit-learn"
        ) from error

    if not texts or all(not str(text).strip() for text in texts):
        return 0, []

    vectorizer = CountVectorizer(
        lowercase=False,
        min_df=1,
        token_pattern=r"\b\w+\b",
    )
    try:
        matrix = vectorizer.fit_transform([str(text) for text in texts])
    except ValueError:
        return 0, []

    feature_names = [str(name) for name in vectorizer.get_feature_names_out()]
    token_sum = int(matrix.sum())
    return token_sum, feature_names


def count_prompt_tokens_with_vectorizer(prompt: str) -> Tuple[int, List[str]]:
    """Return token sum and vocabulary for one prompt."""
    return _vectorize_token_sum([prompt])


def count_prompt_words(prompt: str) -> int:
    """Count prompt tokens using CountVectorizer sum."""
    token_sum, _ = count_prompt_tokens_with_vectorizer(prompt)
    return token_sum


def count_loc(source_code: str) -> int:
    """Count non-empty lines of code."""
    return sum(1 for line in source_code.splitlines() if line.strip())


def count_ast_nodes(source_code: str) -> int:
    """Count AST nodes."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return 0
    return sum(1 for _ in ast.walk(tree))


def strip_prompt_test_examples(prompt: str) -> Tuple[str, List[str]]:
    """Remove doctest-style examples from prompt."""
    lines = prompt.splitlines()
    kept_lines: List[str] = []
    removed_lines: List[str] = []
    in_example_block = False

    for line in lines:
        stripped = line.strip()
        is_doctest_line = stripped.startswith(">>>") or stripped.startswith("...")
        is_docstring_end = stripped in {'"""', "'''"}

        if in_example_block:
            if is_docstring_end or stripped == "":
                in_example_block = False
                kept_lines.append(line)
                continue
            if is_doctest_line:
                removed_lines.append(line)
                continue
            removed_lines.append(line)
            continue

        if is_doctest_line:
            in_example_block = True
            removed_lines.append(line)
            continue

        kept_lines.append(line)

    cleaned_prompt = "\n".join(kept_lines)
    if prompt.endswith("\n"):
        cleaned_prompt += "\n"
    return cleaned_prompt, removed_lines


def _build_ground_truth_map(
    defects_data_dir: Path,
    models: Sequence[str],
    encoding: str,
) -> Dict[int, str]:
    """Aggregate multi-model ground truth and validate consistency."""
    ground_truth_map: Dict[int, str] = {}
    source_map: Dict[int, Tuple[str, int]] = {}

    for model_name in models:
        if model_name not in MODEL_TO_FILES:
            raise ValueError(f"Unsupported model for ground truth aggregation: {model_name}")
        csv_path = defects_data_dir / MODEL_TO_FILES[model_name]["error_csv"]
        if not csv_path.exists():
            raise FileNotFoundError(f"Ground truth source file not found: {csv_path}")

        rows = load_csv(csv_path, encoding)
        for row_index, row in enumerate(rows, start=2):
            task_id = parse_task_id(row.get("Task ID", ""))
            ground_truth_code = str(row.get(GROUND_TRUTH_COLUMN, ""))
            if not ground_truth_code.strip():
                raise ValueError(
                    f"Missing '{GROUND_TRUTH_COLUMN}' for task_id={task_id} "
                    f"in model={model_name}, file={csv_path}, row={row_index}"
                )

            existed = ground_truth_map.get(task_id)
            if existed is None:
                ground_truth_map[task_id] = ground_truth_code
                source_map[task_id] = (model_name, row_index)
                continue

            if existed != ground_truth_code:
                first_model, first_row = source_map[task_id]
                raise ValueError(
                    "Inconsistent Ground Truth Code (Complete) detected for "
                    f"task_id={task_id}. First source: model={first_model}, row={first_row}; "
                    f"conflict source: model={model_name}, row={row_index}."
                )

    return ground_truth_map


def build_task_feature_map(
    humaneval_jsonl_path: Path,
    defects_data_dir: Path,
    models: Sequence[str],
    encoding: str,
) -> Dict[int, Dict[str, Any]]:
    """Build mapping from task_id to task complexity features."""
    rows = load_jsonl(humaneval_jsonl_path, encoding)
    ground_truth_map = _build_ground_truth_map(defects_data_dir, models, encoding)

    task_feature_map: Dict[int, Dict[str, Any]] = {}
    for row in rows:
        task_id = parse_task_id(row["task_id"])
        prompt = str(row.get("prompt", ""))
        cleaned_prompt, _ = strip_prompt_test_examples(prompt)
        ground_truth_code = ground_truth_map.get(task_id)
        if ground_truth_code is None:
            raise ValueError(
                "Ground Truth Code (Complete) missing after multi-model aggregation for "
                f"task_id={task_id}."
            )

        task_feature_map[task_id] = {
            TASK_FEATURE_COLUMNS[0]: count_prompt_words(cleaned_prompt),
            TASK_FEATURE_COLUMNS[1]: count_loc(ground_truth_code) - count_loc(prompt),
            TASK_FEATURE_COLUMNS[2]: count_ast_nodes(ground_truth_code),
        }
    return task_feature_map
