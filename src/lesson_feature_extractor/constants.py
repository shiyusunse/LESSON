"""特征提取常量定义。"""

from typing import Dict, List

MODEL_TO_FILES: Dict[str, Dict[str, str]] = {
    "CodeGen-16B": {
        "error_csv": "codegen-humaneval_error.csv",
        "code_json": "codegen_code.json",
        "test_json": "codegen_test.json",
    },
    "InCoder-1B": {
        "error_csv": "incoder-humaneval_error.csv",
        "code_json": "incoder_code.json",
        "test_json": "incoder_test.json",
    },
    "GPT-3.5": {
        "error_csv": "gpt-3.5-humaneval_error.csv",
        "code_json": "chatgpt_code.json",
        "test_json": "chatgpt_test.json",
    },
    "GPT-4": {
        "error_csv": "gpt-4-humaneval_error.csv",
        "code_json": "gpt-4_code.json",
        "test_json": "gpt4_test.json",
    },
    "SantaCoder": {
        "error_csv": "santacoder-humaneval_error.csv",
        "code_json": "santacoder_code.json",
        "test_json": "santacoder_test.json",
    },
    "StarCoder": {
        "error_csv": "starcoder-humaneval_error.csv",
        "code_json": "starcoder_code.json",
        "test_json": "starcoder_test.json",
    },
}

GT_CODE_JSON: str = "gt_code.json"
TEST_CASE_JSON: str = "HumanEvalPlus-test.json"
HUMAN_EVAL_FAILED_JSON: str = "HumanEvalFailed.json"

BASE_MODEL_FEATURE_COLUMNS: List[str] = [
    "pass_rate",
    "run_err_rate",
    "syn_err",
    "gold_sim_CB",
    "gold_sim_B",
    "mut_sim_CB",
    "mut_sim_B",
    "timeout_rate",
    "black_count",
    "semgrep_count",
]

PYLINT_CODE_SMELL_COLUMNS: List[str] = [
    "invalid-name",
    "singleton-comparison",
    "unnecessary-lambda-assignment",
    "non-ascii-name",
    "disallowed-name",
    "too-many-arguments",
    "too-many-nested-blocks",
    "too-many-boolean-expressions",
    "consider-merging-isinstance",
    "chained-comparison",
    "broad-exception-caught",
    "broad-exception-raised",
    "unnecessary-lambda",
]

MODEL_FEATURE_COLUMNS: List[str] = BASE_MODEL_FEATURE_COLUMNS + PYLINT_CODE_SMELL_COLUMNS

TASK_FEATURE_COLUMNS: List[str] = [
    "prompt_len",
    "LOC",
    "ast_nodes",
]

SEMANTIC_FEATURE_COLUMNS: List[str] = [
    "Aa1",
    "Aa2",
    "Ab1",
    "Ac1",
    "Ac2",
    "Ad1",
    "Ad4",
    "Ae1",
    "Ae2",
    "Ae3",
    "Af1",
    "Af2",
    "Ag1",
]

SYNTACTIC_FEATURE_COLUMNS: List[str] = [
    "Ba1",
    "Bb1",
    "Bb2",
    "Bc2",
    "Bd1",
    "Bd2",
    "Bd3",
    "Be4",
    "Be1",
    "Be5",
    "Be6",
    "Bf1",
    "Bg1",
    "Bg2",
]

SEMANTIC_CODE_TO_FEATURE: Dict[str, str] = {code: code for code in SEMANTIC_FEATURE_COLUMNS}

SYNTACTIC_CODE_TO_FEATURE: Dict[str, str] = {code: code for code in SYNTACTIC_FEATURE_COLUMNS}
