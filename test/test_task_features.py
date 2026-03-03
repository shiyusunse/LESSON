"""Unit tests and manual audit tool for task_features."""

from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
SRC_DIR: Path = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lesson_feature_extractor.constants import MODEL_TO_FILES, TASK_FEATURE_COLUMNS
from lesson_feature_extractor.task_features import (
    GROUND_TRUTH_COLUMN,
    build_task_feature_map,
    count_ast_nodes,
    count_loc,
    count_prompt_tokens_with_vectorizer,
    count_prompt_words,
    strip_prompt_test_examples,
)
from lesson_feature_extractor.utils import load_csv, load_jsonl, parse_task_id, sanitize_model_name


def _write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    """Write JSONL rows for test fixtures."""
    content: str = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    path.write_text(content, encoding="utf-8")


def _write_error_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    """Write minimal error CSV fixtures."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["Error ID", "Model", "Task ID", GROUND_TRUTH_COLUMN]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _resolve_model_name(user_model: str) -> str:
    """Normalize user model name to project model key."""
    model_input = user_model.strip()
    if model_input in MODEL_TO_FILES:
        return model_input

    normalized_input = sanitize_model_name(model_input)
    for model_name in MODEL_TO_FILES:
        if model_name.lower() == model_input.lower():
            return model_name
        if sanitize_model_name(model_name) == normalized_input:
            return model_name

    supported = ", ".join(MODEL_TO_FILES.keys())
    raise ValueError(f"Unsupported model '{user_model}'. Supported models: {supported}")


def _find_error_row(error_rows: List[Dict[str, str]], error_id: str) -> Dict[str, str]:
    """Find one error row by error_id."""
    target_error_id = str(error_id).strip()
    for row in error_rows:
        if str(row.get("Error ID", "")).strip() == target_error_id:
            return row
    raise ValueError(f"Error ID '{error_id}' not found in selected model error CSV.")


def _find_humaneval_row(humaneval_rows: List[Dict[str, Any]], task_id: int) -> Dict[str, Any]:
    """Find one HumanEval row by task_id."""
    for row in humaneval_rows:
        if parse_task_id(row.get("task_id", "")) == task_id:
            return row
    raise ValueError(f"Task ID '{task_id}' not found in HumanEval JSONL.")


def _non_empty_line_numbers(text: str) -> List[int]:
    """Return 1-based line numbers of non-empty lines."""
    return [index + 1 for index, line in enumerate(text.splitlines()) if line.strip()]


def build_task_complexity_audit(
    model: str,
    error_id: str,
    defects_data_dir: Path,
    humaneval_jsonl_path: Path,
    encoding: str,
) -> Dict[str, Any]:
    """Build manual-audit payload for three task-complexity metrics."""
    model_name = _resolve_model_name(model)
    error_csv_path = defects_data_dir / MODEL_TO_FILES[model_name]["error_csv"]
    error_rows = load_csv(error_csv_path, encoding)
    error_row = _find_error_row(error_rows, error_id)
    task_id = parse_task_id(error_row.get("Task ID", ""))
    ground_truth_code_complete = str(error_row.get(GROUND_TRUTH_COLUMN, ""))

    humaneval_rows = load_jsonl(humaneval_jsonl_path, encoding)
    humaneval_row = _find_humaneval_row(humaneval_rows, task_id)
    prompt_raw = str(humaneval_row.get("prompt", ""))
    prompt_cleaned, removed_example_lines = strip_prompt_test_examples(prompt_raw)

    prompt_raw_tokens: List[str] = re.findall(r"\S+", prompt_raw)
    prompt_cleaned_tokens: List[str] = re.findall(r"\S+", prompt_cleaned)
    prompt_len, feature_names = count_prompt_tokens_with_vectorizer(prompt_cleaned)

    prompt_non_empty_lines = _non_empty_line_numbers(prompt_raw)
    ground_truth_non_empty_lines = _non_empty_line_numbers(ground_truth_code_complete)
    loc_value = count_loc(ground_truth_code_complete) - count_loc(prompt_raw)

    try:
        ast_tree = ast.parse(ground_truth_code_complete)
        ast_nodes = list(ast.walk(ast_tree))
        ast_node_types = [type(node).__name__ for node in ast_nodes]
        ast_nodes_value = count_ast_nodes(ground_truth_code_complete)
        ast_root_type = type(ast_tree).__name__
        ast_structure_dump = ast.dump(
            ast_tree,
            annotate_fields=True,
            include_attributes=False,
            indent=2,
        )
        ast_parse_ok = True
        ast_parse_error = ""
    except SyntaxError as error:
        ast_node_types = []
        ast_nodes_value = 0
        ast_root_type = ""
        ast_structure_dump = ""
        ast_parse_ok = False
        ast_parse_error = str(error)

    return {
        "input": {
            "model": model_name,
            "error_id": str(error_id),
            "task_id": task_id,
            "error_csv_path": str(error_csv_path),
            "humaneval_jsonl_path": str(humaneval_jsonl_path),
        },
        "source_preview": {
            "prompt_raw_preview": prompt_raw[:300],
            "prompt_cleaned_preview": prompt_cleaned[:300],
            "ground_truth_code_complete_preview": ground_truth_code_complete[:300],
            "removed_example_lines_count": len(removed_example_lines),
            "ground_truth_code_complete_chars": len(ground_truth_code_complete),
        },
        TASK_FEATURE_COLUMNS[0]: {
            "metric_name": TASK_FEATURE_COLUMNS[0],
            "rule": (
                "Remove doctest examples from prompt first. "
                "Then use CountVectorizer(lowercase=False, min_df=1, token_pattern=r'\\b\\w+\\b') "
                "and return token sum."
            ),
            "vectorizer_params": {
                "lowercase": False,
                "min_df": 1,
                "token_pattern": r"\b\w+\b",
            },
            "prompt_raw_text": prompt_raw,
            "prompt_cleaned_text": prompt_cleaned,
            "removed_example_lines": removed_example_lines,
            "prompt_raw_tokens_total_regex_s_plus": len(prompt_raw_tokens),
            "prompt_cleaned_tokens_total_regex_s_plus": len(prompt_cleaned_tokens),
            "vectorizer_feature_names_count": len(feature_names),
            "vectorizer_feature_names_preview": feature_names[:30],
            "result": int(prompt_len),
        },
        TASK_FEATURE_COLUMNS[1]: {
            "metric_name": TASK_FEATURE_COLUMNS[1],
            "rule": "LOC = non-empty lines of Ground Truth Code (Complete) - non-empty lines of prompt.",
            "prompt_text": prompt_raw,
            "ground_truth_code_complete_text": ground_truth_code_complete,
            "prompt_non_empty_line_numbers": prompt_non_empty_lines,
            "ground_truth_non_empty_line_numbers": ground_truth_non_empty_lines,
            "result": loc_value,
        },
        TASK_FEATURE_COLUMNS[2]: {
            "metric_name": TASK_FEATURE_COLUMNS[2],
            "rule": "Parse AST of Ground Truth Code (Complete), then count all nodes from ast.walk.",
            "ast_parse_ok": ast_parse_ok,
            "ast_parse_error": ast_parse_error,
            "ast_root_type": ast_root_type,
            "ast_structure_dump": ast_structure_dump,
            "node_type_counts": dict(Counter(ast_node_types)),
            "result": ast_nodes_value,
        },
    }


def parse_review_args() -> argparse.Namespace:
    """Parse manual-audit CLI arguments."""
    parser = argparse.ArgumentParser(description="Manual audit for task complexity metrics.")
    parser.add_argument("--model", type=str, required=True, help="Model name, e.g. GPT-4 or codegen_16b.")
    parser.add_argument("--error-id", type=str, required=True, help="Error ID in the selected model CSV.")
    parser.add_argument(
        "--defects-data-dir",
        type=str,
        default="data/defects4codellm-main/data",
        help="Path to defects CSV directory.",
    )
    parser.add_argument(
        "--humaneval-jsonl-path",
        type=str,
        default="data/human-eval-master/data/HumanEval.jsonl/human-eval-v2-20210705.jsonl",
        help="Path to HumanEval JSONL file.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="test",
        help="Directory for saving the audit JSON output.",
    )
    parser.add_argument("--encoding", type=str, default="utf-8", help="File encoding.")
    return parser.parse_args()


def main() -> None:
    """Manual-audit entry point."""
    args = parse_review_args()
    payload = build_task_complexity_audit(
        model=args.model,
        error_id=args.error_id,
        defects_data_dir=Path(args.defects_data_dir),
        humaneval_jsonl_path=Path(args.humaneval_jsonl_path),
        encoding=args.encoding,
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_tag = sanitize_model_name(str(payload["input"]["model"]))
    error_tag = str(payload["input"]["error_id"])
    task_tag = str(payload["input"]["task_id"])
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / (
        f"task_features_audit_{model_tag}_error_{error_tag}_task_{task_tag}_{timestamp}.json"
    )
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding=args.encoding)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"[saved] {output_path}")


def test_count_prompt_words_uses_countvectorizer_sum() -> None:
    """Count should follow CountVectorizer token sum."""
    prompt: str = "  def foo(x):\n\treturn x + 1  \n\n"
    assert count_prompt_words(prompt) == 6


def test_strip_prompt_test_examples_removes_doctest_block() -> None:
    """Doctest lines and expected output lines should be removed."""
    prompt = (
        "def f(x):\n"
        "    \"\"\"desc\n"
        "    >>> f(1)\n"
        "    2\n"
        "    \"\"\"\n"
        "    pass\n"
    )
    cleaned, removed = strip_prompt_test_examples(prompt)
    assert ">>> f(1)" not in cleaned
    assert "    2" not in cleaned
    assert '    """' in cleaned
    assert len(removed) == 2


