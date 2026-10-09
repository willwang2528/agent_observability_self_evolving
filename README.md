# Agent Observability & Self-Evolving Agents

研究链路：执行轨迹与可观测数据处理 → 失败诊断与责任归因 → 诊断驱动的持久改进 → 未见任务验证。

## 已完成的诊断 pilot

[完整报告](experiments/agent_diagnosis_pilot/REPORT.md) · [逐次预测与评分](experiments/agent_diagnosis_pilot/results/raw_rows.csv) · [复现方法](experiments/agent_diagnosis_pilot/README.md)

2026-10-09：Who&When 的 12 个独立任务，固定 `gpt-6-astra / xhigh`，比较完整轨迹与 12,000 字符的首尾轨迹基线，共 24 次真实调用。

| 指标 | 完整轨迹 | 首尾截取 |
|---|---:|---:|
| Agent 与步骤联合精确命中 | 4/12 | 3/12 |
| 主动弃权（准确率计零） | 3/12 | 6/12 |
| 总输入 tokens | 197,790 | 96,472 |

输入 tokens 减少 51.2%。一个已核验案例保留了标注错误步骤，却丢失判断该错误所需的来源表，诊断由正确定位变为弃权。后续重点是预算内保留跨步骤诊断证据链。

这是无任务答案辅助的诊断改编实验，不能直接与官方论文分数比较。样本量不足以证明方法提升；当前没有执行持久改进或验证自进化效果。

## 本地重新评分

以下操作只运行测试与评分，不调用模型：

```bash
cd experiments/agent_diagnosis_pilot
python3 -m unittest discover -s tests -v
python3 score_results.py
```

数据固定官方提交，保留 MIT 数据许可证、来源清单、文件哈希、冻结实验协议、实际输入输出和执行用量。后续新实验应使用独立目录，避免覆盖本轮冻结记录。
