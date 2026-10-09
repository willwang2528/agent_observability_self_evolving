# Agent Observability & Self-Evolving Agents

研究方向：处理 Agent 执行轨迹与可观测数据，诊断失败原因，再通过诊断驱动持久改进，并在未见任务上验证收益。

当前已完成一轮公开数据集上的诊断 pilot。实验链路已跑通，下一步重点是有限预算内的诊断证据链保留；自进化效果尚未验证。

## 两个工作目录

| 目录 | 维护者与用途 | 主要内容 |
|---|---|---|
| [human_audit/](human_audit/README.md) | 由你或真实人工审计者记录判断 | 来源核验、标签与证据复核、研究取舍、异议和裁决 |
| [machine_work/](machine_work/README.md) | 由 Codex 执行和整理工作 | 实验代码、公开数据、冻结协议、实际输入输出、机器自检和候选分析 |

```text
human_audit/
├── README.md                      # 人工审计范围、方法与当前状态
└── REVIEW_TEMPLATE.md             # 人工审计记录模板
machine_work/
├── README.md                      # 机器工作的约定和实验入口
└── experiments/
    └── agent_diagnosis_pilot/      # 已完成的 Who&When pilot
        ├── protocol.json          # 冻结设计
        ├── data/                  # 固定版本数据、来源与原始标签
        ├── results/               # 原始预测、评分、用量和机器复核
        ├── tests/                 # 评分与输入隔离等测试
        └── REPORT.md              # 本轮实验报告
```

**本项目的真人审计尚未完成。** 现有 `results/case_audit.md` 由 Codex 生成，原文中的“人工审查”是旧表述，应理解为机器证据复核，不能计作真人已审。上游作者提供的人工 gold 标签，也不等于本项目已经完成人工复核。

## 协作流程

1. Codex 在 `machine_work/` 准备实验、执行调用、保存原始证据，并写明结果和限制。
2. 人工以 [审计模板](human_audit/REVIEW_TEMPLATE.md) 为起点，在 `human_audit/` 保存带审计人、日期及证据路径的记录。
3. Codex 根据具体意见补充证据或开设新实验；人工记录和原始标签分别保留，异议另存。
4. 新实验使用独立目录，记录样本、模型、预算、协议和版本，再与已有结果比较。冻结结果不被后续调参覆盖。

机器生成的诊断、解释或修复建议都是待验证材料。程序测试、哈希一致、指标命中、人工证据判断及真实干预收益分别记录。

## 已完成的诊断 pilot

[完整报告](machine_work/experiments/agent_diagnosis_pilot/REPORT.md) · [逐次预测与评分](machine_work/experiments/agent_diagnosis_pilot/results/raw_rows.csv) · [复现方法](machine_work/experiments/agent_diagnosis_pilot/README.md)

2026-10-09：Who&When 的 12 个独立任务，固定 `gpt-6-astra / xhigh`，比较完整轨迹与 12,000 字符的首尾轨迹基线，共 24 次真实调用。

| 指标 | 完整轨迹 | 首尾截取 |
|---|---:|---:|
| Agent 与步骤联合精确命中 | 4/12 | 3/12 |
| 主动弃权（准确率计零） | 3/12 | 6/12 |
| 总输入 tokens | 197,790 | 96,472 |

总输入 tokens 减少 51.2%。一个机器复核案例保留了标注错误步骤，却丢失判断该错误所需的来源表，诊断由正确定位变为弃权。它支持提出证据链保留的研究问题，尚不足以证明新方法有效。

本轮未提供任务标准答案，属于无答案辅助的诊断改编实验，不能直接与官方论文分数比较。每任务每条件仅运行一次，样本量不足以给出可靠效果结论；没有执行持久改进或验证自进化。

## 本地重新评分

从仓库根目录执行。以下操作只运行测试与评分，不调用模型：

```bash
cd machine_work/experiments/agent_diagnosis_pilot
python3 -m unittest discover -s tests -v
python3 score_results.py
```

真实模型调用、结果复用、运行环境及重试规则见 [pilot README](machine_work/experiments/agent_diagnosis_pilot/README.md)。

本轮保留固定源版本、MIT 数据许可证、来源清单、文件哈希、冻结协议及实际输入输出。目录迁移不改变冻结代码、数据、计划或预测；历史命令中的本机绝对路径保留为执行证据。