def test_strip_prompt_test_examples_keeps_text_when_no_doctest() -> None:
    """When there is no doctest, prompt should remain unchanged."""
    prompt = "def f(x):\n    \"\"\"desc only\"\"\"\n    return x\n"
    cleaned, removed = strip_prompt_test_examples(prompt)
    assert cleaned == prompt
    assert removed == []


def test_count_loc_ignores_empty_lines() -> None:
    """LOC should count only non-empty lines."""
    source_code: str = "\n\nx = 1\n\n   \nprint(x)\n"
    assert count_loc(source_code) == 2


def test_count_ast_nodes_for_valid_and_invalid_code() -> None:
    """Valid code returns node count, invalid code returns 0."""
    valid_code: str = "def inc(x):\n    return x + 1\n"
    expected_nodes: int = sum(1 for _ in ast.walk(ast.parse(valid_code)))
    assert count_ast_nodes(valid_code) == expected_nodes

    invalid_code: str = "def broken(:\n    pass\n"
    assert count_ast_nodes(invalid_code) == 0


def test_build_task_feature_map_reads_multi_model_ground_truth(tmp_path: Path) -> None:
    """Should aggregate multi-model ground truth and compute metrics correctly."""
    prompt_0 = (
        "x = 1\n"
        "\"\"\"\n"
        ">>> foo(1)\n"
        "2\n"
        "\"\"\"\n"
    )
    humaneval_rows: List[Dict[str, Any]] = [
        {"task_id": "HumanEval/0", "prompt": prompt_0, "canonical_solution": " + 2\n"},
        {"task_id": "HumanEval/1", "prompt": "def f(x):\n    return x\n", "canonical_solution": "    return x + 1\n"},
    ]
    humaneval_jsonl_path = tmp_path / "humaneval.jsonl"
    _write_jsonl(humaneval_jsonl_path, humaneval_rows)

    defects_dir = tmp_path / "defects"
    gt_task_0 = "x = 1 + 2\n"
    gt_task_1 = "def f(x):\n    return x + 1\n"
    codegen_rows = [
        {"Error ID": "1", "Model": "CodeGen-16B", "Task ID": "0", GROUND_TRUTH_COLUMN: gt_task_0},
        {"Error ID": "2", "Model": "CodeGen-16B", "Task ID": "1", GROUND_TRUTH_COLUMN: gt_task_1},
    ]
    gpt4_rows = [
        {"Error ID": "3", "Model": "GPT-4", "Task ID": "0", GROUND_TRUTH_COLUMN: gt_task_0},
        {"Error ID": "4", "Model": "GPT-4", "Task ID": "1", GROUND_TRUTH_COLUMN: gt_task_1},
    ]
    _write_error_csv(defects_dir / MODEL_TO_FILES["CodeGen-16B"]["error_csv"], codegen_rows)
    _write_error_csv(defects_dir / MODEL_TO_FILES["GPT-4"]["error_csv"], gpt4_rows)

    feature_map = build_task_feature_map(
        humaneval_jsonl_path=humaneval_jsonl_path,
        defects_data_dir=defects_dir,
        models=["CodeGen-16B", "GPT-4"],
        encoding="utf-8",
    )
    assert set(feature_map.keys()) == {0, 1}

    cleaned_prompt_0, _ = strip_prompt_test_examples(prompt_0)
    assert feature_map[0][TASK_FEATURE_COLUMNS[0]] == count_prompt_words(cleaned_prompt_0)
    assert feature_map[0][TASK_FEATURE_COLUMNS[1]] == count_loc(gt_task_0) - count_loc(prompt_0)
    assert feature_map[0][TASK_FEATURE_COLUMNS[2]] == count_ast_nodes(gt_task_0)

    prompt_1 = humaneval_rows[1]["prompt"]
    assert feature_map[1][TASK_FEATURE_COLUMNS[0]] == count_prompt_words(prompt_1)
    assert feature_map[1][TASK_FEATURE_COLUMNS[1]] == count_loc(gt_task_1) - count_loc(prompt_1)
    assert feature_map[1][TASK_FEATURE_COLUMNS[2]] == count_ast_nodes(gt_task_1)


