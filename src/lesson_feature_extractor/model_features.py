"""模型特征提取。"""

from __future__ import annotations

import ast
import hashlib
import json
import keyword
import math
import re
import shutil
import subprocess
import sys
import uuid
from contextlib import contextmanager
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .constants import (
    GT_CODE_JSON,
    MODEL_FEATURE_COLUMNS,
    MODEL_TO_FILES,
    PYLINT_CODE_SMELL_COLUMNS,
    TEST_CASE_JSON,
)
from .utils import load_json, parse_task_id

_BLEU_CACHE: Dict[Tuple[str, str], float] = {}
_CODE_BLEU_CACHE: Dict[Tuple[str, str], float] = {}
_BLACK_CACHE: Dict[str, float] = {}
_SEMGREP_CACHE: Dict[str, float] = {}
_SEMGREP_AVAILABLE: bool | None = None
_PYLINT_CACHE: Dict[str, Dict[str, float]] = {}
_PYLINT_AVAILABLE: bool | None = None


@contextmanager
def workspace_temp_dir(prefix: str) -> Path:
    """在项目目录下创建可写临时目录，规避特定环境下 tempfile 权限问题。"""
    root = Path.cwd() / ".tmp_runtime"
    root.mkdir(parents=True, exist_ok=True)
    temp_dir = root / f"{prefix}_{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=False, exist_ok=False)
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def code_hash(source_code: str) -> str:
    """计算代码哈希值。"""
    return hashlib.sha256(source_code.encode("utf-8", errors="ignore")).hexdigest()


def tokenize_code(source_code: str) -> List[str]:
    """将代码分词为 BLEU 计算所需 token。"""
    return re.findall(r"\w+|[^\w\s]", source_code, flags=re.UNICODE)


def build_ngram_counter(tokens: List[str], n: int) -> Counter[Tuple[str, ...]]:
    """构建 n-gram 计数。"""
    if n <= 0:
        return Counter()
    if len(tokens) < n:
        return Counter()
    ngrams: List[Tuple[str, ...]] = [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]
    return Counter(ngrams)


def compute_bleu(candidate_code: str, reference_code: str, max_n: int = 4) -> float:
    """计算简化版 BLEU 分数。"""
    cache_key = (code_hash(candidate_code), code_hash(reference_code))
    if cache_key in _BLEU_CACHE:
        return _BLEU_CACHE[cache_key]

    candidate_tokens = tokenize_code(candidate_code)
    reference_tokens = tokenize_code(reference_code)
    if not candidate_tokens or not reference_tokens:
        _BLEU_CACHE[cache_key] = 0.0
        return 0.0

    precisions: List[float] = []
    for n in range(1, max_n + 1):
        candidate_counter = build_ngram_counter(candidate_tokens, n)
        reference_counter = build_ngram_counter(reference_tokens, n)
        candidate_total = max(sum(candidate_counter.values()), 1)
        overlap = 0
        for ngram, count in candidate_counter.items():
            overlap += min(count, reference_counter.get(ngram, 0))
        precision = (overlap + 1.0) / (candidate_total + 1.0)
        precisions.append(precision)

    geometric_mean = math.exp(sum(math.log(value) for value in precisions) / max_n)
    candidate_length = len(candidate_tokens)
    reference_length = len(reference_tokens)
    if candidate_length > reference_length:
        brevity_penalty = 1.0
    else:
        brevity_penalty = math.exp(1.0 - (reference_length / max(candidate_length, 1)))
    score = brevity_penalty * geometric_mean
    _BLEU_CACHE[cache_key] = score
    return score


