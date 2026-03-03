# LESSON 代码设计说明（基于当前 `src`）

## 1. 目标与范围

本项目的目标是从多模型代码生成错误数据中提取可用于分析/建模的特征，并输出结构化 CSV。
当前 `src` 的职责是“离线特征构建”，不包含训练流程与在线服务。

## 2. 总体架构

采用“入口脚本 + 特征模块 + 管线拼装 + 工具函数”的分层结构：

1. `run_feature_extraction.py`
2. `lesson_feature_extractor/constants.py`
3. `lesson_feature_extractor/task_features.py`
4. `lesson_feature_extractor/model_features.py`
5. `lesson_feature_extractor/pipeline.py`
6. `lesson_feature_extractor/utils.py`

数据流为：

1. CLI 解析参数，建立 `work_dirs/<run_name>/`。
2. 从 HumanEval JSONL 预计算任务复杂度特征（`prompt_len`），从defects4codellm预计算任务复杂度特征（`LOC/ast_nodes`）
3. 对每个模型读取错误 CSV + 网站 JSON 数据，计算模型相关特征。
4. 将任务特征、模型特征、语义/语法 one-hot 合并成统一行。
5. 输出每个模型一个 `*_features.csv`，并写 `config.yaml` 与 `log.txt`。

## 3. 模块职责

### 3.1 `run_feature_extraction.py`

- 负责参数入口与运行目录管理。
- 写入日志头部关键信息：`Command`、`Environment`、`Seed`、`Git Hash`、`Config`。
- 调用 `build_task_feature_map` 与 `run_feature_pipeline` 完成主流程。

### 3.2 `constants.py`

- 定义模型到数据文件的映射 `MODEL_TO_FILES`。
- 定义输出特征列顺序：
  - 任务复杂度列：`TASK_FEATURE_COLUMNS`
  - 模型行为列：`MODEL_FEATURE_COLUMNS`
  - 语义/语法 one-hot 列：`SEMANTIC_FEATURE_COLUMNS`、`SYNTACTIC_FEATURE_COLUMNS`

### 3.3 `task_features.py`

- 针对 HumanEval 基准任务计算 3 个复杂度指标：
  - `prompt_len`：HumanEval JSONL中的`prompt`除去给出的测试用例示例后，计算正则 `\S+` 分词计数，使用from sklearn.feature_extraction.text import CountVectorizer 计算token数
  - `LOC`：defects4codellm中的`Ground Truth Code (Complete)` 非空行数 - HumanEval JSONL中的`prompt`中的非空行数
  - `ast_nodes`：defects4codellm中的`Ground Truth Code (Complete)` AST 节点总数（语法错返回 0）
- 输出 `task_id -> feature_dict` 映射供后续拼接。

### 3.4 `model_features.py`

- 负责每个模型每个任务（`task_id`）的行为特征计算，核心入口是 `build_model_feature_map`。
- 输入文件（来自 `website_data_dir`）：
  - `*_code.json`：当前模型生成代码列表
  - `*_test.json`：当前模型测试结果（`base`/`plus`）
  - `gt_code.json`：参考代码列表
  - `HumanEvalPlus-test.json`：测试输入（`base_input`/`plus_input`）
  - `HumanEvalFailed.json`：模型级失败任务列表
- 遍历范围：`task_id in [0, min(len(generated_codes), len(ground_truth_codes)))`。
- 所有最终写入 CSV 的模型特征列由 `MODEL_FEATURE_COLUMNS` 固定；浮点结果多数在写入前 `round(..., 6)`。

#### 3.4.1 计数与映射预处理

1. `fail_count`
- 来源：`load_model_fail_count(HumanEvalFailed.json, model_name)`
- 公式：`fail_count = len(set(failed_task_ids))`

2. `total_count`
- 当前固定常量：`164`

3. `test_case_input_map`
- 来源：`_build_test_case_input_map`
- 逻辑：`test_cases = base_input + plus_input`，供 `timeout_rate` 评估使用。

4. `pass_count_map`（仅用于审查与辅助分析，不参与 pass_rate 主公式）
- 来源：`build_pass_count_map(test_result_path, encoding)`
- 公式：`pass_count = len(base) + len(plus)`

