# Status: DRAFT
# Task: 为 pass_rate 与 run_err_rate 增加测试代码，并按单模型全量 error 导出审查 JSON
# Updated: 2026-03-03 19:28

## 1. 已确认口径

1. `pass_rate`：
   - 计算公式：`1 - fail_count / total_count`。
   - `fail_count` 从 `HumanEvalFailed.json` 按模型读取失败任务列表长度。
   - `total_count` 固定为 `164`。
2. `run_err_rate`：
   - 计算公式：`fail_count / total_count`。
3. 人工审查输出：
   - 支持输入特定 `model` 做全量 error 测试（覆盖该模型 `error_csv` 中全部 error）。
   - 将“计算过程 + 关键中间值 + 最终结果 + 断言结论”写入 JSON 文件，便于人工审查与留档。
   - JSON 文件名必须带时间戳，格式建议：`<prefix>_YYYYMMDD_HHMMSS.json`。
   - 测试审查文件统一存放在 `test_results/` 目录。
4. `base` / `plus` 语义确认：
   - 需要通过抽查某个模型，联合对比 `error_csv` 与 `*_test.json`，确认 `base`、`plus` 代表“通过样例”还是“未通过样例”。
   - 抽查结论必须写入审查 JSON（含证据字段与判定理由）。

## 2. Change Batch

## Change Batch: 20260303_pass_rate_run_err_rate_tests
- Goal:
  - 为 `pass_rate`、`run_err_rate` 建立可复现单元测试，覆盖正常与边界场景。
  - 提供指定 `model` 的全量 error 审查模式，并输出结构化 JSON。
  - 通过抽查比对确认 `base`、`plus` 字段语义，避免指标方向误判。
- Files to modify:
  - `test/test_model_features.py`（若不存在则新建）
  - `test.md`（记录测试假设、观察与结论）
- Steps:
  1. 盘点 `model_features.py` 中与 `pass_rate`、`run_err_rate` 直接相关函数与输入依赖。
  2. 在测试中构造最小 JSON 样例，覆盖：
     - 普通场景：`total_count > 0`
     - 边界场景：`total_count == 0`
     - 无对应任务映射时的默认行为
  3. 对 `build_pass_count_map`、`build_test_case_total_map` 与最终特征行中的两个指标分别断言。
  4. 增加审查入口（CLI 参数）：`--model`、`--output`。
  5. 增加抽查逻辑：选定一个模型，关联 `error_csv` 与 `*_test.json`（必要时参考 `HumanEvalPlus-test.json`），输出 `base/plus` 语义判定证据。
  6. 按 `model` 遍历该模型全部 error 样本，输出审查 JSON，至少包含：
     - 输入参数（model、error_total、task_coverage）
     - 数据来源文件路径
     - 模型级 `fail_count`、`total_count`、`pass_rate`、`run_err_rate`
     - 每个 error 的映射结果（至少 `error_id`、`task_id`、相关中间值）
     - `base/plus` 语义抽查证据（抽查模型、对比样本、判定结论）
     - 计算公式与最终结论
     - 输出文件名含时间戳（自动追加或按约定生成）
     - 输出目录为 `test_results/`
  7. 运行目标测试并记录结果。
  8. 仅更新 `test.md`（不更新 `README.md`）。
  9. 执行乱码检查后提交结果。
- Risks:
  - 测试如果依赖真实大文件，执行时间会偏长且不稳定。
  - 任务 ID 解析格式（`HumanEval_1` / `HumanEval/1` / `1`）若处理不一致，会导致断言偏差。
  - 全量 error 遍历时，`error_id -> task_id` 映射可能受 CSV 脏数据影响。
  - 若仅凭单样本判定 `base/plus` 语义，可能存在偏差，需要至少一组抽查证据。
- Rollback:
  - 若新增测试影响现有流程，回滚到本批次前的 `plan.md` 与测试文件版本。
  - 保留最小可运行测试，再逐步扩展覆盖面。
- Done Criteria:
  - `pass_rate` 与 `run_err_rate` 的核心公式测试通过。
  - 至少覆盖 1 个边界场景（`fail_count == 0`）。
  - 可通过 `model` 生成覆盖该模型全部 error 的审查 JSON，且 JSON 可直接用于人工核对。
  - 已完成至少一个模型的抽查，并在审查 JSON 中给出 `base/plus` 语义结论。
  - 审查 JSON 文件名包含时间戳，避免覆盖历史结果。
  - 测试文档仅在 `test.md` 同步完成。
  - 乱码检查通过。

## 3. 验证命令（待执行）

1. `python -m pytest test/test_model_features.py -q`
2. `python -m pytest -q`
3. `python test/test_model_features.py --model CodeGen-16B --output test_results/pass_rate_audit_codegen_all_20260303_193000.json`
4. `python test/test_model_features.py --model GPT-4 --output test_results/pass_rate_audit_gpt4_all_20260303_193000.json`
5. `python` 乱码检查脚本（AGENTS 要求）