def compute_weighted_unigram_score(candidate_code: str, reference_code: str) -> float:
    """计算关键词加权 unigram 相似度（参考 CALL 的 weighted ngram 思想）。"""
    candidate_tokens = tokenize_code(candidate_code)
    reference_tokens = tokenize_code(reference_code)
    if not candidate_tokens or not reference_tokens:
        return 0.0

    python_keywords = set(keyword.kwlist)
    candidate_counter = Counter(candidate_tokens)
    reference_counter = Counter(reference_tokens)
    weighted_overlap = 0.0
    weighted_total = 0.0
    for token, cand_count in candidate_counter.items():
        weight = 1.0 if token in python_keywords else 0.2
        overlap_count = min(cand_count, reference_counter.get(token, 0))
        weighted_overlap += overlap_count * weight
        weighted_total += cand_count * weight
    return (weighted_overlap + 1.0) / (weighted_total + 1.0)


def compute_ast_syntax_match(candidate_code: str, reference_code: str) -> float:
    """计算 AST 语法结构匹配度（参考 CALL 的 syntax_match 思想）。"""
    try:
        candidate_tree = ast.parse(candidate_code)
        reference_tree = ast.parse(reference_code)
    except SyntaxError:
        return 0.0

    candidate_subtrees = {ast.dump(node, include_attributes=False) for node in ast.walk(candidate_tree)}
    reference_subtrees = [ast.dump(node, include_attributes=False) for node in ast.walk(reference_tree)]
    if not reference_subtrees:
        return 0.0
    match_count = sum(1 for subtree in reference_subtrees if subtree in candidate_subtrees)
    return match_count / len(reference_subtrees)


def compute_code_bleu(candidate_code: str, reference_code: str) -> float:
    """计算可落地版 CodeBLEU（参考 CALL 的组合公式）。"""
    cache_key = (code_hash(candidate_code), code_hash(reference_code))
    if cache_key in _CODE_BLEU_CACHE:
        return _CODE_BLEU_CACHE[cache_key]

    ngram_score = compute_bleu(candidate_code, reference_code)
    weighted_score = compute_weighted_unigram_score(candidate_code, reference_code)
    syntax_score = compute_ast_syntax_match(candidate_code, reference_code)
    dataflow_score = 0.0
    score = 0.25 * (ngram_score + weighted_score + syntax_score + dataflow_score)
    _CODE_BLEU_CACHE[cache_key] = score
    return score


def has_syntax_error(source_code: str) -> bool:
    """检测代码是否存在语法错误。"""
    try:
        ast.parse(source_code)
    except SyntaxError:
        return True
    return False


