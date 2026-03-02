# LESSON
short for "Llm-generated codE Self-repair method baSed On causal aNalysis"

## 项目概述
- 该项目是基于因果分析技术的大模型生成代码自我修复方法的代码仓库。

## 项目结构
```
.
├── data/  # 其中，defects4codellm-main/data 是项目进行因果分析所使用的数据集
└── src/   # 存放实验所需的 Python 代码
```

## 开发强制要求
1. **虚拟环境强制要求：** 执行代码前检查是否已激活 conda 的 `LESSON` 虚拟环境；如果没有，需切换到 `LESSON` 环境，而不是创建新环境。
2. **禁止更改 `data` 文件夹下的内容。**
3. **优先使用 Python 语言。**

## GitHub 备份流程（强制）

触发条件：
- 用户说“备份到 github”“提交并推送”“同步远端备份”等同义表达。

执行要求：
1. 获取当前 HEAD：
   - `git rev-parse HEAD`
2. 定位最新工作目录（按目录名倒序）：
   - `Get-ChildItem work_dirs -Directory | Sort-Object Name -Descending | Select-Object -First 1 -ExpandProperty Name`
3. 将 `work_dirs/<latest>/log.txt` 中 `Git Hash:` 更新为当前 `HEAD`。
4. 执行提交与推送：
   - `git add -A`
   - `git commit -m "backup: sync repo and update latest work_dir git hash"`（若无变更则跳过）
   - `git push origin main`
5. 推送后校验：
   - 比较 `git rev-parse HEAD` 与 `git ls-remote origin refs/heads/main`
   - 输出“是否一致”的结论。
6. 禁止在仓库文件中写入或回显 PAT/token；认证仅走本机凭据管理器或 SSH。

## Git Push 稳定性保障（强制）
1. 推送前检查：
   - `git remote -v`
   - `git rev-parse --abbrev-ref HEAD`（必须为 `main`）
   - `Test-NetConnection github.com -Port 443`
2. 执行推送：
   - `git push origin main`
3. 若失败，按错误类型修复后重试一次：
   - 出现 `credential-manager-core is not a git command`：
     - `git config --global --unset-all credential.helper`
     - `git config --global credential.helper manager`
   - 出现网络连通性错误（443 不通）：
     - 先修复网络或代理，再执行推送（禁止无效重复重试）。
4. 推送后校验：
   - `git rev-parse HEAD`
   - `git ls-remote origin refs/heads/main`
   - 两者一致才算成功。
5. 安全要求：
   - 禁止在仓库文件中写入 PAT/token。
   - 认证仅使用系统凭据管理器或 SSH。
