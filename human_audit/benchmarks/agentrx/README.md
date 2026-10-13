# AgentRx 轨迹诊断：待真人审计

**尚未真人审计。** 本页由 Codex 创建。独立 subagent 审计也是机器工作。

[机器实验入口](../../../machine_work/benchmarks/agentrx/README.md) · [记录模板](../../REVIEW_TEMPLATE.md)

审计对象是固定 GitHub 快照的29条 tau 失败轨迹，诊断第一处不可恢复的关键失败步骤和类别。不是交互任务执行成功率，也不是最新论文全部170条复现。

- 核对 `inputs/<task_id>/steps.json`：第1步为政策，编号从1开始；工具调用和返回分别计步。
- 对照 `calls/<task_id>/attempt_1/response.json`、官方 `upstream/data/ground_truth/tau_ground_truth.json` 和 `evaluation/per_case.csv`，分别判断步骤、类别、解释证据。
- 特别检查根因属于 User 的样本：官方 baseline 没有传入私有 task.instruction，是否有足够可见证据应另行判断，不能据不一致直接认定模型推理错误。
- 记录标签歧义、恢复判据以及首个错误与首个未恢复错误的差别。保留原标签和预测，在本目录另存审计人、日期、证据及裁决，不回填机器评分。
- 实验仅有一次公开快照运行，模型与论文不同；不能据此证明持久自进化或未见任务收益。
