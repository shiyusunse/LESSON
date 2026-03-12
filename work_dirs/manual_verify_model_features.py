import json
import tempfile
from pathlib import Path

from lesson_feature_extractor.constants import HUMAN_EVAL_FAILED_JSON, MODEL_TO_FILES, TEST_CASE_JSON
from lesson_feature_extractor.model_features import build_model_feature_map


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    website_data_dir = root / "website_data"
    website_data_dir.mkdir(parents=True, exist_ok=True)

    for model_name, file_map in MODEL_TO_FILES.items():
        if model_name == "CodeGen-16B":
            code_list = ["def keep(x):\n    return x\n"]
            test_rows = [{"Task ID": 0, "base": [0], "plus": []}]
        else:
            code_list = ["def keep(x):\n    return x\n"]
            test_rows = [{"Task ID": 0, "base": [], "plus": []}]
        write_json(website_data_dir / file_map["code_json"], code_list)
        write_json(website_data_dir / file_map["test_json"], test_rows)

    write_json(website_data_dir / "gt_code.json", ["def keep(x):\n    return x\n"])
    write_json(website_data_dir / TEST_CASE_JSON, [{"Task ID": "HumanEval_0", "base_input": [[1]], "plus_input": []}])
    write_json(
        website_data_dir / HUMAN_EVAL_FAILED_JSON,
        {name: ([0, 1] if name == "CodeGen-16B" else []) for name in MODEL_TO_FILES},
    )

    feature_map = build_model_feature_map("CodeGen-16B", website_data_dir, "utf-8")
    row = feature_map[0]
    print({
        "pass_rate": row["pass_rate"],
        "run_err_rate": row["run_err_rate"],
        "syn_err": row["syn_err"],
        "timeout_rate": row["timeout_rate"],
    })

