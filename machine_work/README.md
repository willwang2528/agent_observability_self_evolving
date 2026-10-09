# 机器工作目录

本目录供 Codex 存放实验实现、执行记录、机器自检及候选分析。目前已有 [Who&When 诊断 pilot](experiments/agent_diagnosis_pilot/REPORT.md)。

## 内容与约定

| 内容 | 存放位置与要求 |
|---|---|
| 实验实现 | `experiments/<实验名>/`，包含说明、协议和必要测试 |
| 数据与标签 | 实验内 `data/`，记录官方来源、固定版本和哈希；原始标签独立保存 |
| 实际执行 | 实验内 `results/`，保存输入、原始响应、状态、用量及评分 |
| 机器复核 | 随实验记录证据阅读、候选错误分析和不确定性，明确由 Codex 生成 |
| 待人工判断事项 | 在实验报告中列出具体问题和证据路径，交由 `human_audit/` 记录人工判断 |

每轮正式运行先固定样本、条件、指标、模型和预算。完成后保留全部计划任务的分母，区分格式失败、主动弃权和诊断错误。新条件、新模型或调参结果放入独立实验目录，保留旧记录。

## 当前 pilot

- [实验报告](experiments/agent_diagnosis_pilot/REPORT.md)
- [复现入口](experiments/agent_diagnosis_pilot/README.md)
- [冻结协议](experiments/agent_diagnosis_pilot/protocol.json)
- [逐次结果](experiments/agent_diagnosis_pilot/results/raw_rows.csv)
- [机器个案复核](experiments/agent_diagnosis_pilot/results/case_audit.md)

**来源说明：** `case_audit.md` 是 Codex 生成的机器分析。原文中的“独立事后人工审查”旧称不准确，不能据此声称真人已审。为保留本轮档案原文，该说明在此及仓库根 README 中纠正；实际真人审计另存于 [human_audit/](../human_audit/README.md)。

当前只验证诊断实验可运行，`repair_hint` 仅为修复建议，没有执行修复或验证持久自进化。
