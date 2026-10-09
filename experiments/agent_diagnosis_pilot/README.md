# Agent 诊断 pilot

本实验用公开 Who&When 失败轨迹，先验证“Agent 可观测数据处理 → 失败诊断”的实验链路。固定同一诊断模型，对同一批样本比较完整轨迹与预算内首尾轨迹。实际结果与结论见 `REPORT.md`；本文件只说明复现方法和实验边界。

## 运行

在本目录执行，使用 Python 3 标准库，无需安装上游仓库依赖。真实模型调用使用本机已有 Codex 登录，不需要新增 API key。

```bash
cd experiments/agent_diagnosis_pilot
python3 -m unittest discover -s tests -v
python3 run_pilot.py
python3 run_pilot.py --run --workers 3 --timeout 600
python3 score_results.py
```

- 单元测试检查输入字段隔离、轨迹处理、预测校验、评分和运行器行为。
- `python3 run_pilot.py` 只准备并冻结实验计划及输入，不请求诊断模型。它会检查原始数据 SHA-256，并记录代码、协议、指令与 schema 的版本 hash。
- 加 `--run` 才执行真实诊断。每个 job 的有效输入 hash 必须与已有结果一致；已存 `result.json` 会直接复用，不重复调用。传输失败最多重试一次；不会因为诊断错误、弃权或评分不佳而重试。`--timeout 600` 是每次调用的秒数上限。
- `python3 score_results.py` 在预测之后单独读取 gold 评分。缺失、无效和弃权预测保留在预定分母内，不能只报告成功解析样本的准确率。

已有 `results/plan.json` 时，运行器会拒绝覆盖与冻结版本不同的计划。改模型、协议、代码或输入后应创建新的实验目录，保留本轮原始记录。

## 数据与输入

原始数据固定为官方仓库提交 `f4d2b6da464a826580e59b3a0eae15ea2d642d7c`。来源、许可证、下载归档及逐文件校验值见 `data/SOURCES.md`、`data/source_manifest.json` 和 `data/upstream/LICENSE`。

固定样本为 12 条：Algorithm-Generated 与 Hand-Crafted 各 6 条，分别按原始轨迹字符长度分短、中、长三个组，每组 2 条；种子为 `20261009`，全局 question_ID 不重复。抽样只依据来源、长度和任务 ID，不使用诊断标签。具体名单见 `data/selected_manifest.json`，可重跑抽样逻辑见 `data/prepare_selection.py`。

模型输入采用字段白名单：`question`、可选 `system_prompt`、清洗后的 `history` 内容及代理标识；保留原始从 0 开始的 step ID。任务答案 `ground_truth`、诊断标签 `mistake_agent` / `mistake_step` / `mistake_reason`、额外 `labels` 与任务结果标记不提供给模型。标签单独保存在 `data/gold.json`，诊断运行器不读取该文件。原始轨迹自身可能自然包含正确答案或接近答案的文本；这与主动提供顶层答案字段不同，相关审计见 `data/data_audit.json`。

官方诊断实现会向模型提供任务答案，本实验省略该答案，因此属于**无答案辅助的诊断改编实验，不是原论文分数的严格复现**。

## 比较条件与评分

`protocol.json` 固定两种条件：

1. `full`：保留全部记录步骤。
2. `head_tail_12000_chars`：按首尾交替选择完整步骤，显式标明省略的中间 step 区间；不在步骤内容内部静默截断。

**12,000 是渲染后 trace 的字符预算，不是 token 预算，也不是整个 prompt 的预算。** Trace 内的步骤编号、代理标识和省略标记计入预算；问题、系统提示、已知代理列表及诊断指令在 trace 之外。原轨迹低于预算时两种条件可能相同，评估时应读取实际保留步骤和字符数。

主要指标为责任代理准确率、严格步骤命中率和二者同时命中的准确率。步骤 ±1 只作为次要指标。代理名采用明确的大小写/首尾空白规范化，并将 `Orchestrator (...)` 视为 `Orchestrator`；不使用官方评分脚本的 substring 匹配。证据引用是否指向可见步骤、压缩后是否保留 gold 步骤分别报告，不能替代诊断准确率。

## 运行时与结果文件

模型配置为 `gpt-6-astra` / `xhigh`，使用 `runtime.py` 固定的本机 Codex CLI 路径。每次在临时空目录运行，禁用工具、网页检索、记忆、插件与工作区指令发现；记录调用命令和事件流，以审计是否出现工具调用。

这是 **Codex CLI 的固定运行时条件，不是裸 API 调用**。CLI 仍会提供运行时上下文；事件中报告的 input token usage 包含这些 overhead，不能把它直接视为纯 trace token 数。具体 CLI 版本、输入 hash 和运行记录保存在计划与各次调用目录中。

| 路径 | 内容 |
|---|---|
| `protocol.json` | 冻结的实验设计、条件、预算与指标 |
| `instructions.md`、`prediction.schema.json` | 诊断指令与输出结构 |
| `pilot_core.py` | 输入字段白名单、首尾轨迹处理与严格评分逻辑 |
| `data/selected_manifest.json`、`data/gold.json` | 独立的样本清单和诊断标签 |
| `data/DATA_CARD.md`、`data/data_audit.json` | 数据 schema、重复任务和标签语义审计 |
| `results/plan.json` | 模型、CLI 版本、代码 hash、输入 hash 和冻结 job 顺序 |
| `results/runs/<job_id>/prompt.txt` | 实际送入模型的诊断输入 |
| `results/runs/<job_id>/input_metadata.json` | 实际保留/省略步骤、字符数与输入 hash |
| `results/runs/<job_id>/attempt_*/` | 命令、原始事件流、stderr、模型响应和调用元数据 |
| `results/runs/<job_id>/result.json` | 最终结果与所有尝试的 usage/耗时汇总 |
| `results/execution_summary.json` | 本轮执行完成度、工具污染与总 usage |
| `REPORT.md` | 实际 pilot 结果、失败案例与下一步判断 |

输出中的 `repair_hint` 仅是模型提出的修复建议。当前实验没有执行修复、持久更新 Agent 或验证新任务收益，因此不能将其作为自进化效果。运行这些入口也不会推送 GitHub 或发送飞书消息。

## 归档说明

本目录于 2026-10-09 同步至研究仓库。冻结代码、计划、实际 prompt、24 次响应及评分保持原文；历史命令和日志中的绝对路径是当时的运行位置，不影响独立重新评分。复现命令以仓库根目录为起点。

私有上下文调试快照与三次玩具探针目录未发布；`results/runtime_audit.json` 保留探针用量和审计摘要。正式运行的事件流与 stderr 保留，其中每次的两条提示分别是实验功能提醒和代码工具关闭提醒；无实际工具调用或未预期错误。

跨目录同步清单及原文件校验值见 `PUBLICATION_MANIFEST.json`。
