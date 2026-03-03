# LESSON
short for "Llm-generated codE Self-repair method baSed On causal aNalysis"

## 项目概述

本项目用于研究基于因果分析的大模型代码自修复方法，并构建统一的特征提取流程与可审查输出。

## 项目目录结构

```text
.
├── data/                              # defects4codellm 与 HumanEval 数据
├── src/                               # 特征提取主代码（Python）
├── test/                              # 调试与人工审查脚本
├── design.md                          # 设计文档
├── plan.md                            # 实施计划文档
├── test.md                            # 测试与验证记录文档
└── README.md                          # 项目说明文档
```

## 环境与运行准备

1. 准备并激活 `conda` 环境 `LESSON`。
2. 确认 `data` 目录数据已就绪。
3. 在仓库根目录运行 Python 脚本。
4. 开始开发前先阅读 `README.md`。

## 三文档协作流程（design/plan/test）

- 任何 `src/**/*.py` 相关改动前，必须先同步更新：`design.md`、`plan.md`、`test.md`。
- 推荐流程：
1. 在 `design.md` 记录设计口径和边界。
2. 在 `plan.md` 写执行方案，并设置 `Status: DRAFT`。
3. 评审通过后，将 `Status` 改为 `APPROVED`，再进行代码改动。
4. 每一批改动完成后回写 `plan.md` 的执行结果。
5. 验证过程与结论必须记录到 `test.md`。

## Plan 状态门禁（强制）

`plan.md` 顶部必须包含：
- `Status: DRAFT | APPROVED`
- `Task: <任务描述>`
- `Updated: <YYYY-MM-DD HH:MM>`

约束规则：
1. 当 `Status != APPROVED` 时，只允许修改 `design.md`、`plan.md`、`test.md`，禁止修改 `src/**/*.py`。
2. 当任务范围变化或新增需求时，必须先更新 `plan.md` 并将状态置为 `DRAFT`。
3. 代码改动完成后，必须回填 `plan.md` 的结果与最新更新时间。

## plan.md 变更批次模板

在 `plan.md` 中追加：
- `Change Batch: <本批次名称>`
- `Goal: <本批次目标>`
- `Files to modify: <涉及文件>`
- `Steps: <执行步骤>`
- `Risks: <主要风险>`
- `Rollback: <回滚方案>`
- `Done Criteria: <完成标准>`

## test.md 记录模板

每条验证记录建议包含：
- `Hypothesis: ...`
- `Action/Command: ...`
- `Observation: ...`
- `Conclusion: ...`
- `Next Step: ...`

## README 同步与质量规则

1. 任何代码或流程改动后，需同步更新 `README.md` / `README*.md`。
2. README 内容必须与当前实现一致，避免文档与实现脱节。
3. README 必须为可读中文，禁止乱码。
4. README 文件编码必须为 `UTF-8`（无 BOM）。
5. README 改动后必须执行下方检查脚本。

### README 乱码检查（必做）

```bash
python - <<'PY'
from pathlib import Path
import re

files = [Path('README.md')] + list(Path('.').glob('README*.md'))
bad_tokens = ["\u9352", "\u9286", "\u9239", "\u951f", chr(0xFFFD), "?" * 3]
failed = []

for p in files:
    if not p.exists():
        continue
    t = p.read_text(encoding='utf-8')
    has_cn = bool(re.search(r'[\u4e00-\u9fff]', t))
    has_bad = any(tok in t for tok in bad_tokens)
    if (not has_cn) or has_bad:
        failed.append(str(p))

print('FAILED:', len(failed))
for x in failed:
    print(x)
if failed:
    raise SystemExit(1)
PY
```

## GitHub 备份规范

目标：在开始下一轮修改前，确保当前改动已推送到 GitHub 远端。

建议步骤：
1. 查看当前提交：`git rev-parse HEAD`
2. 获取最新 `work_dirs` 子目录：
   - `Get-ChildItem work_dirs -Directory | Sort-Object Name -Descending | Select-Object -First 1 -ExpandProperty Name`
3. 检查 `work_dirs/<latest>/log.txt` 中 `Git Hash` 是否与 `HEAD` 一致。
4. 提交并推送：
   - `git add -A`
   - `git commit -m "backup: sync repo and update latest work_dir git hash"`
   - `git push origin main`
