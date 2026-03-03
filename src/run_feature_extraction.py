"""LESSON 特征提取入口脚本。"""

from __future__ import annotations

import argparse
import datetime as dt
import platform
import sys
from pathlib import Path
from typing import Dict, List

from lesson_feature_extractor.constants import MODEL_TO_FILES
from lesson_feature_extractor.pipeline import run_feature_pipeline
from lesson_feature_extractor.task_features import build_task_feature_map
from lesson_feature_extractor.utils import ensure_directory, get_git_hash, write_simple_yaml


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="Extract features for defects4codellm-main.")
    parser.add_argument(
        "--defects-data-dir",
        type=str,
        default="data/defects4codellm-main/data",
        help="Path of defects CSV files.",
    )
    parser.add_argument(
        "--website-data-dir",
        type=str,
        default="data/defects4codellm-main/website/src/data",
        help="Path of website JSON files.",
    )
    parser.add_argument(
        "--humaneval-jsonl-path",
        type=str,
        default="data/human-eval-master/data/HumanEval.jsonl/human-eval-v2-20210705.jsonl",
        help="Path of HumanEval JSONL file.",
    )
    parser.add_argument(
        "--output-root",
        type=str,
        default="work_dirs",
        help="Root directory to save outputs.",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default="",
        help="Optional run directory name.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for logging.",
    )
    parser.add_argument(
        "--models",
        type=str,
        default=",".join(MODEL_TO_FILES.keys()),
        help="Comma-separated model names.",
    )
    parser.add_argument(
        "--encoding",
        type=str,
        default="utf-8",
        help="File encoding.",
    )
    return parser.parse_args()


def build_run_name(cli_run_name: str) -> str:
    """生成运行目录名。"""
    if cli_run_name.strip():
        return cli_run_name.strip()
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_feature_extraction"


def write_log_header(log_path: Path, args: argparse.Namespace, run_config: Dict[str, str]) -> None:
    """写入日志头信息。"""
    command = " ".join(sys.argv)
    python_version = platform.python_version()
    git_hash = get_git_hash()

    lines: List[str] = [
        f"Command: {command}",
        f"Environment: Python {python_version}",
        f"Seed: {args.seed}",
        f"Git Hash: {git_hash}",
        "Config:",
    ]
    for key, value in run_config.items():
        lines.append(f"  {key}: {value}")
    log_path.write_text("\n".join(lines) + "\n", encoding=args.encoding)


def append_log(log_path: Path, text: str, encoding: str) -> None:
    """追加日志内容。"""
    with log_path.open("a", encoding=encoding) as file:
        file.write(text.rstrip() + "\n")


def main() -> None:
    """主流程。"""
    args = parse_args()
    model_names: List[str] = [name.strip() for name in args.models.split(",") if name.strip()]
    unsupported = [name for name in model_names if name not in MODEL_TO_FILES]
    if unsupported:
        raise ValueError(f"Unsupported model names: {unsupported}")

    run_name = build_run_name(args.run_name)
    output_root = Path(args.output_root)
    run_dir = output_root / run_name
    outputs_dir = run_dir / "outputs"

    ensure_directory(run_dir)
    ensure_directory(outputs_dir)

    run_config: Dict[str, str] = {
        "defects_data_dir": args.defects_data_dir,
        "website_data_dir": args.website_data_dir,
        "humaneval_jsonl_path": args.humaneval_jsonl_path,
        "output_root": args.output_root,
        "run_name": run_name,
        "seed": str(args.seed),
        "models": ",".join(model_names),
        "encoding": args.encoding,
    }
    write_simple_yaml(run_dir / "config.yaml", run_config, args.encoding)
    log_path = run_dir / "log.txt"
    write_log_header(log_path, args, run_config)

    task_feature_map = build_task_feature_map(
        humaneval_jsonl_path=Path(args.humaneval_jsonl_path),
        defects_data_dir=Path(args.defects_data_dir),
        models=list(MODEL_TO_FILES.keys()),
        encoding=args.encoding,
    )
    summary = run_feature_pipeline(
        defects_data_dir=Path(args.defects_data_dir),
        website_data_dir=Path(args.website_data_dir),
        outputs_dir=outputs_dir,
        models=model_names,
        task_feature_map=task_feature_map,
        encoding=args.encoding,
    )

    append_log(log_path, "", args.encoding)
    append_log(log_path, "Output Summary:", args.encoding)
    for model_name, row_count in summary.items():
        append_log(log_path, f"  {model_name}: {row_count} rows", args.encoding)


if __name__ == "__main__":
    main()
