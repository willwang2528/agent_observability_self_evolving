# τ-bench 两任务修复实验（2026-10-11）

**结果：`attempt_01` 两个原固定任务全部成功，官方奖励 1、1，终止状态均为 true；独立验收 PASS。** 共 19 次 actor 调用、11 次用户模拟调用。未发生新的低分重试；原始两条 0 分轨迹仍完整保留。见 [acceptance.json](acceptance.json)。

这是对已经观察过失败的 **retail test 索引 0、1** 做开发修复。不能作为独立测试集准确率、全量 τ-bench 结果或自进化收益。原始 `results/run_20261009/` 的文件全部保留，逐文件哈希记录在本目录的 `protocol.json`。

## 旧失败与修复边界

旧两条轨迹都完成了身份验证、商品查询和价格计算，但没有修改订单，奖励均为 0。用户任务使用 `Google Home`，目录使用 `Google Assistant`；actor 将该命名差异解释成无法核实兼容性，模拟用户随后要求暂停交换并转人工。官方参考动作则选择目录中的相应 Google Assistant 选项。

这暴露了任务描述与目录命名的歧义，不能把未获授权的旧轨迹直接改成成功，也不能编造硬件兼容保证。修复只在官方 policy 后增加通用对话策略：先用目录原词中性澄清用户的选择，明确区分偏好澄清与最终交易授权。策略不包含这些具体平台名字、产品 ID、任务 ID、标准答案或参考动作。若用户仍坚持工具不能证明的要求，actor 应如实说明并尊重限制。

用户模拟器没有改动：私有 instruction 仅传给用户模型，使用官方 `LLMUserSimulationEnv` 系统提示；每条回复由真实 `gpt-6-astra / xhigh` 调用生成，不预置回复，不强制用户同意，不向 actor 暴露参考动作或隐藏数据库。actor 同样为 `gpt-6-astra / xhigh`，工具、官方数据库、任务和评分器不变。

## 重跑与严格验收

从仓库根目录运行：

```bash
.benchmark_cache/venv/bin/python machine_work/benchmarks/tau_bench/recovery_20261011/run.py attempt_01
.benchmark_cache/venv/bin/python machine_work/benchmarks/tau_bench/recovery_20261011/verify.py
```

已有 attempt 目录拒绝覆盖。后续开发重跑必须使用新的 `attempt_XX`；全部尝试保留，不能拼接不同尝试的成功任务。本版本配置已由 `protocol.json` 冻结；改策略需另建版本。`acceptance.json` 只有在最后一个完整双任务 attempt 同时达到官方奖励 **1、1** 且通过离线核验后才标记 PASS；验收失败会写入 FAIL。

验收覆盖原始模型响应与执行动作一致、actor 输入逐字重建、用户官方系统提示及完整对话逐字重建、模型命令/隔离配置/指令/schema 检查、官方初始数据库逐步重放、最终实际数据库哈希等于官方目标哈希、官方评分正负对照、官方 tracked 源码（含 staged）与数据哈希、旧运行逐文件哈希。

`results/attempt_*/` 保留全部对话、工具反馈、原始调用、usage 和分数；`attempt_*.log` 为可读日志。订阅调用美元成本未知。自动核验不等于真人审计，人工入口见 `human_audit/benchmarks/tau_bench/`。

## 结果解释与验收修正

Task 0 在 9 个 actor 步骤后完成双物品交换；task 1 在 10 步后仅交换温控器、保留键盘。两条轨迹都由用户模型先明确接受目录原词，再在已知价格差和付款方式后授权操作。actor 没有声明真实硬件兼容保证。因本轮同时重新采样了用户回复，不能把前后奖励变化单独归因于策略，也没有独立泛化或自进化收益证据。

首次自动验收机械要求最终确认含字面 `yes`，误拒了 task 1 的明确 `proceed with` 授权。该 FAIL 原样保存在 [verification_history/001_literal_yes_false_rejection.json](verification_history/001_literal_yes_false_rejection.json)。随后修正的是验收器对明确授权表达的识别，并增加真实授权正例及否定授权负例；没有修改冻结 runner、策略、模型输出、用户指令或官方分数。确认文本的自动检查只是必要条件，语义复核见 [机器语义复核](semantic_audit.md)，仍待真人审计。

负对照回归：13 项通过，日志见 [verification_tests.log](verification_tests.log)。
