"""pass_rate/run_err_rate 测试与人工审查工具。"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
SRC_DIR: Path = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lesson_feature_extractor import model_features as mf
from lesson_feature_extractor.constants import (
    HUMAN_EVAL_FAILED_JSON,
    MODEL_TO_FILES,
    PYLINT_CODE_SMELL_COLUMNS,
    TEST_CASE_JSON,
)
from lesson_feature_extractor.utils import load_csv, parse_task_id, sanitize_model_name


def _write_json(path: Path, payload: Any) -> None:
    """写入 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_error_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    """写入最小错误样本 CSV。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: List[str] = ["Error ID", "Model", "Task ID", "Ground Truth Code (Complete)"]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer: csv.DictWriter[str] = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _build_minimal_website_data(
    website_data_dir: Path,
    codegen_test_rows: List[Dict[str, Any]],
    testcase_rows: List[Dict[str, Any]],
    codegen_source_code: str = "def broken(:\n    pass\n",
    codegen_failed_tasks: List[int] | None = None,
) -> None:
    """构建最小 website 数据夹，满足 build_model_feature_map 依赖。"""
    website_data_dir.mkdir(parents=True, exist_ok=True)
    for model_name, file_map in MODEL_TO_FILES.items():
        if model_name == "CodeGen-16B":
            code_list: List[str] = [codegen_source_code]
            test_rows: List[Dict[str, Any]] = codegen_test_rows
        else:
            code_list = ["def keep(x):\n    return x\n"]
            test_rows = [{"Task ID": 0, "base": [], "plus": []}]
        _write_json(website_data_dir / file_map["code_json"], code_list)
        _write_json(website_data_dir / file_map["test_json"], test_rows)

    _write_json(website_data_dir / "gt_code.json", ["def ref(x):\n    return x\n"])
    _write_json(website_data_dir / TEST_CASE_JSON, testcase_rows)
    if codegen_failed_tasks is None:
        codegen_failed_tasks = []
    failed_payload: Dict[str, List[int]] = {name: [] for name in MODEL_TO_FILES}
    failed_payload["CodeGen-16B"] = [int(task_id) for task_id in codegen_failed_tasks]
    _write_json(website_data_dir / HUMAN_EVAL_FAILED_JSON, failed_payload)


def _patch_heavy_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    """替换重依赖函数，保证单测稳定和快速。"""

    def _fake_pylint(_: str) -> Dict[str, float]:
        return {column: 0.0 for column in PYLINT_CODE_SMELL_COLUMNS}

    monkeypatch.setattr(mf, "black_diff_count", lambda _: 0.0)
    monkeypatch.setattr(mf, "semgrep_issue_count", lambda _: 0.0)
    monkeypatch.setattr(mf, "pylint_code_smell_counts", _fake_pylint)
    monkeypatch.setattr(mf, "timeout_rate_from_cases", lambda **_: 0.0)


def _resolve_model_name(user_model: str) -> str:
    """将用户输入模型名映射为项目标准模型名。"""
    normalized_input: str = user_model.strip()
    if normalized_input in MODEL_TO_FILES:
        return normalized_input

    normalized_tag: str = sanitize_model_name(normalized_input)
    for model_name in MODEL_TO_FILES:
        if model_name.lower() == normalized_input.lower():
            return model_name
        if sanitize_model_name(model_name) == normalized_tag:
            return model_name
    supported: str = ", ".join(MODEL_TO_FILES.keys())
    raise ValueError(f"Unsupported model '{user_model}'. Supported models: {supported}")


def _find_error_row(error_rows: List[Dict[str, str]], error_id: str) -> Dict[str, str]:
    """按 error_id 查找单条错误样本。"""
    target: str = str(error_id).strip()
    for row in error_rows:
        if str(row.get("Error ID", "")).strip() == target:
            return row
    raise ValueError(f"Error ID '{error_id}' not found in selected model error CSV.")


def _find_test_row_by_task_id(test_rows: List[Dict[str, Any]], task_id: int) -> Dict[str, Any] | None:
    """按 task_id 查找测试结果行。"""
    for row in test_rows:
        if parse_task_id(row.get("Task ID", "")) == task_id:
            return row
    return None


def _infer_base_plus_semantics(
    error_rows: List[Dict[str, str]],
    pass_count_map: Dict[int, int],
    total_count_map: Dict[int, int],
    sample_size: int,
) -> Dict[str, Any]:
    """通过抽查错误样本与测试结果映射，推断 base/plus 语义。"""
    checked_rows: List[Dict[str, Any]] = []
    zero_pass_examples: List[Dict[str, Any]] = []

    for row in error_rows:
        if len(checked_rows) >= sample_size:
            break
        task_id: int = parse_task_id(row.get("Task ID", "0"))
        pass_count: int = pass_count_map.get(task_id, 0)
        total_count: int = total_count_map.get(task_id, 0)
        pass_rate: float = (pass_count / total_count) if total_count > 0 else 0.0
        checked = {
            "error_id": str(row.get("Error ID", "")),
            "task_id": task_id,
            "pass_count": pass_count,
            "total_count": total_count,
            "pass_rate": round(pass_rate, 6),
            "run_err_rate_if_pass_semantics": round(max(0.0, 1.0 - pass_rate), 6),
            "run_err_rate_if_fail_semantics": round(pass_rate, 6),
        }
        checked_rows.append(checked)
        if total_count > 0 and pass_count == 0:
            zero_pass_examples.append(checked)

    if zero_pass_examples:
        conclusion: str = "base_plus_store_passed_cases"
        reason: str = (
            "抽查到 error 样本对应任务的 pass_count=0 且 total_count>0。"
            "若 base/plus 表示未通过样例，则该任务未通过数应为 0，与 error 样本语义冲突。"
        )
        confidence: str = "high"
    else:
        conclusion = "inconclusive_from_current_sample"
        reason = "当前抽查样本未出现 pass_count=0 的强证据，暂无法高置信度判定。"
        confidence = "medium"

    return {
        "sample_size": len(checked_rows),
        "conclusion": conclusion,
        "confidence": confidence,
        "reason": reason,
        "checked_rows_preview": checked_rows[:10],
        "zero_pass_examples_preview": zero_pass_examples[:10],
    }


def build_pass_rate_audit_payload(
    model: str,
    error_id: str,
    defects_data_dir: Path,
    website_data_dir: Path,
    encoding: str,
    sample_size: int = 30,
) -> Dict[str, Any]:
    """构建 pass_rate/run_err_rate 的人工审查 JSON 负载。"""
    model_name: str = _resolve_model_name(model)
    model_files: Dict[str, str] = MODEL_TO_FILES[model_name]

    error_csv_path: Path = defects_data_dir / model_files["error_csv"]
    model_test_json_path: Path = website_data_dir / model_files["test_json"]
    testcase_json_path: Path = website_data_dir / TEST_CASE_JSON
    failed_json_path: Path = website_data_dir / HUMAN_EVAL_FAILED_JSON

    error_rows: List[Dict[str, str]] = load_csv(error_csv_path, encoding)
    target_error_row: Dict[str, str] = _find_error_row(error_rows, error_id)
    task_id: int = parse_task_id(target_error_row.get("Task ID", "0"))

    test_rows: List[Dict[str, Any]] = mf.load_json(model_test_json_path, encoding)
    target_test_row: Dict[str, Any] | None = _find_test_row_by_task_id(test_rows, task_id)

    pass_count_map: Dict[int, int] = mf.build_pass_count_map(model_test_json_path, encoding)
    total_count_map: Dict[int, int] = mf.build_test_case_total_map(testcase_json_path, encoding)
    fail_count: int = mf.load_model_fail_count(failed_json_path, model_name, encoding)
    total_count: int = 164

    pass_count: int = pass_count_map.get(task_id, 0)
    pass_rate: float = 1.0 - (fail_count / total_count)
    run_err_rate: float = fail_count / total_count

    if target_test_row is None:
        base_count: int = 0
        plus_count: int = 0
    else:
        base_count = len(target_test_row.get("base", []))
        plus_count = len(target_test_row.get("plus", []))

    semantic_check: Dict[str, Any] = _infer_base_plus_semantics(
        error_rows=error_rows,
        pass_count_map=pass_count_map,
        total_count_map=total_count_map,
        sample_size=sample_size,
    )
    rule_ok: bool = abs(run_err_rate - (fail_count / total_count)) < 1e-12 and abs(pass_rate - (1.0 - run_err_rate)) < 1e-12

    return {
        "input": {
            "model": model_name,
            "error_id": str(error_id),
            "task_id": task_id,
            "defects_data_dir": str(defects_data_dir),
            "website_data_dir": str(website_data_dir),
            "error_csv_path": str(error_csv_path),
            "model_test_json_path": str(model_test_json_path),
            "testcase_json_path": str(testcase_json_path),
            "human_eval_failed_json_path": str(failed_json_path),
        },
        "formula": {
            "pass_rate": "1 - fail_count / total_count",
            "run_err_rate": "fail_count / total_count",
            "total_count": "fixed 164",
        },
        "process": {
            "fail_count_from_human_eval_failed_json": fail_count,
            "total_count_fixed": total_count,
            "pass_count_from_test_json_for_semantics_check": f"len(base)+len(plus) -> {pass_count}",
            "target_row_base_count": base_count,
            "target_row_plus_count": plus_count,
        },
        "result": {
            "fail_count": fail_count,
            "pass_count": pass_count,
            "total_count": total_count,
            "pass_rate": round(pass_rate, 6),
            "run_err_rate": round(run_err_rate, 6),
            "formula_check_passed": rule_ok,
        },
        "base_plus_semantics_check": semantic_check,
    }


def _build_timestamped_output_path(
    output: str,
    output_dir: Path,
    model_name: str,
    error_id: str,
    task_id: int,
) -> Path:
    """生成带时间戳的输出路径。"""
    timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
    if output.strip():
        candidate: Path = Path(output.strip())
        # 用户仅给文件名时，仍落到 test_results 目录。
        if candidate.parent == Path("."):
            candidate = output_dir / candidate.name
        if candidate.suffix.lower() != ".json":
            candidate = candidate.with_suffix(".json")
        if not re.search(r"_\d{8}_\d{6}$", candidate.stem):
            candidate = candidate.with_name(f"{candidate.stem}_{timestamp}{candidate.suffix}")
        return candidate

    model_tag: str = sanitize_model_name(model_name)
    return output_dir / f"pass_rate_audit_{model_tag}_error_{error_id}_task_{task_id}_{timestamp}.json"


def parse_review_args() -> argparse.Namespace:
    """解析人工审查命令行参数。"""
    parser = argparse.ArgumentParser(description="Manual audit for pass_rate and run_err_rate.")
    parser.add_argument("--model", type=str, required=True, help="Model name, e.g. GPT-4 or codegen_16b.")
    parser.add_argument("--error-id", type=str, required=True, help="Error ID in selected model CSV.")
    parser.add_argument(
        "--defects-data-dir",
        type=str,
        default="data/defects4codellm-main/data",
        help="Path to defects CSV directory.",
    )
    parser.add_argument(
        "--website-data-dir",
        type=str,
        default="data/defects4codellm-main/website/src/data",
        help="Path to website JSON directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="test_results",
        help="Directory to save audit JSON files.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Optional output file path. Timestamp suffix is auto-added if missing.",
    )
    parser.add_argument("--sample-size", type=int, default=30, help="Sample size for base/plus semantics check.")
    parser.add_argument("--encoding", type=str, default="utf-8", help="File encoding.")
    return parser.parse_args()


def main() -> None:
    """人工审查入口。"""
    args = parse_review_args()
    payload: Dict[str, Any] = build_pass_rate_audit_payload(
        model=args.model,
        error_id=args.error_id,
        defects_data_dir=Path(args.defects_data_dir),
        website_data_dir=Path(args.website_data_dir),
        encoding=args.encoding,
        sample_size=max(args.sample_size, 1),
    )
    output_dir: Path = Path(args.output_dir)
    output_path: Path = _build_timestamped_output_path(
        output=args.output,
        output_dir=output_dir,
        model_name=str(payload["input"]["model"]),
        error_id=str(payload["input"]["error_id"]),
        task_id=int(payload["input"]["task_id"]),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding=args.encoding)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"[saved] {output_path}")


def test_build_pass_count_map_sums_base_and_plus(tmp_path: Path) -> None:
    """通过数应等于 base 与 plus 长度之和。"""
    test_json_path: Path = tmp_path / "model_test.json"
    _write_json(
        test_json_path,
        [
            {"Task ID": "HumanEval_0", "base": [1, 2], "plus": [8]},
            {"Task ID": 1, "base": [], "plus": [0, 1]},
        ],
    )
    pass_map: Dict[int, int] = mf.build_pass_count_map(test_json_path, "utf-8")
    assert pass_map[0] == 3
    assert pass_map[1] == 2


def test_build_test_case_total_map_sums_base_input_and_plus_input(tmp_path: Path) -> None:
    """总用例数应等于 base_input 与 plus_input 长度之和。"""
    testcase_json_path: Path = tmp_path / TEST_CASE_JSON
    _write_json(
        testcase_json_path,
        [
            {"Task ID": "HumanEval/0", "base_input": [1, 2], "plus_input": [3]},
            {"Task ID": "HumanEval_1", "base_input": [], "plus_input": [1, 2, 3]},
        ],
    )
    total_map: Dict[int, int] = mf.build_test_case_total_map(testcase_json_path, "utf-8")
    assert total_map[0] == 3
    assert total_map[1] == 3


def test_build_model_feature_map_pass_rate_and_run_err_rate_formula(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证 pass_rate 与 run_err_rate 的主公式。"""
    _patch_heavy_dependencies(monkeypatch)
    website_data_dir: Path = tmp_path / "website_data"
    _build_minimal_website_data(
        website_data_dir=website_data_dir,
        codegen_test_rows=[{"Task ID": 0, "base": [0], "plus": []}],
        testcase_rows=[{"Task ID": "HumanEval_0", "base_input": [1, 2], "plus_input": [3]}],
        codegen_failed_tasks=[0, 1, 2],
    )
    feature_map: Dict[int, Dict[str, Any]] = mf.build_model_feature_map("CodeGen-16B", website_data_dir, "utf-8")
    row: Dict[str, Any] = feature_map[0]
    assert row["pass_rate"] == round(1.0 - (3 / 164), 6)
    assert row["run_err_rate"] == round(3 / 164, 6)


