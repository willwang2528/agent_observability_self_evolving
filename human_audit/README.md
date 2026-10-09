# 人工审计目录

本目录用于你或真实人工审计者记录证据判断、研究取舍和标签异议。**当前状态：待真人审计，尚无已完成的人工审计记录。**

Codex 生成的文档、自动测试和机器语义复核存放于 [machine_work/](../machine_work/README.md)。已有 `case_audit.md` 虽使用“人工审查”旧称，实际由 Codex 生成，只能作为待核验的候选材料。上游数据的人工 gold 是来源标签，也不代表本项目真人已经复核。

## 如何记录

复制 [REVIEW_TEMPLATE.md](REVIEW_TEMPLATE.md)，建议命名为 `YYYY-MM-DD_<实验名>_<范围>.md`。填写实际审计人、日期、对应实验与版本、结论及可定位的证据。模板本身不是已完成的审计记录。

重点检查：

- 官方数据、论文和实现的版本是否对应；本地输入是否含答案或诊断标签。
- 指标分母、零基步骤、责任 Agent 和步骤匹配是否正确；弃权及失败是否保留在分母内。
- 个案解释是否能由可见原始步骤支持，是否遗漏来源、决策或传播环节。
- 标注归因与实际执行者是否存在边界差异；同意标签、标签存疑与证据不足分别记录。
- 报告是否区分可运行、诊断正确、解释可信、干预有效与持久自进化；比较设置是否公平。

原始 gold 和冻结结果保留不动。人工异议应记录原标签、建议、依据及裁决状态；后续若形成修订标签，另存有版本的数据，并同时报告原标签与修订标签下的结果。

## 当前优先审计对象

1. [完整 pilot 报告](../machine_work/benchmarks/who_when/pilot_20261009/REPORT.md)：核验实验设置及结论边界。
2. [机器个案复核](../machine_work/benchmarks/who_when/pilot_20261009/results/case_audit.md)：优先检查 `handcrafted_012`、`handcrafted_031`、`algorithm_106` 和 `handcrafted_021`。
3. [逐次评分](../machine_work/benchmarks/who_when/pilot_20261009/results/raw_rows.csv) 与 [原始标签](../machine_work/benchmarks/who_when/pilot_20261009/data/gold.json)：逐条核对需要关注的样本。

## 按 benchmark 审计

每套 benchmark 有独立入口，均为待真人填写状态：[Who&When](benchmarks/who_when/README.md)、[ALFWorld](benchmarks/alfworld/README.md)、[WebShop](benchmarks/webshop/README.md)、[τ-bench](benchmarks/tau_bench/README.md)。机器验收记录与原始输出见各入口所链接的 `machine_work/benchmarks/`。