def black_diff_count(source_code: str) -> float:
    """调用 black 统计差异块数量。"""
    code_digest = code_hash(source_code)
    if code_digest in _BLACK_CACHE:
        return _BLACK_CACHE[code_digest]
    if not shutil_which("black"):
        _BLACK_CACHE[code_digest] = math.nan
        return math.nan

    with workspace_temp_dir("black") as temp_dir:
        temp_path = temp_dir / "black_call.py"
        temp_path.write_text(source_code, encoding="utf-8")
        result = subprocess.run(
            ["black", str(temp_path), "--diff"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
        )
        output_text = f"{result.stdout}\n{result.stderr}"
        changed = output_text.count("@@") // 2
    _BLACK_CACHE[code_digest] = float(changed)
    return float(changed)


def semgrep_available() -> bool:
    """判断 semgrep 是否可用。"""
    global _SEMGREP_AVAILABLE
    if _SEMGREP_AVAILABLE is not None:
        return _SEMGREP_AVAILABLE
    result = subprocess.run(
        [sys.executable, "-m", "semgrep", "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=False,
    )
    _SEMGREP_AVAILABLE = result.returncode == 0
    return _SEMGREP_AVAILABLE


def semgrep_issue_count(source_code: str) -> float:
    """调用 semgrep 统计潜在安全问题数量。"""
    code_digest = code_hash(source_code)
    if code_digest in _SEMGREP_CACHE:
        return _SEMGREP_CACHE[code_digest]
    if not semgrep_available():
        _SEMGREP_CACHE[code_digest] = math.nan
        return math.nan

    with workspace_temp_dir("semgrep") as temp_dir:
        temp_path = temp_dir / "semgrep_call.py"
        log_path = temp_dir / "semgrep_log.json"
        temp_path.write_text(source_code, encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "semgrep",
                "--config",
                "p/python",
                str(temp_path),
                "--json",
                "-o",
                str(log_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
        )
        # semgrep 正常时常见返回码包括 0（无结果）和 1（有结果）
        if result.returncode not in (0, 1) or not log_path.exists():
            _SEMGREP_CACHE[code_digest] = math.nan
            return math.nan
        try:
            payload = load_json(log_path, "utf-8")
            issue_count = float(len(payload.get("results", [])))
        except Exception:
            issue_count = math.nan
    _SEMGREP_CACHE[code_digest] = issue_count
    return issue_count


def pylint_available() -> bool:
    """判断 pylint 是否可用。"""
    global _PYLINT_AVAILABLE
    if _PYLINT_AVAILABLE is not None:
        return _PYLINT_AVAILABLE
    result = subprocess.run(
        [sys.executable, "-m", "pylint", "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=False,
    )
    _PYLINT_AVAILABLE = result.returncode == 0
    return _PYLINT_AVAILABLE


def pylint_code_smell_counts(source_code: str) -> Dict[str, float]:
    """调用 pylint 统计指定代码异味数量。"""
    code_digest = code_hash(source_code)
    if code_digest in _PYLINT_CACHE:
        return dict(_PYLINT_CACHE[code_digest])

    if not pylint_available():
        nan_payload: Dict[str, float] = {column: math.nan for column in PYLINT_CODE_SMELL_COLUMNS}
        _PYLINT_CACHE[code_digest] = nan_payload
        return dict(nan_payload)

    counts: Dict[str, float] = {column: 0.0 for column in PYLINT_CODE_SMELL_COLUMNS}
    with workspace_temp_dir("pylint") as temp_dir:
        temp_path = temp_dir / "pylint_call.py"
        temp_path.write_text(source_code, encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pylint",
                str(temp_path),
                "--score=n",
                "--reports=n",
                "--output-format=json",
                "--disable=all",
                f"--enable={','.join(PYLINT_CODE_SMELL_COLUMNS)}",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
        )
        payload_text = result.stdout.strip()
        if payload_text:
            try:
                payload = json.loads(payload_text)
                if isinstance(payload, list):
                    for item in payload:
                        symbol = str(item.get("symbol", ""))
                        if symbol in counts:
                            counts[symbol] += 1.0
            except json.JSONDecodeError:
                counts = {column: math.nan for column in PYLINT_CODE_SMELL_COLUMNS}

    _PYLINT_CACHE[code_digest] = counts
    return dict(counts)


def shutil_which(command_name: str) -> str | None:
    """查找可执行文件路径。"""
    try:
        from shutil import which
    except Exception:
        return None
    return which(command_name)


def build_test_case_total_map(test_case_path: Path, encoding: str) -> Dict[int, int]:
    """构建每个任务的测试用例总数映射。"""
    rows = load_json(test_case_path, encoding)
    total_map: Dict[int, int] = {}
    for row in rows:
        task_id = parse_task_id(row.get("Task ID", ""))
        base_total = len(row.get("base_input", []))
        plus_total = len(row.get("plus_input", []))
        total_map[task_id] = base_total + plus_total
    return total_map


def build_pass_count_map(test_result_path: Path, encoding: str) -> Dict[int, int]:
    """构建每个任务通过测试数映射。"""
    rows = load_json(test_result_path, encoding)
    pass_map: Dict[int, int] = {}
    for row in rows:
        task_id = parse_task_id(row.get("Task ID", ""))
        base_pass = len(row.get("base", []))
        plus_pass = len(row.get("plus", []))
        pass_map[task_id] = base_pass + plus_pass
    return pass_map


def load_all_model_codes(website_data_dir: Path, encoding: str) -> Dict[str, List[str]]:
    """读取所有模型的代码列表。"""
    model_codes: Dict[str, List[str]] = {}
    for model_name, file_map in MODEL_TO_FILES.items():
        code_path = website_data_dir / file_map["code_json"]
        model_codes[model_name] = [str(code) for code in load_json(code_path, encoding)]
    return model_codes


def compute_mutual_similarity(
    model_name: str,
    task_id: int,
    generated_code: str,
    all_model_codes: Dict[str, List[str]],
) -> Tuple[float, float]:
    """计算与其他模型在同任务下的互相似度。"""
    other_codes: List[str] = []
    for other_model, codes in all_model_codes.items():
        if other_model == model_name:
            continue
        if task_id < len(codes):
            other_codes.append(codes[task_id])
    if not other_codes:
        return math.nan, math.nan

    bleu_scores = [compute_bleu(generated_code, other) for other in other_codes]
    code_bleu_scores = [compute_code_bleu(generated_code, other) for other in other_codes]
    mut_sim_b = sum(bleu_scores) / len(bleu_scores)
    mut_sim_cb = sum(code_bleu_scores) / len(code_bleu_scores)
    return mut_sim_b, mut_sim_cb


def build_model_feature_map(model_name: str, website_data_dir: Path, encoding: str) -> Dict[int, Dict[str, Any]]:
    """构建 task_id 到模型特征的映射。"""
    model_files = MODEL_TO_FILES[model_name]
    code_path = website_data_dir / model_files["code_json"]
    test_result_path = website_data_dir / model_files["test_json"]
    gt_path = website_data_dir / GT_CODE_JSON
    test_case_path = website_data_dir / TEST_CASE_JSON

    generated_codes: List[str] = [str(code) for code in load_json(code_path, encoding)]
    ground_truth_codes: List[str] = [str(code) for code in load_json(gt_path, encoding)]
    all_model_codes = load_all_model_codes(website_data_dir, encoding)
    pass_count_map = build_pass_count_map(test_result_path, encoding)
    total_count_map = build_test_case_total_map(test_case_path, encoding)

    feature_map: Dict[int, Dict[str, Any]] = {}
    upper_bound = min(len(generated_codes), len(ground_truth_codes))
    for task_id in range(upper_bound):
        generated_code = generated_codes[task_id]
        ground_truth_code = ground_truth_codes[task_id]
        pass_count = pass_count_map.get(task_id, 0)
        total_count = total_count_map.get(task_id, 0)
        pass_rate = (pass_count / total_count) if total_count > 0 else 0.0
        run_err_rate = max(0.0, 1.0 - pass_rate)
        syn_err = 1 if has_syntax_error(generated_code) else 0
        gold_sim_b = compute_bleu(generated_code, ground_truth_code)
        gold_sim_cb = compute_code_bleu(generated_code, ground_truth_code)
        mut_sim_b, mut_sim_cb = compute_mutual_similarity(
            model_name=model_name,
            task_id=task_id,
            generated_code=generated_code,
            all_model_codes=all_model_codes,
        )
        black_count = black_diff_count(generated_code)
        semgrep_count = semgrep_issue_count(generated_code)
        pylint_counts = pylint_code_smell_counts(generated_code)

        row: Dict[str, Any] = {
            "pass_rate": round(pass_rate, 6),
            "run_err_rate": round(run_err_rate, 6),
            "syn_err": syn_err,
            "gold_sim_CB": round(gold_sim_cb, 6),
            "gold_sim_B": round(gold_sim_b, 6),
            "mut_sim_CB": round(mut_sim_cb, 6) if not math.isnan(mut_sim_cb) else math.nan,
            "mut_sim_B": round(mut_sim_b, 6) if not math.isnan(mut_sim_b) else math.nan,
            "timeout_rate": math.nan,
            "black_count": round(black_count, 6) if not math.isnan(black_count) else math.nan,
            "semgrep_count": round(semgrep_count, 6) if not math.isnan(semgrep_count) else math.nan,
        }
        for column in PYLINT_CODE_SMELL_COLUMNS:
            value = pylint_counts.get(column, math.nan)
            row[column] = int(value) if not math.isnan(value) else math.nan

        feature_map[task_id] = {key: row.get(key, math.nan) for key in MODEL_FEATURE_COLUMNS}

    return feature_map
