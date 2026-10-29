# Name2SMILES 数据集

[English](README.md) | **简体中文**

化学领域的大多数语言模型基准只考察模型能否读懂 SMILES。本项目考察更难的
方向：只给一个化合物名称，模型能否写出正确结构。项目从 PubChem 构建可复现
的基准数据集，包含参考结构、描述符元数据、二维结构图和坐标文件，再用一个
统一客户端调用候选模型，并用 RDKit 打分。版本 0 已完成：1500 条记录，在元
素类型、环系、立体化学、电荷状态和官能团上做了覆盖采样。首批 100 条、8 个
模型的评测也已完成，主要结果见下。

## 评测结果

八个模型回答同一百个 PubChem 名称，每个名称一次调用。800 次调用在重试后全
部完成。Claude Haiku 5.5 的精确匹配率最高，为 79%。GPT-6.1 Terra 最便宜，
每百条 0.07 元，每 100 个正确答案 0.11 元。准确率从最简单层的 78% 降到最
难层的 28%。

![各模型精确匹配率](docs/figures/eval_mini_100/leaderboard.png)

| 模型 | 精确 | 连接性 | 有效 | 每百条费用（元） | 每百个正确答案费用（元） |
|---|---:|---:|---:|---:|---:|
| Claude Haiku 5.5 | 79% | 84% | 100% | 0.20 | 0.25 |
| DeepSeek Flash | 74% | 80% | 100% | 5.04 | 6.82 |
| MiniMax M3.1 Flash | 71% | 74% | 98% | 2.12 | 2.99 |
| Gemini 3.8 Flash | 70% | 81% | 94% | 4.86 | 6.94 |
| GPT-6.1 Terra | 62% | 70% | 93% | 0.07 | 0.11 |
| GLM 5.3 Flash | 49% | 54% | 91% | 2.17 | 4.42 |
| LongCat 2.5 Preview | 46% | 52% | 88% | 4.80 | 10.43 |
| MiMo V2.6 Flash | 30% | 32% | 74% | 0.94 | 3.13 |

完整报告见 [docs/eval_mini_100.zh-CN.md](docs/eval_mini_100.zh-CN.md)，包含分层
结果、token 使用、运行设置和注意事项。800 行原始 JSONL 和日志在
`data/eval_mini_100_20261028T231806/`，该目录不随仓库提交。

## 功能

- 1500 条 PubChem 记录，InChIKey 互不重复，968 个非空 Murcko 骨架。
- 按元素类别、重原子数、环数、立体化学、电荷、53 种官能团和结构标记做覆
  盖采样。
- 每条记录六种二维结构图：RDKit 标准 PNG 和 SVG、去掉立体化学的版本、带
  原子编号的版本、低分辨率 PNG，以及 PubChem 原图。
- 二维 SDF、可获取时的 PubChem 三维 SDF（1068 条），以及 RDKit ETKDG 生
  成的备用构象（365 条）。
- 每条记录附带 RDKit 描述符、元素计数、环大小、螺原子和桥头原子、立体中心
  以及 Murcko 骨架。
- 100 条记录的小型测试集，分为五个难度层级，覆盖版本 0 的全部官能团，适合
  低成本快速检查。
- 一个客户端支持 10 家服务商的 20 个模型，兼容 OpenAI 与 Anthropic 两种接
  口，统一统计 token，并控制推理强度。
- 价格表与成本估算脚本，以及可续跑的先导和批量评测脚本，会解析模型输出的
  SMILES 并用 RDKit 打分。
- 构建流程可中断续跑，PubChem 请求限速并带缓存。

## 环境要求