def test_build_task_complexity_audit_contains_ast_structure(tmp_path: Path) -> None:
    """Manual audit payload should include AST structure dump for review."""
    humaneval_rows: List[Dict[str, Any]] = [
        {"task_id": "HumanEval/0", "prompt": "def f(x):\n    return x\n", "canonical_solution": "    return x + 1\n"},
    ]
    humaneval_jsonl_path = tmp_path / "humaneval.jsonl"
    _write_jsonl(humaneval_jsonl_path, humaneval_rows)

    defects_dir = tmp_path / "defects"
    _write_error_csv(
        defects_dir / MODEL_TO_FILES["CodeGen-16B"]["error_csv"],
        [{"Error ID": "1", "Model": "CodeGen-16B", "Task ID": "0", GROUND_TRUTH_COLUMN: "def f(x):\n    return x + 1\n"}],
    )

    payload = build_task_complexity_audit(
        model="CodeGen-16B",
        error_id="1",
        defects_data_dir=defects_dir,
        humaneval_jsonl_path=humaneval_jsonl_path,
        encoding="utf-8",
    )
    ast_payload = payload[TASK_FEATURE_COLUMNS[2]]
    assert ast_payload["ast_parse_ok"] is True
    assert ast_payload["ast_root_type"] == "Module"
    assert "FunctionDef" in ast_payload["ast_structure_dump"]
    assert ast_payload["ast_structure_dump"]


