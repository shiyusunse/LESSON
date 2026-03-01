# LESSON
short for "Llm-generated codE Self-repair method baSed On causal aNalysis"

# 项目仓库结构
```
.
├── src/                          # LESSON 特征提取代码
│   ├── run_feature_extraction.py
│   └── lesson_feature_extractor/
├── data/                         # 数据集与原始数据
│   ├── defects4codellm-main/
│   └── human-eval-master/
├── work_dirs/                    # 实验运行输出（config/log/features）
├── CALL-main/                    # 对照/参考项目代码
├── 课件/                           # 课程材料
├── CLAUDE.md                     # 项目规范与常用命令
├── Task.md                       # 当前任务说明
├── README.md
├── *.zip                         # 备份/原始压缩包
└── .idea/                        # IDE 配置
```

# Feature Design

## Model度量
模型度量：标注是哪个模型输出的错误信息

## Task 复杂度度量
| No. | Feature | Description |
| --- | --- | --- |
| 1 | prompt_len| the number of words in the prompt |
| 2 | LOC | the length of the correct solution |
| 3 | ast_nodes | Number of AST nodes of correct solutions|

## Code metrics

| No. | Feature | Description |
| --- | --- | --- |
| 1 | pass_rate | The pass rate of test cases. |
| 2 | run_err_rate | The runtime error rate of test cases. |
| 3 | syn_err | The number of syntax errors revealed by tree-sitter |
| 4 | gold_sim_CB | The similarity in CodeBLEU |
| 5 | gold_sim_B | The similarity in BLEU |
| 6 | mut_sim_CB | The mutual similarity (in CodeBLEU) among the generated solutions. |
| 7 | mut_sim_B | The mutual similarity (in BLEU) among the generated solutions. |
| 8 | timeout_rate | The timeout rate of test cases. |
| 9 | black_count | The number of places reported by black where PEP8 is violated |
| 10 | semgrep_count | The number of potential security bugs revealed by Semgrep |

## Code smell metrics
| No. | Feature | Description |
| --- | --- | --- |
| 1 | invalid-name |  |
| 2 | singleton-comparison |  |
| 3 | unnecessary-lambda-assignment |  |
| 4 | non-ascii-name |  |
| 5 | disallowed-name |  |
| 6 | too-many-arguments |  |
| 7 | too-many-nested-blocks |  |
| 8 | too-many-boolean-expressions |  |
| 9 | consider-merging-isinstance |  |
| 10 | chained-comparison |  |
| 11 | broad-exception-caught |  |
| 12 | broad-exception-raised |  |
| 13 | unnecessary-lambda |  |

## Semantic Errors
| No. | Feature | Description |
| --- | --- | --- |
| 1 | Condition Error - Missing condition |  |
| 2 | Condition Error - Incorrect condition |  |
| 3 | Constant Value Error |  |
| 4 | Reference Error - Wrong method/variable |  |
| 5 | Reference Error - Undefined name |  |
| 6 | Operation/Calculation Error - Incorrect arithmetic operation |  |
| 7 | Operation/Calculation Error - Incorrect comparison operation |  |
| 8 | Gabrage Code - Only comments |  |
| 9 | Gabrage Code - Meaningless code snippet |  |
| 10 | Gabrage Code - Wrong (logical) direction |  |
| 11 | Incomplete Code/Missing Steps - Missing one step |  |
| 12 | Incomplete Code/Missing Steps - Missing multiple steps |  |
| 13 | Memory Error - Infinite loop |  |
## Syntactic Errors
| No. | Feature | Description |
| --- | --- | --- |
| 1 | Condition Error - If error |  |
| 2 | Loop Error - For error |  |
| 3 | Loop Error - While error |  |
| 4 | Return Error - Incorrect return value |  |
| 5 | Method Call Error - Incorrect function name |  |
| 6 | Method Call Error - Incorrect function arguments |  |
| 7 | Method Call Error - Incorrect method call target |  |
| 8 | Assignment Error - Incorrect constant |  |
| 9 | Assignment Error - Incorrect arithmetic |  |
| 10 | Assignment Error - Incorrect variable name |  |
| 11 | Assignment Error - Incorrect comparison |  |
| 12 | Import Error - Import error |  |
| 13 | Code Block Error - Incorrect code block |  |
| 14 | Code Block Error - Missing code block |  |
## Repair Effort
| No. | Feature | Description |
| --- | --- | --- |
| 1 | Levenshtein distance |  |
| 2 | Jaccard |  |
| 3 | CodeBERTScore |  |

| No. | Feature | Description |
| --- | --- | --- |
| 1 | single-line error |  |
| 2 | single-hunk error |  |
| 3 | multi-hunk error |  |

# Data structure

本项目当前使用两类数据：
1. `defects4codellm-main/data`：按模型划分的错误标注数据（CSV）
2. `human-eval-master/data`：HumanEval 原始任务与示例数据（JSONL/JSON/Python）

```text
data/
├── defects4codellm-main/
│   └── data/
│       ├── codegen-humaneval_error.csv
│       ├── gpt-3.5-humaneval_error.csv
│       ├── gpt-4-humaneval_error.csv
│       ├── incoder-humaneval_error.csv
│       ├── santacoder-humaneval_error.csv
│       └── starcoder-humaneval_error.csv
└── human-eval-master/
    └── data/
        ├── HumanEval.jsonl/
        │   └── human-eval-v2-20210705.jsonl
        ├── HumanEval.jsonl.gz
        ├── example.json
        ├── example.py
        ├── example_problem.jsonl
        └── example_samples.jsonl
```

## 1) `defects4codellm-main/data`（错误标注数据）

六个 CSV 的字段结构一致：

| Field | Description |
| --- | --- |
| `Error ID` | 错误样本编号（文件内编号） |
| `Model` | 生成代码的模型名称 |
| `Task ID` | HumanEval 任务编号（如 `0`, `1`, `26`） |
| `Semantic Characteristics` | 语义错误标签（如 `Aa2`, `Ae3`） |
| `Syntactic Characteristics` | 语法错误标签（如 `Ba1`, `Bg2`） |
| `Incorrect Code (Complete)` | 模型生成的错误代码全文 |
| `Ground Truth Code (Complete)` | 对应任务的参考正确代码全文 |

文件规模（行数）：

| File | Rows |
| --- | ---: |
| `codegen-humaneval_error.csv` | 129 |
| `gpt-3.5-humaneval_error.csv` | 52 |
| `gpt-4-humaneval_error.csv` | 20 |
| `incoder-humaneval_error.csv` | 182 |
| `santacoder-humaneval_error.csv` | 181 |
| `starcoder-humaneval_error.csv` | 123 |
| **Total** | **687** |

## 2) `human-eval-master/data`（原始任务数据）

核心文件：`HumanEval.jsonl/human-eval-v2-20210705.jsonl`。  
该文件每行是一个 JSON 对象，包含以下键：

| Key | Description |
| --- | --- |
| `task_id` | 任务标识（如 `HumanEval/0`） |
| `prompt` | 题目描述与函数签名 |
| `entry_point` | 待实现函数名 |
| `canonical_solution` | 官方参考实现 |
| `test` | 任务测试代码 |

补充说明：
- `*_humaneval_error.csv` 中的 `Task ID` 与 `HumanEval` 的 `task_id` 后缀一一对应（例如 `Task ID = 0` 对应 `HumanEval/0`）。
- `example.json`、`example_problem.jsonl`、`example_samples.jsonl`、`example.py` 为示例数据与示例代码，用于快速理解数据格式与评测流程。
