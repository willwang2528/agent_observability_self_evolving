# AgentRx τ 轨迹诊断运行报告 — 2026-10-13

固定公开 GitHub 快照的 **29/29 条失败轨迹已真实完成诊断和官方离线评分**。配置 `gpt-6-astra / xhigh`，每条一次，29次实际尝试，失败尝试0次。全部预测保留，无按准确率重试。

## 结果

| 指标 | 结果 | 定义 |
|---|---:|---|
| 有效模型响应 / 评分覆盖 | 29/29 | 全部预定轨迹均有完成事件、结构化响应和评分 |
| 根因步骤 exact | 9/29（31.0%） | 预测步骤与根因 gold 整数相等 |
| 根因类别 exact | 9/29（31.0%） | 预测类别与根因标签相等；官方 Correct cases |
| 步骤 + 类别联合 exact | 7/29（24.1%） | 两者同时正确；本地补充指标 |
| 步骤 ±1 | 10/29 | 步距 ≤1 |
| 步骤 ±3 | 14/29 | 步距 ≤3 |
| 步骤 ±5 | 18/29 | 步距 ≤5 |
| 平均绝对步距 | 6.3103 | sum(abs(pred-gold))/29 |
| 预测步骤越界数 | 1 | 越界同样记入分母 |

按 gold 责任主体分层（只作描述分析，不改变主分母）：

| gold 主体 | N | 步骤 exact | 类别 exact | 联合 exact |
|---|---:|---:|---:|---:|
| Assistant | 21 | 9 | 9 | 7 |
| User | 8 | 0 | 0 | 0 |

## 固定协议与证据

- 来源 commit：`7a18c79708e7671be15124460f4f7296107c2a55`，见 [来源与候选筛选](SELECTION.md)、[来源许可](SOURCE_NOTICES.md)。原始数据、标签、官方源码完整保存在 `upstream/`，SHA-256 冻结于 [plan.json](plan.json)。
- 输入：29条，1,064步；官方 `load_trajectories` → `tau_bench_ir` → `Conversation: str(steps)`，步骤从1开始。每条首步保留政策，完整保留对话与工具信息，无轨迹裁剪。最长模型 user prompt 59,796字符。
- 模型：配置 `gpt-6-astra / xhigh`，Codex CLI `codex-cli 0.162.0-alpha.17.2`，并发3，超时600秒，仅传输/格式失败最多2次。实际全部 attempt_1 完成。API未提供底层模型权重版本，本报告记录请求的模型配置和运行时版本。
- 隔离：空临时工作目录、忽略用户配置、禁用 shell/网络/文件工具、memories、skills/plugins/apps；每次原始 events 中零工具调用。所有最终事件JSON与 response.json 一致。
- 标签边界：模型不接收人工根因步骤、类别或解释。prepare 仅为 gold 源文件计算校验和，不用标签内容构造输入；解析和比较标签发生在离线评分。见 [协议补充](RUN_NOTES.md)。
- 适配：官方 system prompt 放入 Codex model_instructions_file，官方 user prompt 从 stdin 输入，增加 JSON 输出约束。没有生成 AgentRx 静态/动态约束，没有引入 violation log 或 few-shot examples。
- 评分：未修改的官方 `Report.compute_stats()` 与 `analysis()`；完整29条覆盖前置检查，另行重算步骤/类别/联合及步距。gold-as-prediction 得29/29，所有step平移+1得0/29，验证评分器能区分正确/错误步骤。

## 执行记录

- 原始时间（UTC）：2026-10-13T04:04:06.454867+00:00 → 2026-10-13T04:12:16.212477+00:00，墙钟约 8.2 分钟。
- 原始 CLI usage：input 403,765，cached input 20,736，output 29,516 tokens。缓存是input子集，不额外相加。
- 每次请求：`inputs/<task_id>/prompt.txt`；原始步骤：`inputs/<task_id>/steps.json`。
- 每次调用：`calls/<task_id>/attempt_1/`，含 command、输入/计划哈希、起止时间、events、stderr、原始 response 与验证结果。
- [逐例 CSV](evaluation/per_case.csv) · [完整官方结果](evaluation/official_results.json) · [原始调用审计](evaluation/call_audit.json) · [本地验收](evaluation/acceptance.json) · [评分正负对照](evaluation/scorer_controls.json)。
- 独立 subagent 从原始数据、模型事件与原始官方函数重新核验，结果见 [独立复核](INDEPENDENT_AUDIT.md)。独立复核不等同真人审计。

## 固定三例语义复核

[CASE_AUDIT.md](CASE_AUDIT.md)记录任务82、21、2的输入、预测、gold及逐步证据。82的gold依赖模型未见的隐藏用户目标；21和2暴露了真实违规、恢复判据与关键失败选择的差别。这是机器语义分析，未作环境反事实验证，未修改任何预测或标签。

## 结果边界

本轮跑通的是**固定公开 GitHub 快照的29条诊断 baseline**。最新论文v2报告tau39条、全量170条；本次没有跑完这些最新版规模。论文默认gpt-5且重复3次，本地为另一模型单次，不能直接宣称复现论文表格或优于论文方法。

官方模板声称提供ground-truth actions，但该commit实际只传steps，顶层task.instruction、reference actions和outputs都未提供。本轮保留官方代码行为。部分gold涉及User未表达私有任务要求，预测不一致可能涉及证据不可见、标签语义或推理错误；不能仅据exact分数确定原因，也没有为提高分数补入隐藏字段。

目前只验证轨迹诊断的可执行性和一次基线水平。诊断解释的因果正确性、诊断驱动修复、持久自进化及未见任务收益仍待后续实验。该29条公开数据可作为pilot，正式paper需要独立开发/测试划分、多次重复与额外数据域。
