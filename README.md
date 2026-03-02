# LESSON

LESSON = **Llm-generated codE Self-repair method baSed On causal aNalysis**。

## 项目结构

```text
.
├── src/
│   ├── run_feature_extraction.py
│   └── lesson_feature_extractor/
├── data/
│   ├── defects4codellm-main/
│   └── human-eval-master/
├── work_dirs/
├── CALL-main/
├── 课件/
└── README.md
```

## 特征设计

### 任务复杂度特征

| No. | Feature | Description |
| --- | --- | --- |
| 1 | prompt_len | prompt 词数 |
| 2 | LOC | 参考解法非空行数 |
| 3 | ast_nodes | 参考解法 AST 节点数 |

### 代码度量特征

| No. | Feature | Description |
| --- | --- | --- |
| 1 | pass_rate | 测试通过率 |
| 2 | run_err_rate | 运行错误率 |
| 3 | syn_err | 语法错误标记 |
| 4 | gold_sim_CB | 与参考解法的 CodeBLEU 相似度 |
| 5 | gold_sim_B | 与参考解法的 BLEU 相似度 |
| 6 | mut_sim_CB | 与其他模型输出的平均 CodeBLEU |
| 7 | mut_sim_B | 与其他模型输出的平均 BLEU |
| 8 | timeout_rate | 超时率（抽样估计） |
| 9 | black_count | black 检出的差异块数量 |
| 10 | semgrep_count | semgrep 检出的潜在安全问题数量 |

### 代码异味特征（Pylint）

| No. | Feature |
| --- | --- |
| 1 | invalid-name |
| 2 | singleton-comparison |
| 3 | unnecessary-lambda-assignment |
| 4 | non-ascii-name |
| 5 | disallowed-name |
| 6 | too-many-arguments |
| 7 | too-many-nested-blocks |
| 8 | too-many-boolean-expressions |
| 9 | consider-merging-isinstance |
| 10 | chained-comparison |
| 11 | broad-exception-caught |
| 12 | broad-exception-raised |
| 13 | unnecessary-lambda |

这 13 个异味特征在输出 CSV 中位于 `semgrep_count` 与语义特征 `Aa1` 之间。

### 语义与语法 one-hot 特征

- 语义特征列：`Aa1` ~ `Ag1`
- 语法特征列：`Ba1` ~ `Bg2`

## 数据来源

- `data/defects4codellm-main/data`：按模型拆分的错误标注 CSV。
- `data/defects4codellm-main/website/src/data`：模型代码、测试结果、测试输入等 JSON。
- `data/human-eval-master/data/HumanEval.jsonl/human-eval-v2-20210705.jsonl`：HumanEval 原始任务。

## 运行方式

在项目根目录执行：

```bash
python src/run_feature_extraction.py
```

常用参数：

- `--run-name`：指定输出目录名。
- `--models`：指定模型列表（逗号分隔）。
- `--encoding`：文件编码（默认 `utf-8`）。

## 输出结构

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
    └── starcoder_features.csv
```

## 依赖说明

- `pylint`：用于计算 13 个 code smell 特征。
- `semgrep`：用于计算 `semgrep_count`。

当前实现具备回退策略：

- `semgrep` 不可用或执行失败时，`semgrep_count` 回退为 `0.0`。
- `pylint` 不可用时，code smell 特征会写空值。