5. `entry_point_map`
- 来源：`_extract_entry_point(gt_code)`
- 逻辑：从 `gt_code` AST 顶层提取第一个函数名；未找到或解析失败返回空字符串。

#### 3.4.2 每一个度量的当前计算逻辑

1. `pass_rate`:对于某一个error而言，测试用例的通过率
- 公式：`pass_rate = 1.0 - fail_count / total_count`
- 注：`total_count` 当前固定为 `164`，因此同一模型下所有 `task_id` 的 `pass_rate` 相同。

2. `run_err_rate`：对于某一个error而言，测试用例的运行时error率
- 公式：`run_err_rate = fail_count / total_count`
- 注：同一模型下所有 `task_id` 的 `run_err_rate` 相同。

3. `syn_err`
- 公式：`syn_err = 1 if ast.parse(generated_code) 抛 SyntaxError else 0`

4. `gold_sim_B`（生成代码 vs Ground Truth 的 BLEU）
- 来源函数：`compute_bleu(candidate_code, reference_code, max_n=4)`
- token 切分：`re.findall(r"\w+|[^\w\s]", source_code)`
- n-gram 精度：
  - 对 `n=1..4` 计算 overlap
  - 使用加一平滑：`(overlap + 1) / (candidate_total + 1)`
- 汇总：
  - 几何平均：`exp(mean(log(precision_n)))`
  - 长度惩罚（brevity penalty）：
    - `1.0`（候选更长）
    - 否则 `exp(1 - reference_length / candidate_length)`
- 空 token 边界：任一侧为空时返回 `0.0`
- 缓存：`_BLEU_CACHE[(sha256(candidate), sha256(reference))]`

5. `gold_sim_CB`（生成代码 vs Ground Truth 的 CodeBLEU）
- 来源函数：`compute_code_bleu`
- 公式：
  - `ngram_score = compute_bleu(...)`
  - `weighted_score = compute_weighted_unigram_score(...)`
  - `syntax_score = compute_ast_syntax_match(...)`
  - `dataflow_score = 0.0`（当前固定值，尚未实现数据流分量）
  - `gold_sim_CB = 0.25 * (ngram_score + weighted_score + syntax_score + dataflow_score)`
- 其中 `weighted_unigram` 权重：
  - Python 关键字权重 `1.0`
  - 非关键字权重 `0.2`
  - 同样使用加一平滑
- 其中 `syntax_score`：
  - 对两段代码做 AST 解析
  - 统计 `reference` 的子树中有多少出现在 `candidate` 子树集合中
  - 任一方语法错误则为 `0.0`
- 缓存：`_CODE_BLEU_CACHE[(sha256(candidate), sha256(reference))]`

6. `mut_sim_B` / `mut_sim_CB`（与其他模型同任务互相似度）
- 来源函数：`compute_mutual_similarity`
- 逻辑：
  - 取“除当前模型外”的同 `task_id` 代码
  - 分别计算 BLEU / CodeBLEU
  - 对其他模型取平均
- 边界：若无可比较代码，返回 `NaN`

7. `black_count`
- 来源函数：`black_diff_count`
- 逻辑：
  - 将代码写入临时文件，执行 `black <file> --diff`
  - 以输出中 `@@` 个数估计 diff hunk 数：`changed = output_text.count("@@") // 2`
- 边界：系统无 `black` 时返回 `NaN`
- 缓存：`_BLACK_CACHE[code_hash]`

8. `semgrep_count`
- 来源函数：`semgrep_issue_count`
- 逻辑：
  - 执行 `semgrep --config p/python <file> --json -o <log_path>`
  - 读取 JSON，计数 `len(payload["results"])`
- 降级：
  - `semgrep` 不可用 => `0.0`
  - 执行失败或 JSON 读取失败 => `0.0`
- 缓存：`_SEMGREP_CACHE[code_hash]`

9. `timeout_rate`
- 主流程短路：若 `syn_err == 1`，直接 `timeout_rate = 0.0`
- 否则调用 `timeout_rate_from_cases(task_id, source_code, entry_point, test_cases, time_limit=3.0)`
- 评估逻辑：
  - 若无 `test_cases` 或 `entry_point` 为空 => `0.0`
  - 若样本量大于 `_TIMEOUT_SAMPLE_LIMIT(=50)`，按等间隔索引抽样到 50 条
  - 每条输入用子进程执行目标函数，超时（`TimeoutExpired`）计入 `timeout_count`
  - 公式：`timeout_rate = timeout_count / len(eval_cases)`
  - 非超时运行错误（异常返回码）当前不计入超时
