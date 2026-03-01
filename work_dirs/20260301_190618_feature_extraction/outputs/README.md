# Outputs 说明

本目录包含按模型拆分的特征文件，每个文件一行对应一个错误样本。

## 文件列表

- `codegen_16b_features.csv`：CodeGen-16B 错误样本特征
- `incoder_1b_features.csv`：InCoder-1B 错误样本特征
- `gpt_3_5_features.csv`：GPT-3.5 错误样本特征
- `gpt_4_features.csv`：GPT-4 错误样本特征
- `santacoder_features.csv`：SantaCoder 错误样本特征
- `starcoder_features.csv`：StarCoder 错误样本特征

## 行粒度

- 每一行表示一个错误样本（来自 `defects4codellm-main/data/*_humaneval_error.csv`）。
- `Task ID` 对应 HumanEval 任务编号。

## 字段分组与含义

### 1) 基础标识字段

- `Error ID`：错误样本编号（原始数据内编号）
- `Model`：模型名
- `Task ID`：HumanEval 任务编号
- `Semantic Characteristics`：原始语义错误标签文本
- `Syntactic Characteristics`：原始语法错误标签文本

### 2) Task complexity 字段

- `Prompt length`：prompt 词数（按空白分词）
- `LOC`：参考解代码非空行数
- `Number of AST nodes of correct solutions`：参考解（含 prompt 上下文）AST 节点数

### 3) Model 度量字段

- `pass_rate`：通过测试比例（通过用例数 / 总用例数）
- `run_err_rate`：`1 - pass_rate`
- `syn_err`：语法错误标志（可解析为 Python AST 为 `0`，否则为 `1`）
- `gold_sim_B`：生成代码与参考代码的 BLEU 相似度（简化实现）
- `gold_sim_CB`、`mut_sim_CB`、`mut_sim_B`、`timeout_rate`、`black_count`、`semgrep_count`：当前数据集中无直接可恢复字段，列保留为空

### 4) Semantic Errors one-hot 字段

以下列均为 `0/1`，列名直接使用 `Error Code`：

- `Aa1`
- `Aa2`
- `Ab1`
- `Ac1`
- `Ac2`
- `Ad1`
- `Ad4`
- `Ae1`
- `Ae2`
- `Ae3`
- `Af1`
- `Af2`
- `Ag1`

### 5) Syntactic Errors one-hot 字段

以下列均为 `0/1`，列名直接使用 `Error Code`：

- `Ba1`
- `Bb1`
- `Bb2`
- `Bc2`
- `Bd1`
- `Bd2`
- `Bd3`
- `Be4`
- `Be1`
- `Be5`
- `Be6`
- `Bf1`
- `Bg1`
- `Bg2`

## one-hot 取值规则

- `1`：该样本属于该错误类型
- `0`：该样本不属于该错误类型

## 空值说明

- CSV 中空字符串表示该特征在当前数据版本下不可直接计算或未提供。

## 当前无法计算的 feature 列表

以下特征在当前数据版本中缺少直接计算所需的原始输入或中间结果，因此在 CSV 中留空：

- `gold_sim_CB`：缺少计算 CodeBLEU 所需的完整评估配置与依赖结果。
- `mut_sim_CB`：缺少多候选生成集合及其 CodeBLEU 两两比较结果。
- `mut_sim_B`：缺少多候选生成集合及其 BLEU 两两比较结果。
- `timeout_rate`：缺少逐测试用例的超时标记或执行日志。
- `black_count`：缺少对每个样本运行 `black` 后的违规计数结果。
- `semgrep_count`：缺少对每个样本运行 `semgrep` 后的告警计数结果。