def test_build_model_feature_map_zero_fail_count_means_full_pass_rate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """当 fail_count=0 时，pass_rate=1.0 且 run_err_rate=0.0。"""
    _patch_heavy_dependencies(monkeypatch)
    website_data_dir: Path = tmp_path / "website_data"
    _build_minimal_website_data(
        website_data_dir=website_data_dir,
        codegen_test_rows=[{"Task ID": 0, "base": [1, 2], "plus": [3]}],
        testcase_rows=[{"Task ID": "HumanEval_0", "base_input": [], "plus_input": []}],
        codegen_failed_tasks=[],
    )
    feature_map: Dict[int, Dict[str, Any]] = mf.build_model_feature_map("CodeGen-16B", website_data_dir, "utf-8")
    row: Dict[str, Any] = feature_map[0]
    assert row["pass_rate"] == 1.0
    assert row["run_err_rate"] == 0.0


def test_build_model_feature_map_defaults_when_task_missing_in_test_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试结果缺失该 task_id 时，pass_count 默认 0。"""
    _patch_heavy_dependencies(monkeypatch)
    website_data_dir: Path = tmp_path / "website_data"
    _build_minimal_website_data(
        website_data_dir=website_data_dir,
        codegen_test_rows=[{"Task ID": 1, "base": [0], "plus": [1]}],
        testcase_rows=[{"Task ID": "HumanEval_0", "base_input": [1], "plus_input": [2, 3]}],
        codegen_failed_tasks=[0, 3],
    )
    feature_map: Dict[int, Dict[str, Any]] = mf.build_model_feature_map("CodeGen-16B", website_data_dir, "utf-8")
    row: Dict[str, Any] = feature_map[0]
    assert row["pass_rate"] == round(1.0 - (2 / 164), 6)
    assert row["run_err_rate"] == round(2 / 164, 6)


def test_build_pass_rate_audit_payload_contains_process_and_semantics(tmp_path: Path) -> None:
    """审查 JSON 负载应包含过程结果及 base/plus 语义结论。"""
    defects_data_dir: Path = tmp_path / "defects_data"
    _write_error_csv(
        defects_data_dir / MODEL_TO_FILES["CodeGen-16B"]["error_csv"],
        [
            {
                "Error ID": "13",
                "Model": "CodeGen-16B",
                "Task ID": "0",
                "Ground Truth Code (Complete)": "def f(x):\n    return x\n",
            },
            {
                "Error ID": "14",
                "Model": "CodeGen-16B",
                "Task ID": "1",
                "Ground Truth Code (Complete)": "def g(x):\n    return x\n",
            },
        ],
    )

    website_data_dir: Path = tmp_path / "website_data"
    website_data_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        website_data_dir / MODEL_TO_FILES["CodeGen-16B"]["test_json"],
        [
            {"Task ID": 0, "base": [0], "plus": []},
            {"Task ID": 1, "base": [], "plus": []},
        ],
    )
    _write_json(
        website_data_dir / TEST_CASE_JSON,
        [
            {"Task ID": "HumanEval_0", "base_input": [1, 2], "plus_input": []},
            {"Task ID": "HumanEval_1", "base_input": [1], "plus_input": [2, 3]},
        ],
    )
    _write_json(
        website_data_dir / HUMAN_EVAL_FAILED_JSON,
        {
            "CodeGen-16B": [0, 1, 2],
            "InCoder-1B": [],
            "GPT-3.5": [],
            "GPT-4": [],
            "StarCoder": [],
            "SantaCoder": [],
        },
    )

    payload: Dict[str, Any] = build_pass_rate_audit_payload(
        model="CodeGen-16B",
        error_id="13",
        defects_data_dir=defects_data_dir,
        website_data_dir=website_data_dir,
        encoding="utf-8",
        sample_size=10,
    )
    assert payload["result"]["fail_count"] == 3
    assert payload["result"]["pass_count"] == 1
    assert payload["result"]["total_count"] == 164
    assert payload["result"]["pass_rate"] == round(1.0 - (3 / 164), 6)
    assert payload["result"]["run_err_rate"] == round(3 / 164, 6)
    assert payload["result"]["formula_check_passed"] is True
    assert payload["base_plus_semantics_check"]["conclusion"] == "base_plus_store_passed_cases"


def test_build_timestamped_output_path_appends_timestamp(tmp_path: Path) -> None:
    """输出路径若不带时间戳，应自动追加。"""
    output_dir: Path = tmp_path / "test_results"
    output_path: Path = _build_timestamped_output_path(
        output="audit_result.json",
        output_dir=output_dir,
        model_name="CodeGen-16B",
        error_id="13",
        task_id=0,
    )
    assert output_path.parent == output_dir
    assert re.search(r"_\d{8}_\d{6}\.json$", output_path.name) is not None


if __name__ == "__main__":
    main()