- 缓存：`_TIMEOUT_RATE_CACHE[(code_hash, task_id)]`

10. `pylint` code smell 列（`PYLINT_CODE_SMELL_COLUMNS`）
- 来源函数：`pylint_code_smell_counts`
- 逻辑：
  - 运行 `pylint` JSON 输出，仅启用目标 smell 规则：
    - `--disable=all`
    - `--enable=<逗号拼接规则列表>`
  - 统计每条消息 `symbol` 出现次数
- 降级：
  - `pylint` 不可用 => 所有列 `NaN`
  - JSON 解析失败 => 所有列 `NaN`
- 写出：
  - 非 `NaN` 值转为 `int`
  - `NaN` 原样保留
- 缓存：`_PYLINT_CACHE[code_hash]`

#### 3.4.3 最终行组装与输出值约束

- `row` 组装时包含：
  - 基础模型行为列：`pass_rate`, `run_err_rate`, `syn_err`, `gold_sim_CB`, `gold_sim_B`, `mut_sim_CB`, `mut_sim_B`, `timeout_rate`, `black_count`, `semgrep_count`
  - 全部 `pylint` smell 列
- 缺失处理：
  - `mut_sim_*` 在无对比模型时保留 `NaN`
  - 各工具列根据降级策略可能是 `NaN` 或 `0.0`
- 最终仅保留 `MODEL_FEATURE_COLUMNS` 中定义的键，保证列顺序稳定。

### 3.5 `pipeline.py`

- 读取模型错误 CSV（含 `Error ID`, `Task ID`, 语义/语法标签）。
- 调用 `build_model_feature_map` 与 `task_feature_map` 做行级合并。
- 将标签代码转换为 one-hot 向量。
- 按固定列顺序写出最终 CSV。

### 3.6 `utils.py`

- 通用 I/O：`load_json`、`load_jsonl`、`load_csv`、`write_csv`。
- 值标准化：`to_csv_value`（`None/NaN -> ""`）。
- 标识解析：`parse_task_id`、`parse_label_code`、`sanitize_model_name`。
- 工程辅助：`get_git_hash`、`write_simple_yaml`、`ensure_directory`。

## 4. 输入输出契约

### 输入

- `data/defects4codellm-main/data/*.csv`
- `data/defects4codellm-main/website/src/data/*.json`
- `data/human-eval-master/data/HumanEval.jsonl/...jsonl`

### 输出

- `work_dirs/<run_name>/config.yaml`
- `work_dirs/<run_name>/log.txt`
- `work_dirs/<run_name>/outputs/<model>_features.csv`

CSV 主键语义：以 `Error ID + Model + Task ID` 标识一条错误样本。

## 5. 当前设计决策与取舍

1. **单进程串行计算**：实现简单，便于复现；代价是全量运行耗时较长。
2. **缓存优先**：避免重复计算相似度与静态分析结果；代价是进程内内存占用增加。
3. **外部工具容错**：确保流程可跑通；代价是部分指标在缺依赖时信息量下降。
4. **固定列顺序输出**：便于下游建模和对齐；代价是新增特征需同步维护常量。

## 6. 已识别风险

1. `model_features.py` 体积较大，职责偏重，可读性与可维护性有压力。
2. 任务级与样本级特征混合在同一行，后续扩展需注意重复字段语义。
3. 外部工具版本差异可能影响 `black/semgrep/pylint` 指标稳定性。
4. 部分模块文档字符串存在历史编码问题，需统一清理。

## 7. 演进建议（与当前代码兼容）

1. 将 `model_features.py` 按“相似度/静态分析/超时评估”拆分子模块。
2. 引入 `dataclass` 描述中间结构，减少 `Dict[str, Any]` 弱类型传递。
3. 增加最小可复现实验集（少量 task），用于 CI 快速回归。
4. 在日志中增加依赖可用性快照（black/semgrep/pylint 版本与状态）。
