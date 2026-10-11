# 修复运行与成功验收：2026-10-11

**WebShop 2/2、τ-bench 2/2，四个原固定任务均获官方奖励 1，并完成真实模型证据核验和从初始状态的独立重放。** 本轮修复任务完成。原报告完整保存在 [REPORT_20261009.md](REPORT_20261009.md)，原失败预测、任务、数据与评分未覆盖。

[严格成功验收及日志](SUCCESS_ACCEPTANCE.json) · [调用与用量汇总](RUN_SUMMARY.json) · [任务状态](TASK_STATUS.json) · [机器语义复核](RECOVERY_SEMANTIC_AUDIT.md)

| 环境 | 旧结果 | 修复后同一完整 attempt | actor / user 调用 | input / output tokens |
|---|---|---|---|---|
| WebShop | 1/2；奖励 2/3、1 | attempt_001：2/2；奖励 1、1 | 22 / 0 | 148,590 / 2,607 |
| τ-bench | 0/2；奖励 0、0 | attempt_01：2/2；奖励 1、1 | 19 / 11 | 265,872 / 8,748 |

模型均为 `gpt-6-astra / xhigh`。本轮新增 52 次真实调用，已保留恢复尝试：WebShop 1 组、τ-bench 1 组。输入 tokens 已包含缓存子集和固定运行时开销；订阅调用美元成本未知。

## 修复及可见证据

**WebShop：购买前核对全部约束。** 原任务 0 在颜色和价格满足时过早购买，功能属性得分为 0。新策略要求拆解类别、功能、选项和价格，读取商品说明、比较候选后再购买。模型通过普通搜索自行发现可见 Features 含 `oral hygiene` 的候选，并选择蓝色；任务 1 核对口味与包装数量。预算 20→40，实际使用 [15, 7] 步；未注入目标 ASIN、参考路径或隐藏 goal。两个任务使用同一冻结策略、同一完整 attempt，未跨 attempt 拼接成功。

证据：[新验收与奖励拆分](webshop/recovery_20261011/acceptance.json)、[全部新运行](webshop/recovery_20261011/results/)、[旧部分得分轨迹](webshop/results/run_20261009/case_000/trajectory.json)。

**τ-bench：先澄清目录名称，再请求确认。** 原失败停在用户要求 `Google Home`、目录标签 `Google Assistant` 的差异。新策略没有宣称兼容性，按工具原词询问这是否是用户所指选项。用户模拟的真实回复明确确认，再执行换货。任务 0 使用允许的无背光键盘备选并换温控器；任务 1 保留不可替代的键盘，只换温控器。所有修改在确认后一次提交，最终数据库与原官方参考状态一致；步数预算仍为 30。

证据：[新验收、用户输入重建与 DB 哈希](tau_bench/recovery_20261011/acceptance.json)、[全部新运行](tau_bench/recovery_20261011/results/)、[旧零分轨迹](tau_bench/results/run_20261009/)。目录释义来自模拟用户澄清，不等于已验证真实设备兼容性。

## 严格验收

- 每套固定原任务索引 `[0,1]`，最新完整双任务 attempt 中每项都须 `reward=1、won=true、done=true`；部分得分、零分、漏任务或替换任务均拒绝。
- 从原始事件核对模型响应与执行动作，重建 actor 可见输入；核验 `gpt-6-astra / xhigh`、系统指令、schema、隔离工作目录及禁用外部工具设置。
- τ-bench 重建官方用户系统提示与完整对话输入，确认未插入参考答案或强制用户授权；另做机器语义审计。
- 在固定官方代码与数据中从初始状态逐步重放，核对 observation、终止、奖励、τ-bench 实际 DB 与参考 DB 哈希，并执行原评分器正负对照。
- 新增失败关闭门禁：开始/失败时 `publication_allowed=false`，全部通过后才为 true。全局共 **86 项测试通过**，验收阶段零次模型调用。

原 Who&When 与 ALFWorld 结果保持不变。真人审计为 pending，机器语义审计不替代真人审计。

## 研究边界与复验

这是已观察失败后调整策略的固定开发集重跑，不能作为无调试的 pass@1、全量 benchmark 准确率、独立测试收益或自进化效果。WebShop 增加步数预算、τ-bench 重新采样用户对话，尚不能单独识别策略修改的因果收益。下一阶段效果实验需要独立任务划分、冻结干预与多次重复。

```bash
.benchmark_cache/venv/bin/python machine_work/benchmarks/_shared/accept_success.py
```

该入口只验收已有证据，不重调模型。真实重跑必须另建 append-only attempt，保留所有失败和用量。
