# 机器工作目录

本目录由 Codex 存放候选筛选、版本化代码、真实运行与机器验收。每套 benchmark 在 [benchmarks/](benchmarks/) 下独立保存协议、数据来源、实际输入输出、官方评分与验收；[选择依据](benchmarks/SELECTION.md)与[总报告](benchmarks/REPORT.md)连接全部证据。

[AgentRx轨迹诊断](benchmarks/agentrx/README.md) · [Who&When](benchmarks/who_when/README.md) · [ALFWorld](benchmarks/alfworld/README.md) · [WebShop](benchmarks/webshop/README.md) · [τ-bench](benchmarks/tau_bench/README.md) · [本轮严格成功验收](benchmarks/SUCCESS_ACCEPTANCE.json)

先冻结来源版本、样本、模型、预算与指标，再执行真实调用；全部预选任务保留在分母内。原始响应与官方环境重放、评分器正负对照分别验证，验收失败不推送。正式独立评测不按分数更换任务或挑选重试；本轮用户明确要求诊断后修复并重跑，已在 `recovery_20261011` 单独记录为开发实验，保留全部尝试，要求同一完整双任务 attempt 全部成功。适配器缺陷须另存无效 setup 证据。

新实验另建目录，不覆盖旧预测、标签或协议。环境缓存位于仓库忽略的 `.benchmark_cache/`；本机依赖快照和准备入口随代码发布。

**所有 Codex 生成的复核与解释都是机器结果。** 原 `case_audit.md` 中“人工审查”的旧称不能计为真人审计；实际真人记录由 [human_audit/](../human_audit/README.md) 维护。当前没有持久自进化实验或效果证明。
