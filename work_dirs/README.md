# work_dirs 说明

本目录用于保存每次特征提取任务的运行产物。

## 目录命名

默认命名格式：

- `<YYYYMMDD_HHMMSS>_feature_extraction`

也可通过 `--run-name` 指定固定目录名。

## 如何生成

在项目根目录执行：

```bash
python src/run_feature_extraction.py
```

示例（指定目录名）：

```bash
python src/run_feature_extraction.py --run-name 20260302_demo_feature_extraction
```

## 单次运行产物

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

- `config.yaml`：本次运行参数快照。
- `log.txt`：命令、Python 版本、git hash 与输出汇总。
- `outputs/*.csv`：按模型输出的特征文件。

## 字段说明（关键）

- `timeout_rate`：基于测试输入抽样执行后得到的超时率估计值。
- `semgrep_count`：semgrep 检出的潜在安全问题数量。
- 13 个 code smell 列：由 pylint 统计得到。

## 依赖与回退

- 若 `semgrep` 不可用或执行失败，`semgrep_count` 回退为 `0.0`。
- 若 `pylint` 不可用，13 个 code smell 列会为空。

## 最近一次完整产出

- `work_dirs/20260302_180229_feature_extraction`
