# LESSON

LESSON 是 **Llm-generated codE Self-repair method baSed On causal aNalysis** 的缩写。

## 项目概述

该项目用于研究基于因果分析的大模型代码自修复方法，并构建统一的特征提取流程与可审查测试输出。

## 项目结构

```text
.
├── data/
│   ├── defects4codellm-main/
│   │   └── data/                       # 各模型错误样本 CSV
│   └── human-eval-master/
│       └── data/
│           └── HumanEval.jsonl/
│               └── human-eval-v2-20210705.jsonl
├── src/                                 # 特征提取主代码
├── test/                                # 人工审查与单元测试
├── design.md                            # 设计文档
├── plan.md                              # 实施计划文档
└── test.md                              # 调试假设与验证记录
```

<!-- PROTECTED:FEATURE_DESIGN START -->
## 特征设计（受保护）

说明：本节是受保护章节，后续只能在本节内增补或修订内容，禁止删除本节标题与整体结构。

### 1. 任务复杂度特征（Task Features）

当前实现 3 个任务复杂度指标（见 `TASK_FEATURE_COLUMNS`）：

1. `prompt_len`
- 输入：HumanEval 的 `prompt`。
- 处理：先移除 doctest 示例行，再使用 `CountVectorizer` 统计 token 累加和。
- 当前参数：

```python
from sklearn.feature_extraction.text import CountVectorizer

vectorizer = CountVectorizer(
    lowercase=False,
    min_df=1,
    token_pattern=r"\b\w+\b",
)
X = vectorizer.fit_transform(java_contents)
feature_names = vectorizer.get_feature_names_out()
token_sum = int(X.sum())
```

2. `LOC`
- 定义：`Ground Truth Code (Complete)` 非空行数减去原始 `prompt` 非空行数。

3. `ast_nodes`
- 定义：对 `Ground Truth Code (Complete)` 做 AST 解析后，统计 `ast.walk` 节点总数。
- 人工审查 JSON 额外输出：`ast_parse_ok`、`ast_parse_error`、`ast_root_type`、`ast_structure_dump`、`node_type_counts`。

### 2. 模型行为特征（Model Features）

模型行为特征由 `MODEL_FEATURE_COLUMNS` 定义，包含：

- 代码特征：`pass_rate`, `run_err_rate`, `syn_err`, `gold_sim_CB`, `gold_sim_B`, `mut_sim_CB`, `mut_sim_B`, `timeout_rate`, `black_count`, `semgrep_count`
- Pylint code smell 计数（异味特征）：`invalid-name`, `singleton-comparison`, `unnecessary-lambda-assignment`, `non-ascii-name`, `disallowed-name`, `too-many-arguments`, `too-many-nested-blocks`, `too-many-boolean-expressions`, `consider-merging-isinstance`, `chained-comparison`, `broad-exception-caught`, `broad-exception-raised`, `unnecessary-lambda`

### 3. 错误类型（Semantic / Syntactic）

- 语义特征：`Aa1 ... Ag1`
- 句法特征：`Ba1 ... Bg2`

以上编码映射在 `constants.py` 中由 `SEMANTIC_CODE_TO_FEATURE` 与 `SYNTACTIC_CODE_TO_FEATURE` 维护。
<!-- PROTECTED:FEATURE_DESIGN END -->

<!-- PROTECTED:DATASET_STRUCTURE START -->
## 数据集结构（受保护）

说明：本节是受保护章节，后续只能在本节内增补或修订内容，禁止删除本节标题与整体结构。

### 1. defects4codellm 数据

路径：`data/defects4codellm-main/data/`

包含按模型拆分的错误样本 CSV：
- `codegen-humaneval_error.csv`
- `incoder-humaneval_error.csv`
- `gpt-3.5-humaneval_error.csv`
- `gpt-4-humaneval_error.csv`
- `santacoder-humaneval_error.csv`
- `starcoder-humaneval_error.csv`

字段中关键列包括：`Error ID`、`Model`、`Task ID`、`Ground Truth Code (Complete)`。

### 2. HumanEval 数据

主路径：`data/human-eval-master/data/HumanEval.jsonl/human-eval-v2-20210705.jsonl`

关键字段包括：`task_id`、`prompt`、`canonical_solution`。

### 3. Ground Truth 汇总策略

- 汇总多模型 CSV 后按 `task_id` 做一致性校验。
- 同一 `task_id` 的 `Ground Truth Code (Complete)` 若冲突，直接报错（fail fast）。
- 缺失 ground truth 同样报错，阻止产生错误特征。

### 4. website JSON 数据（模型测试结果与测试用例）

路径：`data/defects4codellm-main/website/src/data/`

#### 4.1 模型测试结果 JSON（`*_test.json`）

文件示例：
- `codegen_test.json`
- `incoder_test.json`
- `chatgpt_test.json`
- `gpt4_test.json`
- `santacoder_test.json`
- `starcoder_test.json`

单条记录结构：

```json
{
  "Task ID": 32,
  "base": [0, 1, 2],
  "plus": []
}
```

字段说明：
- `Task ID`：任务编号（可能是整数或 `HumanEval_1` / `HumanEval/1` 形式）。
- `base`：通过的基础测试用例结果集合。
- `plus`：通过的扩展测试用例结果集合。

解析口径：
- `pass_count = len(base) + len(plus)`。

#### 4.2 测试用例总表（`HumanEvalPlus-test.json`）

单条记录结构：

```json
{
  "Task ID": "HumanEval_1",
  "base_input": ["..."],
  "plus_input": ["..."]
}
```

字段说明：
- `base_input`：基础测试输入列表。
- `plus_input`：扩展测试输入列表。

解析口径：
- `total_count = len(base_input) + len(plus_input)`。
- 超时评估用例输入为 `base_input + plus_input`（大于采样上限时会均匀抽样）。

#### 4.3 失败任务总表（`HumanEvalFailed.json`）

结构说明：
- 顶层为模型名到失败任务列表的映射，例如：`{"CodeGen-16B": [1, 3, 5, ...], ...}`。
- 当前用于 `pass_rate/run_err_rate` 计算的 `fail_count` 直接取该模型失败任务列表长度。
- `total_count` 当前固定为 `164`。

#### 4.4 代码文本 JSON（`*_code.json` 与 `gt_code.json`）

- `*_code.json`：各模型生成代码列表。
- `gt_code.json`：同任务对应的 Ground Truth 代码列表。
- 两者均按索引与 `task_id` 对齐。

#### 4.5 指标计算映射关系

- `fail_count = len(HumanEvalFailed.json[model])`
- `total_count = 164`（固定常量）
- `pass_rate = 1 - fail_count / total_count`
- `run_err_rate = fail_count / total_count`
- `Task ID` 会先做标准化解析，统一转成整数后再合并（支持 `HumanEval_1` / `HumanEval/1` / `1`）。
<!-- PROTECTED:DATASET_STRUCTURE END -->

## 依赖与环境

- 推荐使用 `conda` 的 `LESSON` 环境。
- `prompt_len` 依赖 `scikit-learn`：

```bash
conda run -n LESSON python -m pip install scikit-learn
```

## 人工审查命令

```bash
python test/test_task_features.py --model CodeGen-16B --error-id 13
```

执行后会在 `test/` 目录生成 JSON 文件，文件名包含时间戳，例如：
`task_features_audit_codegen_16b_error_13_task_26_20260303_171530.json`。

输出包括：
- `prompt_len` 的 prompt 清洗、分词与结果
- `LOC` 的文本与非空行识别过程
- `ast_nodes` 的 AST 解析状态、节点计数与 AST 结构文本
