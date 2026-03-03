"""Common utility helpers."""

from __future__ import annotations

import csv
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence


def ensure_directory(path: Path) -> None:
    """Ensure a directory exists."""
    path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, encoding: str) -> Any:
    """Load a JSON file."""
    with path.open("r", encoding=encoding) as file:
        return json.load(file)


def load_jsonl(path: Path, encoding: str) -> List[Dict[str, Any]]:
    """Load a JSONL file."""
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding=encoding) as file:
        for line in file:
            stripped: str = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def load_csv(path: Path, encoding: str) -> List[Dict[str, str]]:
    """Load a CSV file."""
    with path.open("r", encoding=encoding, newline="") as file:
        reader: csv.DictReader[str] = csv.DictReader(file)
        return [dict(row) for row in reader]


def to_csv_value(value: Any) -> Any:
    """Convert internal values to CSV-friendly values."""
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return value


def write_csv(
    path: Path,
    fieldnames: Sequence[str],
    rows: Iterable[Mapping[str, Any]],
    encoding: str,
) -> None:
    """Write rows into a CSV file."""
    with path.open("w", encoding=encoding, newline="") as file:
        writer: csv.DictWriter[str] = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            converted: Dict[str, Any] = {key: to_csv_value(row.get(key)) for key in fieldnames}
            writer.writerow(converted)


def parse_task_id(raw_value: Any) -> int:
    """Parse different task id formats into an integer."""
    if isinstance(raw_value, int):
        return raw_value
    text: str = str(raw_value).strip()
    if text.startswith("HumanEval/"):
        text = text.split("/", 1)[1]
    if text.startswith("HumanEval_"):
        text = text.split("_", 1)[1]
    return int(text)


def parse_label_code(raw_value: str) -> str:
    """Extract an error code from label text."""
    match = re.match(r"([A-Z][a-z]\d+|[A-Z]\d+)", raw_value.strip())
    if not match:
        return ""
    return match.group(1)


def sanitize_model_name(model_name: str) -> str:
    """Convert model names into filesystem-safe file names."""
    return re.sub(r"[^a-z0-9]+", "_", model_name.lower()).strip("_")


def get_git_hash() -> str:
    """Get current git commit hash for this repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        pass

    try:
        safe_dir = Path.cwd().resolve().as_posix()
        result = subprocess.run(
            ["git", "-c", f"safe.directory={safe_dir}", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return "N/A (not a git repository)"


def write_simple_yaml(path: Path, data: Mapping[str, Any], encoding: str) -> None:
    """Write a minimal YAML file without external dependencies."""
    lines: List[str] = []
    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
            continue
        lines.append(f"{key}: {value}")
    path.write_text("\n".join(lines) + "\n", encoding=encoding)
