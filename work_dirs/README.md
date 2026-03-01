# work_dirs 使用说明

本文档说明如何生成 `work_dirs` 下的特征提取结果。

## 1. 功能入口

- 脚本入口：`src/run_feature_extraction.py`
- 作用：从 `defects4codellm-main` 与 `human-eval-master` 读取数据，提取以下特征并按模型输出 CSV：
  - `Task complexity`：`prompt_len`、`LOC`、`ast_nodes`
  - `Model`：`pass_rate`、`run_err_rate`、`syn_err`、`gold_sim_CB`、`gold_sim_B`、`mut_sim_CB`、`mut_sim_B`、`black_count`（`timeout_rate` 与 `semgrep_count` 视环境与数据可用性）
  - `Semantic Errors` one-hot（`Aa1`~`Ag1`）
  - `Syntactic Errors` one-hot（`Ba1`~`Bg2`）

## 2. 运行命令

在项目根目录执行：

```bash
python src/run_feature_extraction.py
```

说明：

- 不传 `--run-name`：自动创建新目录，如 `work_dirs/20260301_192312_feature_extraction`
- 传 `--run-name`：覆盖或写入指定目录

示例（覆盖指定目录）：

```bash
python src/run_feature_extraction.py --run-name 20260301_192312_feature_extraction
```

## 3. 主要参数

- `--defects-data-dir`：默认 `data/defects4codellm-main/data`
- `--website-data-dir`：默认 `data/defects4codellm-main/website/src/data`
- `--humaneval-jsonl-path`：默认 `data/human-eval-master/data/HumanEval.jsonl/human-eval-v2-20210705.jsonl`
- `--output-root`：默认 `work_dirs`
- `--run-name`：默认空（自动时间戳）
- `--models`：默认 `CodeGen-16B,InCoder-1B,GPT-3.5,GPT-4,SantaCoder,StarCoder`
- `--encoding`：默认 `utf-8`

## 4. 输出结构

每次运行会生成：

```text
work_dirs/<run_name>/
├── config.yaml
├── log.txt
└── outputs/
    ├── codegen_16b_features.csv
    ├── incoder_1b_features.csv
    ├── gpt_3_5_features.csv
    ├── gpt_4_features.csv
    ├── santacoder_features.csv
    ├── starcoder_features.csv
    └── README.md
```

- `config.yaml`：本次运行参数快照
- `log.txt`：运行命令、Python 版本、seed、git hash、输出行数摘要
- `outputs/*.csv`：每模型一个文件，每行一个错误样本

## 5. 复现建议

- 在同一 Python 环境、同一输入数据下重复运行可复现同样的行数与字段结构。
- 如果只想更新同一批输出，使用固定 `--run-name`。

## 6. 每个 feature 的生成方式

下表按最终 CSV 字段说明生成逻辑（数据来源与公式）。

### 6.1 基础字段

- `Error ID`：直接来自 `*_humaneval_error.csv` 的 `Error ID`。
- `Model`：直接来自 `*_humaneval_error.csv` 的 `Model`（或模型配置名）。
- `Task ID`：直接来自 `*_humaneval_error.csv` 的 `Task ID`，并标准化为整数。
- `Semantic Characteristics`：直接来自 `*_humaneval_error.csv`。
- `Syntactic Characteristics`：直接来自 `*_humaneval_error.csv`。

### 6.2 Task complexity

- `prompt_len`
  - 数据来源：`data/human-eval-master/data/HumanEval.jsonl/human-eval-v2-20210705.jsonl` 的 `prompt`。
  - 计算：按空白分词后计数（`\S+` token 数）。
- `LOC`
  - 数据来源：同上文件的 `canonical_solution`。
  - 计算：非空行数。
- `ast_nodes`
  - 数据来源：`prompt + canonical_solution` 拼接后的正确代码上下文。
  - 计算：Python `ast.parse` 后 `ast.walk` 节点总数；若解析失败则记为 `0`。

### 6.3 Model 度量

- `pass_rate`
  - 数据来源：
    - `website/src/data/<model>_test.json`（每题 `base`、`plus` 通过索引）
    - `website/src/data/HumanEvalPlus-test.json`（每题 `base_input`、`plus_input` 总测试数）
  - 计算：`(len(base) + len(plus)) / (len(base_input) + len(plus_input))`。
- `run_err_rate`
  - 计算：`1 - pass_rate`。
- `syn_err`
  - 数据来源：`website/src/data/<model>_code.json` 中该 `Task ID` 的生成代码。
  - 计算：代码能被 Python AST 解析则为 `0`，否则为 `1`。
- `gold_sim_B`
  - 数据来源：
    - 生成代码：`website/src/data/<model>_code.json`
    - 参考代码：`website/src/data/gt_code.json`
  - 计算：脚本内实现的简化 BLEU（1~4 gram，+1 平滑，含 brevity penalty）。
- `gold_sim_CB`
  - 数据来源：同 `gold_sim_B`。
  - 计算：参考 `CALL-main` 的 CodeBLEU 组合思想，实现可落地版：
    - `ngram`：简化 BLEU
    - `weighted`：Python 关键词加权 unigram 匹配
    - `syntax`：AST 子树匹配率
    - `dataflow`：当前置 `0`
    - 最终：`0.25 * (ngram + weighted + syntax + dataflow)`。
- `mut_sim_B`
  - 数据来源：同一 `Task ID` 下“其他模型”的生成代码（`website/src/data/*_code.json`）。
  - 计算：当前模型代码与其他模型代码逐一计算 BLEU 后取平均。
- `mut_sim_CB`
  - 数据来源：同 `mut_sim_B`。
  - 计算：当前模型代码与其他模型代码逐一计算可落地版 CodeBLEU 后取平均。
- `black_count`
  - 数据来源：当前模型生成代码文本。
  - 计算：调用 `black --diff`，统计 diff hunk 数（`@@` 数量 / 2）。

### 6.4 Semantic one-hot（列名为 Error Code）

- 字段：`Aa1,Aa2,Ab1,Ac1,Ac2,Ad1,Ad4,Ae1,Ae2,Ae3,Af1,Af2,Ag1`
- 数据来源：`Semantic Characteristics` 文本中的错误码前缀（如 `Ae3 Wrong ...`）。
- 计算：匹配到对应 code 列记 `1`，其余记 `0`。

### 6.5 Syntactic one-hot（列名为 Error Code）

- 字段：`Ba1,Bb1,Bb2,Bc2,Bd1,Bd2,Bd3,Be4,Be1,Be5,Be6,Bf1,Bg1,Bg2`
- 数据来源：`Syntactic Characteristics` 文本中的错误码前缀（如 `Bg1 Incorrect ...`）。
- 计算：匹配到对应 code 列记 `1`，其余记 `0`。

## 7. 当前无法生成的 feature

这些字段在项目根目录 `README.md` 的 `Feature Design` 下，归属于 **Code metrics** 类。

以下字段在当前数据与实现条件下无法直接可靠计算，CSV 中留空：

- `timeout_rate`
  - 原因：当前数据只提供“通过用例索引”，不提供失败原因，无法区分“超时失败”与“非超时失败”。
- `semgrep_count`
  - 原因：当前环境缺少 `semgrep` 运行时（`python -m semgrep` 不可用）。
