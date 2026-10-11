# 2026-10-11 修复复跑：机器语义复核

状态：四个固定任务未发现阻塞成功判定的语义问题。**这是 Codex 生成的机器复核，真人审计仍为 pending。** 官方重放与评分以 [SUCCESS_ACCEPTANCE.json](SUCCESS_ACCEPTANCE.json) 及对应原生 verifier 为准。下列 turn 均从 0 开始。

## WebShop — attempt_001

[任务 0 轨迹](webshop/recovery_20261011/results/attempt_001/case_000/trajectory.json)：共 15 个真实模型动作，官方 reward=1、done=true。

- turn 0 普通搜索，turn 1 打开原先未满足功能属性的商品。turn 2 的 Features 和 turn 5 的 Description 显示这是儿童商品，未获得完整属性证据。
- turn 6/7 重新搜索，turn 8 从可见搜索结果打开另一候选；turn 9 的 Features 明确包含用户要求的 `oral hygiene`。
- turn 11 选择 blue，turn 14 按可见价格 22.90（低于 60）购买。所选颜色与需求一致，官方属性、选项、类型和价格评分通过。
- 搜索词和商品点击均来自原始模型输出。通用 actor 策略没有目标 ASIN、任务 ID 或参考路径；商品标识只在正常可见搜索结果之后进入对话。

[任务 1 轨迹](webshop/recovery_20261011/results/attempt_001/case_001/trajectory.json)：共 7 个真实模型动作，官方 reward=1、done=true。

- turn 2 的 Features 包含 twelve、Blue Diamond、gluten free；turn 4 选择 pecan，turn 5 选择 pack of 12。
- turn 6 在可见价格 34.44（低于 70）时购买，两个选项与用户指令对应。
- 未发现用隐藏目标或替换模型动作取得奖励的证据。

## τ-bench — attempt_01

[任务 0 轨迹](tau_bench/recovery_20261011/results/attempt_01/case_000/trajectory.json)：共 9 个真实 actor 动作，官方 reward=1、won=true、done=true。

- turn 0 用户提供姓名与 ZIP，turn 1 工具认证，turn 2 确认订单属于该用户且 delivered。
- turn 5 用户确认只换键盘和温控器；键盘要求 full size、clicky、RGB，不可用时允许无背光备选；温控器要求 Google Home 并尽量保留颜色。
- turn 3/4 的工具数据表明所需 RGB 键盘不可用，而无背光备选 269.16 可用；黑色 Google Assistant 温控器 249.01 可用。结合原订单价格，退款为 16.63。
- turn 6 以目录原词询问 Google Assistant 是否是用户所指的 Google Home 选项，没有声称现实设备兼容保证。[user_calls/003](tau_bench/recovery_20261011/results/attempt_01/case_000/user_calls/003/prediction.json) 的真实回复明确确认两者为其所指，并授权双换货和退款至原卡。
- turn 7 唯一一次 exchange 将两个项目一并提交，使用原付款卡；工具返回 exchange requested 和差额 -16.63。其他商品未换。
- turn 8 准确报告已提交请求，用户返回停止标记。最终 DB 与官方参考状态一致，由原生 verifier 独立重放核对。

[任务 1 轨迹](tau_bench/recovery_20261011/results/attempt_01/case_001/trajectory.json)：共 10 个真实 actor 动作，官方 reward=1、won=true、done=true。

- turn 0/1 完成姓名与 ZIP 认证，turn 2 确认订单 delivered，turn 3/4 读取商品选项。
- turn 5 用户明确要求 RGB、full-size、clicky，若不能同时满足则仅换温控器。
- turn 6 actor 保留键盘，并按目录原词中性澄清。真实 [user_calls/003](tau_bench/recovery_20261011/results/attempt_01/case_001/user_calls/003/prediction.json) 明确 Google Assistant 就是其所指，并同意黑色且仅换温控器。
- turn 7 告知替换价格 249.01、退款 13.46，并询问退款方式；[user_calls/004](tau_bench/recovery_20261011/results/attempt_01/case_001/user_calls/004/prediction.json) 明确原卡退款且授权仅换温控器。
- turn 8 唯一 exchange 只提交温控器，原付款卡和差额 -13.46 均与确认一致，键盘未加入交换。
- turn 9 准确报告请求完成，用户停止，官方奖励为 1。

## 额外独立核验

只读审计逐份核对 52 次新调用：WebShop 22 次，τ-bench actor 19 次、user 11 次。原始 `agent_message` 与 `prediction.json` 相等，均有 `turn.completed`，actor 调用数与轨迹步数一致。11/11 份 τ-bench user prompt 完整保留从官方 `tasks_test.py` 读取的原私有 instruction；未删改键盘备选条件或 Google Home 要求。

## 输入与结论边界

τ-bench 使用与原运行相同的官方用户 instruction 和模拟协议；原生 verifier 重建每一份用户系统提示、对话历史及 actor 可见输入。没有删掉用户要求、强迫用户回复或把参考动作加入 actor 输入。用户的澄清只支持本次模拟交易的意图解释，不支持现实硬件兼容性结论。

本轮是在已知失败的固定任务上修改通用策略后重新运行。WebShop 同时增加步数预算，τ-bench 重新生成用户对话；这些结果不能单独证明策略的因果提升、未见任务泛化或持久自进化。全部旧失败继续保留。