5. 双向校验：
   - `git rev-parse HEAD`
   - `git ls-remote origin refs/heads/main`

## Git Push 排障流程

1. 基础检查：
   - `git remote -v`
   - `git rev-parse --abbrev-ref HEAD`（应为 `main`）
   - `Test-NetConnection github.com -Port 443`
2. 重试推送：`git push origin main`
3. 常见问题修复：
   - 若出现 `credential-manager-core is not a git command`：
     - `git config --global --unset-all credential.helper`
     - `git config --global credential.helper manager`
4. 推送后再次校验本地与远端哈希一致。
5. 如仍失败，优先检查 PAT/token，或改用 SSH。


## README 受保护章节规则（强制）

目标：确保 `README.md` 中“特征设计”和“数据集结构”两个受保护章节仅允许就地修改，不可整段删除。

必须保留的标题（全文一致）：
- `## 特征设计（受保护）`
- `## 数据集结构（受保护）`

必须保留的标记：
- `<!-- PROTECTED:FEATURE_DESIGN START -->`
- `<!-- PROTECTED:FEATURE_DESIGN END -->`
- `<!-- PROTECTED:DATASET_STRUCTURE START -->`
- `<!-- PROTECTED:DATASET_STRUCTURE END -->`

规则：
1. 禁止删除任何必需标记。
2. 禁止删除 START/END 之间的完整区块。
3. 允许在受保护区块内部增删改具体条目。
4. 涉及 `README.md` 的提交前必须执行下方检查脚本。

### README 受保护章节检查（必做）

```bash
python - <<'PY'
from pathlib import Path

readme = Path('README.md')
text = readme.read_text(encoding='utf-8')

required_titles = [
    '## 特征设计（受保护）',
    '## 数据集结构（受保护）',
]
required_markers = [
    '<!-- PROTECTED:FEATURE_DESIGN START -->',
    '<!-- PROTECTED:FEATURE_DESIGN END -->',
    '<!-- PROTECTED:DATASET_STRUCTURE START -->',
    '<!-- PROTECTED:DATASET_STRUCTURE END -->',
]

missing = [x for x in required_titles + required_markers if x not in text]
print('MISSING:', len(missing))
for item in missing:
    print(item)
if missing:
    raise SystemExit(1)
print('README protected sections check: PASS')
PY
```

## README Protected Blocks (Mandatory)

Scope:
- File: `README.md`
- Protected blocks must remain in the file and can only be edited in-place.

Required markers (must all exist):
- `<!-- PROTECTED:FEATURE_DESIGN START -->`
- `<!-- PROTECTED:FEATURE_DESIGN END -->`
- `<!-- PROTECTED:DATASET_STRUCTURE START -->`
- `<!-- PROTECTED:DATASET_STRUCTURE END -->`

Rules:
1. Never delete any required marker.
2. Never delete the full content block between START/END markers.
3. You may revise or extend content inside protected blocks.
4. Before finishing any README-related change, run the check below.

### Protected blocks check (required)

```bash
python - <<'PY'
from pathlib import Path
import re

text = Path('README.md').read_text(encoding='utf-8')
markers = [
    '<!-- PROTECTED:FEATURE_DESIGN START -->',
    '<!-- PROTECTED:FEATURE_DESIGN END -->',
    '<!-- PROTECTED:DATASET_STRUCTURE START -->',
    '<!-- PROTECTED:DATASET_STRUCTURE END -->',
]
missing = [m for m in markers if m not in text]
if missing:
    print('MISSING MARKERS:', len(missing))
    for m in missing:
        print(m)
    raise SystemExit(1)

pairs = [
    ('FEATURE_DESIGN', r'<!-- PROTECTED:FEATURE_DESIGN START -->(.*?)<!-- PROTECTED:FEATURE_DESIGN END -->'),
    ('DATASET_STRUCTURE', r'<!-- PROTECTED:DATASET_STRUCTURE START -->(.*?)<!-- PROTECTED:DATASET_STRUCTURE END -->'),
]
for name, pattern in pairs:
    m = re.search(pattern, text, re.S)
    if not m:
        print(f'BLOCK NOT FOUND: {name}')
        raise SystemExit(1)
    if not m.group(1).strip():
        print(f'BLOCK EMPTY: {name}')
        raise SystemExit(1)

print('README protected blocks check: PASS')
PY
```
