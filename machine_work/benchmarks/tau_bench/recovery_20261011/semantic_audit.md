# τ-bench 修复：机器复核记录，待真人审计

状态：由 Codex 生成，并经另一 Codex 子代理只读复核；**没有声称真人已审计**。

实验固定为官方 retail test 索引 0、1；选中 `recovery_20261011/results/attempt_01`，两项奖励均为 1。共 19 次 actor、11 次用户模拟真实调用，官方数据重放和目标数据库哈希匹配。原始 2026-10-09 两条失败轨迹保持逐文件哈希不变。

## Task 0

- actor turn 6 原样呈现目录标签，询问用户是否将 `Google Assistant` 作为其所说的 `Google Home` 选项；没有声明技术兼容保证。同时列明全尺寸 clicky 无背光键盘、黑色温控器、价格和 $16.63 退款。
- user call 3 自主生成 `Yes, Google Assistant is what I mean by Google Home`，并明确要求同时交换两项、退差价到原卡。
- actor turn 7 执行官方交换工具；turn 8 据工具成功结果告知，用户以 `###STOP###` 结束。
- 实际最终 DB 哈希：`5ed21c65cf9e8d0c20ad0210721146bb6abad19bedce7c2e08472311dabbeec8`，等于官方目标哈希。

## Task 1

- actor turn 6 如实告知 full-size clicky/RGB 键盘缺货，依用户要求保留键盘；对温控器使用目录原词进行中性澄清。user call 3 明确接受 Google Assistant 和黑色，仅交换温控器。
- actor turn 7 告知 $249.01 价格和 $13.46 退款，询问退款方式。user call 4 自主生成：`Please refund the $13.46 to the original credit card and proceed with the thermostat-only exchange, leaving the keyboard unchanged.`
- 这是已知交易详情后的明确授权，语义相当于 yes；不必包含字面 yes。actor turn 8 执行交换，turn 9 告知结果，用户以 `###STOP###` 结束。
- 实际最终 DB 哈希：`4adebec00ba70d55dd0c5a53c768d8853f475d0cec8f2b1264887c3602fb86a3`，等于官方目标哈希。

## 审计边界

- 通用策略不含商品名、Google 平台名、商品 ID、订单 ID、任务标签或参考动作。官方用户系统提示、私有 instruction 和全部对话在验收中逐字重建；没有强制用户回复。
- 这些成功说明本次用户澄清后的模拟交易达到了官方状态目标，不能据此证明真实设备兼容、所有 policy 条款全面正确、全量 benchmark 成功或跨任务泛化。
- 本轮是已观察失败后的开发修复，同时重新采样了模型与用户回复；没有消融实验，不能单独归因于策略，也不是自进化方法有效性证据。
- 首次验收的字面 yes 误拒及修复已保留；只修验收器，未改轨迹或官方奖励。13 项回归覆盖输入/配置/响应篡改、未确认和否定授权。

[完整验收](acceptance.json) · [全部原始证据](results/attempt_01/)
