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

## 常用命令
### 备份
```powershell
# 需要先准备 GitHub PAT（classic，至少勾选 repo 权限）
$env:GITHUB_USER = "shiyusunse"
$env:GITHUB_REPO = "LESSON"
$env:GITHUB_TOKEN = "<YOUR_GITHUB_PAT>"

# 若尚未初始化仓库，则初始化并首次提交
if (-not (Test-Path .git)) { git init -b main }
git add .
git commit -m "backup: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" 2>$null

# 首次备份时创建远程仓库（已存在会返回 422，可忽略）
$headers = @{
    Authorization = "Bearer $env:GITHUB_TOKEN"
    Accept        = "application/vnd.github+json"
    "User-Agent"  = "LESSON-backup-script"
}
$payload = @{ name = $env:GITHUB_REPO; private = $false; auto_init = $false } | ConvertTo-Json
try {
    Invoke-RestMethod -Method Post -Uri "https://api.github.com/user/repos" -Headers $headers -Body $payload -ContentType "application/json" | Out-Null
} catch {}

# 推送到 GitHub
git remote remove origin 2>$null
git remote add origin "https://github.com/$($env:GITHUB_USER)/$($env:GITHUB_REPO).git"
$auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$($env:GITHUB_USER):$($env:GITHUB_TOKEN)"))
git -c http.extraHeader="Authorization: Basic $auth" push -u origin main
```
