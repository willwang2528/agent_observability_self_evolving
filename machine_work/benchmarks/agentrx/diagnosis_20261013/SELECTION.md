# Agent 执行轨迹诊断 benchmark 选择与一手来源核验

核验日期：2026-10-13（北京时间）。这是来源与可运行性调查，不是模型运行结果。候选列表中的“已下载/已核验”不表示模型已经跑通。本轮最终选择 **AgentRx 的固定 GitHub 快照公开的全部 tau-retail 29 条失败轨迹**，运行诊断 baseline；不将该 baseline 称为完整复现 AgentRx 的约束生成、检查和归因方法。

## 1. 本轮选择

| 候选 | 直接诊断目标 | 已核验公开规模 | 本轮状态与取舍 |
|---|---|---:|---|
| AgentRx / tau-retail | 第一处不可恢复的关键失败步骤、失败类别 | 本地固定版本 29 条失败轨迹及 29 条 gold | **本轮已运行29/29；真实指标和验收见 REPORT.md**。输入短，完整分集可运行；与既有 τ-bench 交互成功率实验是不同任务 |
| TRAIL | 轨迹中全部错误的 span 定位、类型及整体评分 | GitHub 固定版本 117 GAIA + 31 SWE Bench，841 条 error | 下载与源码核验完成，未运行模型。适合后续长轨迹证据处理，但本轮不优先 |
| AgentErrorBench | 最早关键失败的步骤、模块、错误类型 | 官方 Drive 标签 100 ALFWorld + 50 GAIA + 50 WebShop | 标签和每域一条原始样例下载核验完成，未运行模型。直接相关，但缺少现成官方离线 scoring CLI |
| Who&When | 责任 Agent 和失败步骤 | 当前 repo 已有独立 pilot | 已有历史实验，不作为本次新增目录的重复 benchmark |

“跑通”应有原始调用、逐例预测、固定分母评分与独立重算；不要求诊断模型对每个 gold 都答对，也不将流程通过写成诊断全命中。失败预测必须保留，不能通过换样本、读取诊断 gold 或只保留成功输出达成验收。

## 2. AgentRx：所选 benchmark

一手来源：

