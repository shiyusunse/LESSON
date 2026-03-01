# LESSON
short for "Llm-generated codE Self-repair method baSed On causal aNalysis"

## 沟通与语言规范

- 永远使用简体中文进行思考和对话
- 代码与术语： 所有代码实体（变量名、函数名、类名等）及技术术语必须保持英文原文。
- 注释规范： 代码注释应使用中文，遵循 PEP 257 文档字符串规范。
- 类型注解强制要求： 所有函数和方法必须添加类型注解，提高代码可读性和IDE支持。

## 项目概述
- 该项目是基于因果分析技术的大模型生成代码自我修复方法的代码仓库

## 项目结构
```
.
├── data/ # 其中，defects4codellm-main/data是项目进行因果分析所使用的数据集
└── src/ # 存放实验所需的python代码 
```

## 编码规范
1.**配置解耦(Config Decoupling)**

    严禁在代码里“硬编码”超参数（Hard Code）。比如 lr = 0.001 这种写法，一旦修改忘记改回来，这组实验就成了“黑箱”。

    规范操作： 所有可变参数必须通过 argparse（命令行参数）传入。

2.**标准化目录结构 (Structure)**

    不要把所有日志都堆在根目录。建立一个层级清晰的 work_dirs。

    命名规范： 时间戳_模型名称_关键改动，如20251126_resnet50_add_se_block_lr0.01

    目录内容清单： 每个实验文件夹下应自动生成config.yaml：当时的配置副本；log.txt：完整的日志。

3.**代码指纹 (Git Commit ID)**

    这是大多数人容易忽略，但最关键的一步。 光记录参数不够，必须记录“跑这份参数时的代码长什么样”。
    
    规范操作： 加入一段自动记录 Git Commit Hash 的代码。
    
    建议在日志开头打印： Current Code Version: [Git Hash]
    这样，哪怕后来代码改得面目全非，只要 git checkout [Hash]，就能找回当时那一刻的代码环境。

4.**日志内容核对表 (Checklist)**

    你的 log.txt 开头，必须包含以下信息，缺一不可：

    Command： 运行这行代码的完整指令。

    Environment： Python 版本。

    Seed： 当前使用的随机种子。

    Git Hash： 代码版本号。

    Config： 所有超参数的列表。

5.**模块化编程**

    可读性优先 (Readability First)： 遵循 "The Zen of Python" - 代码应该像诗一样优美，简洁胜过复杂。

    DRY (Don't Repeat Yourself)： 通过函数、类、模块和装饰器来消除重复，充分利用 Python 的抽象能力。

    高内聚，低耦合 (High Cohesion, Low Coupling)： 利用 Python 的模块系统和包结构实现清晰的代码组织。将程序的功能拆分成独立的模块（通常放在不同的源文件中），每个模块负责特定的任务，然后通过一个主文件（如 main.py）来统一调用和组织这些模块，从而实现整体功能



## 常用命令
### 环境管理
```bash
# 创建虚拟环境
python -m venv venv

# 安装依赖
pip install -r requirements.txt

# 生成依赖文件
pip freeze > requirements.txt

# 使用 poetry 管理依赖
poetry init
poetry add package_name
poetry install
```

### 备份

## 开发强制要求
1. **虚拟环境强制要求：** 所有 Python 项目必须使用虚拟环境LESSON
2. **禁止更改data文件夹下的内容**
3. **优先使用python语言**
4. **修改代码的同时同步修改对应的REAMDE文档**

