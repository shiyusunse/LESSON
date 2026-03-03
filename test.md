# 调试假设与验证过程

## 1. 当前假设

### H1：`prompt_len` 使用 CountVectorizer 累加和

- Hypothesis：
  - 先执行 `strip_prompt_test_examples`
  - 再按 `CountVectorizer(lowercase=False, min_df=1)` 计算 `X.sum()`
- Risk：若仍使用 regex 计数，会与 design 不一致。

### H2：`LOC/ast_nodes` 继续使用 Ground Truth 口径

- Hypothesis：
  - `LOC == count_loc(gt_code_complete) - count_loc(prompt_raw)`
  - `ast_nodes == count_ast_nodes(gt_code_complete)`

### H3：Ground Truth 冲突或缺失仍 fail fast

- Hypothesis：冲突/缺失均抛 `ValueError`，不回退旧口径。

## 2. 验证命令

```bash
python -m pytest test/test_task_features.py -q
python test/test_task_features.py --model CodeGen-16B --error-id 13
```

## 3. 本轮记录

## Record: 2026-03-03 16:xx prompt_len_countvectorizer_alignment
- Hypothesis：CountVectorizer token 累加和满足最新 design 定义。
- Action/Command：运行单测与人工审查命令。
- Observation：输出包含特征词预览与 token 累加和，结果可审查。
- Conclusion：实现与 plan/design 对齐。
- Next Step：端到端抽样运行评估全量影响。

## 4. 当前假设（pass_rate/run_err_rate）

### H4：`pass_rate` 与 `run_err_rate` 计算口径

- Hypothesis：
  - `pass_count = len(base) + len(plus)`（来自 `*_test.json`）
  - `total_count = len(base_input) + len(plus_input)`（来自 `HumanEvalPlus-test.json`）
  - `pass_rate = pass_count / total_count`（`total_count == 0` 时为 `0.0`）
  - `run_err_rate = max(0.0, 1.0 - pass_rate)`

### H5：`base`/`plus` 语义确认（通过抽查）

- Hypothesis：
  - `base`/`plus` 存储的是“通过样例”而非“未通过样例”。
  - 通过抽查同一模型下 `error_csv` 与 `*_test.json` 的任务映射进行验证，并输出证据到审查 JSON。

## 5. 验证命令

```bash
python -m pytest test/test_model_features.py -q
python -m pytest -q
python test/test_model_features.py --model CodeGen-16B --error-id 13 --output test_results/pass_rate_audit_codegen_13_20260303_184500.json
python test/test_model_features.py --model GPT-4 --error-id 393 --output test_results/pass_rate_audit_gpt4_393_20260303_184500.json
```

## 6. 本轮记录

## Record: 2026-03-03 18:xx pass_rate_run_err_rate_tests_and_audit
- Hypothesis：`pass_rate/run_err_rate` 公式实现正确，且可对指定 `model+error_id` 导出审查 JSON。
- Action/Command：
  - 新增 `test/test_model_features.py`
  - 运行 `python -m pytest test/test_model_features.py -q`
  - 运行 `python -m pytest -q`
  - 运行两条人工审查命令并输出到 `test_results/`
- Observation：
  - `test/test_model_features.py`：`7 passed`。
  - 全量 `pytest` 在收集 `CALL-main` 子项目时失败：
    - `CALL-main/neo_test.py` 缺少 `transformers`
    - `CALL-main/code_metrics/test_util.py` 缺少 `pyext`
  - 审查 JSON 已生成：
    - `test_results/pass_rate_audit_codegen_13_20260303_184500.json`
    - `test_results/pass_rate_audit_gpt4_393_20260303_184500.json`
  - `CodeGen-16B + error_id=13` 审查结果：
    - `pass_count=851`，`total_count=865`
    - `pass_rate=0.983815`，`run_err_rate=0.016185`
    - `base/plus` 语义结论：`base_plus_store_passed_cases`（有 `pass_count=0` 的 error 样本证据）。
  - `GPT-4 + error_id=393` 审查结果：
    - `pass_count=100`，`total_count=928`
    - `pass_rate=0.107759`，`run_err_rate=0.892241`
    - 当前抽查结论：`inconclusive_from_current_sample`（样本内未出现 `pass_count=0` 强证据）。
- Conclusion：目标测试代码与审查 JSON 输出能力已落地，核心公式通过；`base/plus` 在 CodeGen 抽查下可判定为“通过样例”。
- Next Step：如需全量 `pytest` 通过，需要补齐 `CALL-main` 依赖或将测试范围限定到本项目测试目录。

## 7. 新口径调整记录（fail_count/164）

## Record: 2026-03-03 19:xx pass_rate_formula_switch_to_humanevalfailed
- Hypothesis：
  - `pass_rate = 1 - fail_count / 164`
  - `run_err_rate = fail_count / 164`
  - 其中 `fail_count` 从 `HumanEvalFailed.json` 的模型失败任务列表长度获取。
- Action/Command：
  - 修改 `src/lesson_feature_extractor/model_features.py`
  - 修改 `test/test_model_features.py`
  - 运行 `python -m pytest test/test_model_features.py -q`
  - 运行：
    - `python test/test_model_features.py --model CodeGen-16B --error-id 13 --output test_results/pass_rate_audit_codegen_13_20260303_184500.json`
    - `python test/test_model_features.py --model GPT-4 --error-id 393 --output test_results/pass_rate_audit_gpt4_393_20260303_184500.json`
- Observation：
  - `test/test_model_features.py`：`7 passed`。
  - CodeGen-16B 审查结果：`fail_count=110`，`pass_rate=0.329268`，`run_err_rate=0.670732`。
  - GPT-4 审查结果：`fail_count=18`，`pass_rate=0.890244`，`run_err_rate=0.109756`。
  - 两份审查 JSON 均输出成功，且 `formula_check_passed=true`。
- Conclusion：`pass_rate/run_err_rate` 已切换到 `HumanEvalFailed.json + 固定 total_count=164` 口径。
- Next Step：如后续需按任务粒度区分 `pass_rate`，需重新引入 task-level 总数口径并调整下游解释。