def test_build_task_feature_map_raises_when_ground_truth_conflicts(tmp_path: Path) -> None:
    """Should fail when same task_id has conflicting ground truth."""
    humaneval_rows: List[Dict[str, Any]] = [
        {"task_id": "HumanEval/0", "prompt": "x = 1\n", "canonical_solution": "x = 2\n"},
    ]
    humaneval_jsonl_path = tmp_path / "humaneval.jsonl"
    _write_jsonl(humaneval_jsonl_path, humaneval_rows)

    defects_dir = tmp_path / "defects"
    _write_error_csv(
        defects_dir / MODEL_TO_FILES["CodeGen-16B"]["error_csv"],
        [{"Error ID": "1", "Model": "CodeGen-16B", "Task ID": "0", GROUND_TRUTH_COLUMN: "x = 1\n"}],
    )
    _write_error_csv(
        defects_dir / MODEL_TO_FILES["GPT-4"]["error_csv"],
        [{"Error ID": "2", "Model": "GPT-4", "Task ID": "0", GROUND_TRUTH_COLUMN: "x = 2\n"}],
    )

    try:
        build_task_feature_map(
            humaneval_jsonl_path=humaneval_jsonl_path,
            defects_data_dir=defects_dir,
            models=["CodeGen-16B", "GPT-4"],
            encoding="utf-8",
        )
    except ValueError as error:
        assert "Inconsistent Ground Truth Code (Complete)" in str(error)
    else:
        raise AssertionError("Expected ValueError for conflicting ground truth, but no exception was raised.")


def test_build_task_feature_map_raises_when_ground_truth_missing(tmp_path: Path) -> None:
    """Should fail when HumanEval task has no matched ground truth."""
    humaneval_rows: List[Dict[str, Any]] = [
        {"task_id": "HumanEval/0", "prompt": "x = 1\n", "canonical_solution": "x = 2\n"},
    ]
    humaneval_jsonl_path = tmp_path / "humaneval.jsonl"
    _write_jsonl(humaneval_jsonl_path, humaneval_rows)

    defects_dir = tmp_path / "defects"
    _write_error_csv(
        defects_dir / MODEL_TO_FILES["CodeGen-16B"]["error_csv"],
        [{"Error ID": "1", "Model": "CodeGen-16B", "Task ID": "1", GROUND_TRUTH_COLUMN: "x = 1\n"}],
    )

    try:
        build_task_feature_map(
            humaneval_jsonl_path=humaneval_jsonl_path,
            defects_data_dir=defects_dir,
            models=["CodeGen-16B"],
            encoding="utf-8",
        )
    except ValueError as error:
        assert "Ground Truth Code (Complete) missing" in str(error)
    else:
        raise AssertionError("Expected ValueError for missing ground truth, but no exception was raised.")


if __name__ == "__main__":
    main()