- [官方论文全文 v1](https://arxiv.org/html/2602.02475v1)，重点 §2、§4.1、Appendix G。
- [微软官方项目](https://github.com/microsoft/AgentRx)。本地已读取固定 commit `7a18c79708e7671be15124460f4f7296107c2a55`。
- [官方数据集卡片](https://huggingface.co/datasets/microsoft/AgentRx)。代码 MIT；卡片明确数据 CC-BY-4.0，保留论文、作者、数据来源与适配说明。
- [固定版本原始失败轨迹](https://github.com/microsoft/AgentRx/blob/7a18c79708e7671be15124460f4f7296107c2a55/data/tau_retail/tau_dataset_failed.json)。
- [固定版本完整 29 条诊断 gold](https://github.com/microsoft/AgentRx/blob/7a18c79708e7671be15124460f4f7296107c2a55/data/ground_truth/tau_ground_truth.json)。
- [固定版本官方 judge](https://github.com/microsoft/AgentRx/blob/7a18c79708e7671be15124460f4f7296107c2a55/agentrx/judge/judge.py)。

### 下载与分母核验

在 `/tmp/agentrx_source_20261013` 只读核验：

| 文件 | 数量/大小 | SHA-256 |
|---|---|---|
| `data/tau_retail/tau_dataset_failed.json` | 29 项，900,014 bytes | `17f8b3356d1124274cc7ed0215b5ff696970073dbed57394c60e775d5f85d717` |
| `data/ground_truth/tau_ground_truth.json` | 29 项 | `58067689b2ec42f9cbfec2a84ec08d39cea4d8270617b55d0185862753642d16` |
| `data/ground_truth/tau_retail.json` | **仅 24 项**，不可误当完整 29 条 gold | `92899ac61630bef5b4b41ee2e9b738a8784af80b7b4a7744119fef65990e27d8` |

完整 task IDs：`[2,3,4,12,20,21,28,31,32,34,38,39,41,47,55,59,63,71,72,74,79,80,82,87,91,98,99,104,105]`。轨迹 `traj` 按 `json.dumps(..., ensure_ascii=False)` 计算字符数：最短 13,900，中位数 21,957，最长 51,921，合计 703,006。步骤数最短 20、中位数 36、最长 62。这些是字符而非 token，不包含额外 policy/schema/prompt。

### 输入、输出、评分边界

原始记录包含 `task_id, reward, info, traj, trial, records`。诊断 gold 另存 `trajectory_id, failures, root_cause, failure_summary`，通过 root cause 指向的 failure 获取关键步骤和类别。必须按身份 join，校验 29/29 覆盖与步骤编号，不能直接按列表位置配对。

诊断输入是执行轨迹、必要的领域政策、工具 schema，以及协议显式允许的任务上下文。上游模板声称提供任务参考 actions / expected outputs，但固定版本的实际调用仅传入 `item["steps"]`，`ground_truth/outputs` 参数未使用。本轮沿用官方实际 baseline：只输入完整步骤的 Python repr，保留每条轨迹内的政策和真实对话，不额外注入 task.instruction、actions、outputs、reward 或诊断 gold。这个源码与模板不一致的限制保留并报告。

baseline 由模型输出关键失败步骤、类别和证据理由。按照论文可离线计算 exact step accuracy、step accuracy @ ±1/±3/±5、平均步骤距离、critical category accuracy；可补 joint exact step+category，但需明确是补充指标。不要把“Any-failure category”与“Critical-failure category”混为一谈。

论文中的 LLM judge 是待评估诊断器的一部分；有已标注 step/category 后，字符串/索引评分不需要额外模型。完整 AgentRx 方法还生成静态/动态约束并调用 checker，开销高于单次 baseline，不能用一次诊断调用冒充完整方法。

论文 v1 总规模为 115（29 tau、42 Flash、44 Magentic）。2026-10-13 补查[最新 v2 全文](https://arxiv.org/html/2602.02475v2)：规模已扩为 170，其中 tau 39、Flash 42、Magentic 44、RelWork 45。固定 GitHub 快照当前仍提供配对的 tau 29 条。本轮运行该公开快照的全部 29 条，不宣称跑完 v2 的 39 条 tau 或 170 条全量，也不宣称新产生交互轨迹。论文默认 gpt-5、配置重复 3 次；若本地模型或重复次数不同，应标明是新 baseline 运行而非原论文数值复现。

## 3. TRAIL：数据与官方评分已核验

一手来源：

- [论文全文 v1](https://arxiv.org/html/2505.08638v1)。
- [官方仓库](https://github.com/patronus-ai/trail-benchmark)，固定 commit `0ffbed9db859b4a66250dc783fa4dccf86869595`；本地只读副本 `/tmp/diagnosis_benchmark_source_audit/trail-benchmark`。
- [官方数据卡片](https://huggingface.co/datasets/PatronusAI/TRAIL)。
- [推理入口](https://github.com/patronus-ai/trail-benchmark/blob/0ffbed9db859b4a66250dc783fa4dccf86869595/benchmarking/run_eval.py) 与 [评分入口](https://github.com/patronus-ai/trail-benchmark/blob/0ffbed9db859b4a66250dc783fa4dccf86869595/benchmarking/calculate_scores.py)。

源码和数据均可匿名 git clone，raw trace、processed annotations 在同一仓库。MIT；HF 卡片另写仅用于评估 benchmark、不用于训练自动人评系统。本轮是评估用途。

输入为嵌套 `spans/child_spans` 的 OpenTelemetry/OpenInference 轨迹。输出含 `errors[]`（`category,location,evidence,description,impact`）及 `scores[]`。`location` 为原始 span ID。`get_prompt` 要求枚举全部错误；Resource Abuse 定位最后出现，其他类型定位首次出现。官方 scoring 是纯 Python，无额外 LLM judge。

### 长度实测

字符数基于原始 UTF-8 文本的 Python `len`；compact 指保留全部 JSON 字段，只去非语义空白并以 Unicode 写出，不是摘要。

| GitHub split | 文件数 | raw 最短 | raw 中位数 | raw 最长 | raw 合计 | compact 中位数 | compact 最长 |
|---|---:|---:|---:|---:|---:|---:|---:|
| GAIA | 117 | 96,308 | 248,213 | 9,036,173 | 111,205,744 | 212,274 | 8,219,144 |
| SWE Bench | 31 | 441,015 | 1,618,503 | 8,901,770 | 74,366,103 | 1,504,887 | 6,256,500 |

GAIA compact ≤250k/500k/1M 字符分别 65/77/89 条；SWE 分别 0/1/9 条。大量 LLM span 重复完整 messages 历史。若需分块、去重或只读检索，这属于需单列协议的输入适配，不能把删掉历史后的输入描述为完整原始 one-shot prompt。

固定 GitHub checkout 的 split 数为 **117+31**；HF 卡片写 **118+30**，不可照抄卡片替代下载版本分母。递归 span 记录实测 GAIA 3,579、SWE 1,047（包含父级/不同种类 span），不能将该计数直接视为论文所报 1,987 的同一口径。

### 数据及 scorer 异常点

1. GAIA `processed_annotations_gaia/a96c6811716c0473b86a23321db79c34.json` 第 38 行有尾逗号，标准 `json.load` 失败。该项 5 条 errors；若未来运行，需保留原件和独立 syntax-only 修复记录。其余 GAIA 580 条，加该项 5 条，SWE 256 条，共 841 条。
2. GAIA 全部 585 个 error location 都存在于轨迹，无重复 span ID，3 条 zero-error 轨迹。
3. SWE 的 `72822db6e120878d916b515c2501246b.json` 有 14 条 span 记录但 13 个 ID；`e7bdf7bbf6b931c3be95afe323704041.json` 和 `e88b6bbc943971964ce88bf46c5cf76f.json` 各有一条 gold location 写作 `Span ID not found for this shard`。SWE 有 1 条 zero-error 轨迹。
4. 官方 `joint_accuracy = |predicted_pairs ∩ gold_pairs| / |gold_pairs|`，是每条轨迹的标签对召回，**不是整条轨迹全对率**；它自身不惩罚额外预测。宜原样报告官方值，再补 precision/F1。
5. 官方 CLI 对 missing prediction、JSON 错误等会跳过，导致有效分母变小；验收必须另行检查所有预定样本都被评分。
6. zero-error gold 的 location/joint 返回 0；category normalization 有单向子串匹配，不能清除所有拼写变体；scorer taxonomy 含 `Incorrect Memory Usage`，prompt 列表未包含该类。
7. 分数相关性路径用 truthiness 将 0 转成 -1。应保留 upstream 行为的报告与限制，不静默改分。

本轮选择更短且直接关键失败诊断的 AgentRx；TRAIL 保留为后续海量轨迹处理、证据检索与压缩研究候选，未运行模型，不宣称复现。

## 4. AgentErrorBench：官方数据可匿名下载，scorer 未配套

一手来源：

- [论文全文 v1](https://arxiv.org/html/2509.25370v1)。
- [官方 AgentDebug 仓库](https://github.com/ulab-uiuc/AgentDebug)，本地 clone commit `7740fe3a5c4822b2143cbde78ecfffeace0bb166`，代码 MIT。
- [官方 README 指向的 Google Drive](https://drive.google.com/drive/folders/1bQe6dQA85pktT63YnKIKJDTVaH3O3Vpu)。
- [原始失败轨迹目录](https://drive.google.com/drive/folders/1wTUcUONh_xV1m-SUGD8_NlXhoQ14APX0)。

官方 Drive README 和三份 labels 已匿名下载并 JSON 解析，计数为 ALFWorld 100、GAIA 50、WebShop 50。三个域各下载一条原始轨迹样例成功。未完成全部 200 原始轨迹下载，Drive HTML 首屏列表存在 50 条边界，不能把首屏当全目录。第三方 HF `davide221/agenterrorbench` 不是本轮依据。

稳定下载地址：

- [ALFWorld labels](https://drive.google.com/uc?export=download&id=1E6UYJBF86FZxLg5l85J0yr5U8944B8px)
- [GAIA labels](https://drive.google.com/uc?export=download&id=1Q6TgfvS9KRZhYK6vgNapk2vGhH9xRuiv)
- [WebShop labels](https://drive.google.com/uc?export=download&id=1prK2f3NX47Xidh6jgE7HXAzt5OxotcdB)
- [数据 README](https://drive.google.com/uc?export=download&id=1Nf-4YDh2kLsLoGN8ZMrDUlfgFiN3Xg-L)

原始样本为 `{messages, metadata}`；标签为 `trajectory_id, LLM, task_type, critical_failure_step, critical_failure_module, step_annotations`。module 有 `planning` 与 `plan` 变体。论文指标为 step exact、step+module、step+module+error-type All Correct，可用确定性 scorer 实现。

已检查官方 `detector/fine_grained_analysis.py` 与 `critical_error_detection.py`，提供两阶段诊断实现：先各步各模块检测，再找关键错误；后者明确写无评分。当前 clone 未找到配套离线 benchmark scorer，README 所列 `docs/`、`examples/` 目录也不在该 checkout。直接 prompting baseline 可一条轨迹一次诊断；完整两阶段方法按步骤/模块调用，不能混称。

代码 MIT 不自动证明 Drive 数据单独许可；下载的 Drive README 未给数据许可。这不影响本次作为候选核验，但后续发布原始数据副本应明确来源与许可边界。论文 v1 算法写 Stage 2 无 rollout/counterfactuals，正文又声称逐步反事实替换执行；源码当前是 LLM 归因。故仅靠阅读不能宣称已实证验证可恢复根因或完整反事实复现。

## 5. 实验记录应延续的证据要求

- 冻结版本、全分集 task IDs、输入字段、输出 schema、模型配置与重试条件，再执行。
- 将诊断 gold 与实际模型可见目录和 prompt 分离；只允许 scorer 读取 gold。
- 保留每次实际请求/响应、异常及修复过程；只有传输/解析失败可按预先协议重试，预测与 gold 不一致不能换结果。
- 记录官方定义的诊断指标及其分母；模型有效输出率、schema 合法率属于执行质量，不等于诊断正确率。
- 独立从冻结预测重算，并检查步骤范围、ID 关联、无漏样本；之后才对本轮运行作“已跑通”声明。
- 当前文档仅完成 benchmark 选择与下载/静态核验；实际运行结果应由后续 run manifest、逐例评分与验收报告给出。
