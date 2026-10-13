# 运行过程 — 2026-10-13

1. 检索并读取 AgentRx、TRAIL、AgentErrorBench 官方论文/仓库/数据。独立研究 subagent 核验来源和实际下载。候选及取舍见 SELECTION.md。
2. TRAIL 全 split raw 轨迹最长约 9 MB，发现坏 JSON、部分无效 span gold，以及官方 scorer 跳样本问题。选择能够完整输入的 AgentRx τ-retail 29 条；保留 TRAIL 为后续长轨迹研究候选。
3. 固定 AgentRx commit 7a18c79708e7671be15124460f4f7296107c2a55。核对 29 条 raw 与 29 条 gold 的 ID 一致、共 1064 步。未用同库只有 24 条的旧 gold。
4. 阅读官方实际调用：baseline 只发送 Conversation: str(steps)，不传 task.instruction/reference outputs；保留此行为和模板声称提供参考动作的已知差异。
5. 从官方源码 AST 选择未修改的函数，绕开 Azure/TRAPI 客户端初始化，使用隔离 Codex CLI 做模型传输。原始 CLI 事件持续写入，超时现场也保存。
6. 使用 test-driven-development 技能，由子代理先写并验证失败的协议测试，再实现适配器。加入调用完成/出错/工具污染/响应篡改等负面对照；格式外预测失败，整数步骤越界和 no-error 预测作为诊断错误保留计分，不按 gold 重试。

后续原始执行时间和每次尝试见 plan.json、calls/*/attempt_*/metadata.json、execution_history.jsonl。测试及本轮最终结果在执行后补充。

7. 15项协议与事件负面对照测试通过（tests_before_run.log），随后prepare冻结29条全部输入及代码哈希。
8. 执行 `python -u run.py run`，2026-10-13T04:04:06.454867+00:00开始、2026-10-13T04:12:16.212477+00:00结束；29次真实调用全部首轮有效，无重试。每条events持续写盘，最终响应与事件一致。
9. 执行 `python score.py`，29/29全分母；官方评分与手工算术核对通过。步骤9/29、类别9/29、联合7/29。全部模型预测保留；未按gold结果继续调参或重跑。
10. 最新论文v2与GitHub数据规模不同，记录在SELECTION/SOURCE_NOTICES/RUN_NOTES，不改变冻结29例范围。独立subagent复核结果另存INDEPENDENT_AUDIT.md。

11. 独立subagent未依赖项目PASS，直接重新生成官方IR/prompt、核查29次原始events与command，再分别执行官方函数和独立手算。结论PASS_EXECUTION_AND_OFFICIAL_SCORING，与根因步骤9/29、类别9/29、联合7/29完全一致。task82的index=-1保留计错。15项单元测试与4类独立评分对照均通过。

12. 另一独立subagent按固定规则审计task82/21/2，分别记录隐藏目标不可见、实际违规不一定解释终局、恢复判据差异。未因错误样本进行任何模型重试或标签改写，见CASE_AUDIT.md。

13. 发布前再次从仓库入口执行独立验收，PASS。排版检查识别到标准CSV的CRLF与原样官方prompt的尾空格；这些冻结数据保持原字节，排版门禁只检查本地编写的Python/Markdown/JSON。源码、输入、事件与预测不为排版而重写。
