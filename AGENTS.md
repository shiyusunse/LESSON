# LESSON
short for "Llm-generated codE Self-repair method baSed On causal aNalysis"

## 项目概述
- 该项目是基于因果分析技术的大模型生成代码自我修复方法的代码仓库

## 项目结构
```
.
├── data/ # 其中，defects4codellm-main/data是项目进行因果分析所使用的数据集
└── src/ # 存放实验所需的python代码 
```

## 开发强制要求
1. **虚拟环境强制要求：** 执行代码前检查是否conda已激活LESSON虚拟环境，没有的话帮我切换到LESSON环境，而不是自己创建虚拟环境
2. **禁止更改data文件夹下的内容**
3. **优先使用python语言**

## GitHub 备份流程（强制）

触发条件：
- 用户说“备份到github”“提交并推送”“同步远端备份”等同义表达。

执行要求：
1. 获取当前 HEAD：`git rev-parse HEAD`
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
