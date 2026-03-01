"""特征提取流水线。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Sequence

from .constants import (
    MODEL_FEATURE_COLUMNS,
    MODEL_TO_FILES,
    SEMANTIC_CODE_TO_FEATURE,
    SEMANTIC_FEATURE_COLUMNS,
    SYNTACTIC_CODE_TO_FEATURE,
    SYNTACTIC_FEATURE_COLUMNS,
    TASK_FEATURE_COLUMNS,
)
from .model_features import build_model_feature_map
from .utils import load_csv, parse_label_code, parse_task_id, sanitize_model_name, write_csv


def build_one_hot_feature(
    code: str,
    code_to_feature: Dict[str, str],
    feature_columns: Sequence[str],
) -> Dict[str, int]:
    """根据错误代码构造 one-hot 特征。"""
    one_hot: Dict[str, int] = {column: 0 for column in feature_columns}
    if code in code_to_feature:
        one_hot[code_to_feature[code]] = 1
    return one_hot


def build_model_rows(
    model_name: str,
    defects_data_dir: Path,
    website_data_dir: Path,
    task_feature_map: Dict[int, Dict[str, Any]],
    encoding: str,
) -> List[Dict[str, Any]]:
    """构建单个模型的完整行数据。"""
    error_csv = defects_data_dir / MODEL_TO_FILES[model_name]["error_csv"]
    error_rows = load_csv(error_csv, encoding)
    model_feature_map = build_model_feature_map(model_name, website_data_dir, encoding)
    rows: List[Dict[str, Any]] = []

    for row in error_rows:
        task_id = parse_task_id(row.get("Task ID", "0"))
        semantic_code = parse_label_code(row.get("Semantic Characteristics", ""))
        syntactic_code = parse_label_code(row.get("Syntactic Characteristics", ""))

        task_features = task_feature_map.get(
            task_id,
            {
                TASK_FEATURE_COLUMNS[0]: 0,
                TASK_FEATURE_COLUMNS[1]: 0,
                TASK_FEATURE_COLUMNS[2]: 0,
            },
        )
        model_features = model_feature_map.get(task_id, {key: None for key in MODEL_FEATURE_COLUMNS})
        semantic_one_hot = build_one_hot_feature(
            semantic_code,
            SEMANTIC_CODE_TO_FEATURE,
            SEMANTIC_FEATURE_COLUMNS,
        )
        syntactic_one_hot = build_one_hot_feature(
            syntactic_code,
            SYNTACTIC_CODE_TO_FEATURE,
            SYNTACTIC_FEATURE_COLUMNS,
        )

        merged_row: Dict[str, Any] = {
            "Error ID": row.get("Error ID", ""),
            "Model": row.get("Model", model_name),
            "Task ID": task_id,
            "Semantic Characteristics": row.get("Semantic Characteristics", ""),
            "Syntactic Characteristics": row.get("Syntactic Characteristics", ""),
        }
        merged_row.update(task_features)
        merged_row.update(model_features)
        merged_row.update(semantic_one_hot)
        merged_row.update(syntactic_one_hot)
        rows.append(merged_row)

    return rows


def run_feature_pipeline(
    defects_data_dir: Path,
    website_data_dir: Path,
    outputs_dir: Path,
    models: Sequence[str],
    task_feature_map: Dict[int, Dict[str, Any]],
    encoding: str,
) -> Dict[str, int]:
    """执行特征提取并输出每个模型的 CSV。"""
    fieldnames: List[str] = [
        "Error ID",
        "Model",
        "Task ID",
        "Semantic Characteristics",
        "Syntactic Characteristics",
    ]
    fieldnames.extend(TASK_FEATURE_COLUMNS)
    fieldnames.extend(MODEL_FEATURE_COLUMNS)
    fieldnames.extend(SEMANTIC_FEATURE_COLUMNS)
    fieldnames.extend(SYNTACTIC_FEATURE_COLUMNS)

    result_summary: Dict[str, int] = {}
    for model_name in models:
        rows = build_model_rows(
            model_name=model_name,
            defects_data_dir=defects_data_dir,
            website_data_dir=website_data_dir,
            task_feature_map=task_feature_map,
            encoding=encoding,
        )
        output_file = outputs_dir / f"{sanitize_model_name(model_name)}_features.csv"
        write_csv(output_file, fieldnames=fieldnames, rows=rows, encoding=encoding)
        result_summary[model_name] = len(rows)
    return result_summary