- Python 3.11 或更高版本。数据集使用 Python 3.13 构建。
- RDKit。版本 0 使用 RDKit 2025.09.1。
- 完整图像和坐标文件约需 170 MB 磁盘空间。
- 只有评测脚本需要 API 密钥，构建数据集不需要。

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
Copy-Item .env.example .env
```

脚本和测试会自行把 `src/` 加入模块搜索路径，所以可编辑安装只是方便，并非
必需。把计划调用的模型密钥填入 `.env`。每个密钥都可选，缺少密钥的模型会被
跳过。

## 快速开始

```powershell
python scripts/sample_candidates.py --n 20000
python scripts/select_dataset.py --n 1500
python scripts/build_dataset.py
python scripts/coverage_report.py
python scripts/select_mini_dataset.py --n 100
```

`sample_candidates.py` 从 PubChem 随机抽取 CID，保留通过筛选的结构。
`select_dataset.py` 按覆盖分箱贪心挑选。`build_dataset.py` 抓取名称、同义
词、结构图和坐标文件，中断后重跑即可继续。`data/` 是生成目录，不纳入版本
管理，新克隆的仓库需要本地重建。构建依赖 PubChem 的实时内容，因此今天重建
的结果在下述细节上可能与版本 0 不同。

## 使用与配置

### 记录字段

`data/benchmark_v0.jsonl` 中每条记录包含：

- PubChem CID、IUPAC 名称、同义词、异构 SMILES、连接性 SMILES、InChIKey、
  分子式、电荷和重原子数。
- RDKit 描述符：元素计数、环大小、芳香环、螺原子和桥头原子、立体中心、双
  键立体化学、官能团、片段以及 Murcko 骨架。
- 六种二维结构图、一个二维 SDF，以及最多两个三维 SDF 的文件路径。
- 来源链接、抓取时间和 PubChem 原始响应。

### 数据集版本 0

- 元素分布：765 条 CHNO、305 条含卤素、287 条含 S/P、82 条含
  B/Si/Se/As、61 条含金属。
- 250 条无环记录，968 个不同的非空 Murcko 骨架。
- 1068 条 PubChem 三维结构，365 条 RDKit 备用构象；67 条没有三维文件，多
  为大分子或含金属结构。
- 1500 条记录都具备六种二维结构图。

完整覆盖表见 [`docs/coverage.md`](docs/coverage.md)，数据集说明见
[`docs/datasheet.md`](docs/datasheet.md)。名称取自 PubChem 计算的 IUPAC
名，不保证是首选 IUPAC 名。

### 小型测试集

`data/mini_100.jsonl` 含 100 条记录，用于快速检查模型。选择脚本先用启发式
难度模型给每条记录打分，固定最容易和最难的样本，再按五档配额填充，同时覆
盖元素、大小、环、立体、电荷、标记和官能团分箱。

| 层级 | 标签 | 记录数 | 分数区间 |
|---|---|---:|---|
| L1 | 简单 | 25 | 0-<12 |
| L2 | 中等 | 30 | 12-<24 |
| L3 | 困难 | 20 | 24-<38 |
| L4 | 很难 | 15 | 38-<52 |
| L5 | 极难 | 10 | >=52 |

小测试集覆盖全部 53 种官能团、所有元素类别、所有重原子、环、立体和电荷分
箱，包含 84 个不同的非空 Murcko 骨架和 16 条无环记录。记录沿用原编号和资
产路径，直接复用完整数据集的图像与 SDF 文件。

```powershell
python scripts/select_mini_dataset.py --n 100
python scripts/evaluate_name2smiles.py --data data/mini_100.jsonl --limit 100 --models "deepseek-flash,qwen3.8-flash" --workers 6 --reasoning low
```

难度分是规划用的启发式指标，未做难度标定。完整分层、分数构成和覆盖对比见
[`docs/mini_100.md`](docs/mini_100.md)。

### 大模型评测

20 个候选模型注册在 `src/name2smiles/llm/registry.py`，不需要厂商 SDK。客户
端统一 token 统计，并把推理文本和可见回答分开。服务商表与模型 ID 见
[`docs/llm.md`](docs/llm.md)，推理与强度参数见
[`docs/reasoning_controls.md`](docs/reasoning_controls.md)。

```powershell
python scripts/smoke_llm.py --all
python scripts/smoke_llm.py --provider deepseek
python scripts/smoke_llm.py --models "deepseek-v4-pro,glm-5.3"
```

默认输出上限为 16,384 token。请求不带温度参数，各服务商使用自己的默认值。
连通性测试的结果写入 `data/llm_smoke_<时间戳>.jsonl`。

先导评测用 10 条均衡记录跑低成本模型：

```powershell
python scripts/evaluate_name2smiles.py --pilot --workers 6 --reasoning low
```

90 次调用在低推理强度下花费 0.60 元。结果与观察见
[`docs/eval_pilot.md`](docs/eval_pilot.md)。脚本按模型和记录逐条输出，并在
`data/` 下写一份汇总 JSON。

### 成本估算

价格存放在 `config/llm_pricing.json`，说明文档为
[`docs/llm_pricing.md`](docs/llm_pricing.md)。表内单位为每百万 token 人民币
价格，记录 4Router 分组显示价，已包含分组倍率。

```powershell
python scripts/estimate_costs.py --records 1500 --input-tokens 200 --output-tokens 800
python scripts/estimate_costs.py --records 1500 --input-tokens 200 --output-tokens 800 --models "deepseek-v4-pro,claude-opus-5.5"
```

估算脚本用于规划。大批量运行前，应先用先导评测得到的真实 token 数替换假设
值。

## 仓库结构

```text
src/name2smiles/
  pubchem.py              # 带限速的 PubChem 客户端
  descriptors.py          # RDKit 描述符与官能团
  difficulty.py           # 小测试集的启发式难度分
  names.py                # 名称质量规则
  render.py               # RDKit 结构图与三维构象
  llm/                    # 服务商注册表、对话客户端、定价
scripts/
  sample_candidates.py    # 随机筛选候选池
  select_dataset.py       # 覆盖优先的选择
  select_mini_dataset.py  # 100 条分难度子集
  build_dataset.py        # 名称、图像、SDF 文件
  assign_common_names.py  # 常用名与商品名
  recompute_descriptors.py
  validate_dataset.py
  coverage_report.py
  regenerate_large_images.py
  smoke_llm.py
  estimate_costs.py
  evaluate_name2smiles.py
tests/
config/llm_pricing.json   # 机器可读的模型价格
docs/                     # 覆盖报告、数据集说明、小测试集、大模型笔记
data/                     # 生成的记录与资产，不纳入版本管理
```

## 测试

```powershell
python -m pytest tests/
```

测试覆盖描述符、名称规则、难度打分、PubChem 客户端、大模型客户端、价格表
和小测试集约束。测试可离线运行，不需要 API 密钥。

## 许可证

尚未选择许可证。仓库未公开，代码暂未授权他人复用。PubChem 计算数据可自由
使用，数据集许可证和第三方标注的使用条款将在发布前确定。
