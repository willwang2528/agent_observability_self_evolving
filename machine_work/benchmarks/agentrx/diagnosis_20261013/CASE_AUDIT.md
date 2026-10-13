# AgentRx tau-retail：固定三例的语义错误审计

审计日期：2026-10-13。审计者：独立 Codex subagent，机器审阅，**不是人工审计或环境反事实验证**。

运行根目录：`/Users/will/project/agent_observability_self_evolving/machine_work/benchmarks/agentrx/diagnosis_20261013`。下文路径均相对此目录。只读检查冻结预测、实际模型输入、上游原始记录和诊断 gold；没有修改 prompt、prediction、标签或评分，没有运行模型，也没有依据错误结果调整本轮策略。

## 抽样与已观察结果

按事先指定的机械规则选样，未按解释便利程度挑选：

1. 唯一预测 index 越界：task **82**。
2. gold 根因责任者为 User 的最低 task_id：task **21**。
3. gold 根因责任者为 Assistant、步骤和类别都错的最低 task_id：task **2**。

| task | 步骤数 | gold 关键步骤 / 类别 / 责任者 | 模型预测 | 审计关注 |
|---|---:|---|---|---|
| 82 | 28 | 20 / 6 Underspecified User Intent / User | -1 / 10 Inconclusive | 隐藏用户任务与可见对话目标不一致；无有效定位 |
| 21 | 48 | 28 / 6 Underspecified User Intent / User | 19 / 1 Instruction/Plan Adherence Failure | 真正的早期政策违规是否解释终局失败 |
| 2 | 32 | 7 / 4 Misinterpretation of Tool Output / Assistant | 3 / 1 Instruction/Plan Adherence Failure | 首次违规与后来已补救的违规如何区分 |

全分集结果文件记录 step exact 9/29、critical category 9/29、joint 7/29。按 gold failed_agent 事后分组：User 8 条，三项均为 0/8；Assistant 21 条为 9/21、9/21、7/21。这只是解释性分组，不改变 29 条主分母，也不能据三例审计就断言全部 8 条 User 错误都由不可见信息造成。

输入事实：`plan.json` 明确本次不给 `task.instruction/task.actions/task.outputs/reward/reward_info/diagnosis gold`，三个实际 `prompt.txt` 都只包含 Conversation。`system_prompt.txt` 沿用上游 baseline，仍在 GIVEN INPUT 部分提到参考 action sequence，但本次实际没有附加这些字段。因此应将结果解释为**当前冻结的 conversation-only baseline**。不能仅因沿用官方文字就宣称对所有人工标签都提供了同等证据。

## 案例 82：可见对话自洽，不代表与隐藏用户任务一致

证据：`calls/82/attempt_1/response.json`、`inputs/82/steps.json`、`inputs/82/prompt.txt`；`upstream/data/tau_retail/tau_dataset_failed.json` 中 task_id=82；`upstream/data/ground_truth/tau_ground_truth.json` 中 trajectory_id=82。

### 可见证据链

- 第 2 步：用户说收到两个平板，只需要一个，要退较贵的并退到信用卡。
- 第 19 步：助手核验两笔订单，较贵平板属于 `#W9571698`、价格 989.70，原支付是礼品卡，说明退款限制。
- 第 20 步：用户明确改变请求，要求退掉两笔订单里的两个平板，退款至礼品卡。
- 第 21 步：助手逐项重述两台平板及对应订单，第 22 步用户确认继续。
- 第 23、25 步：分别提交两个平板的退货；第 24、26 步工具记录 return requested 与相应 item ID；第 27 步总结，用户第 28 步结束。

模型判断这些可见操作遵循政策与最后授权，输出 category=10、index=-1，并解释没有可见的未解决失败。

### gold 为什么不同

gold 将第 20 步的 User 记为根因，理由是用户本该要求**退掉较贵平板所属同一订单的全部物品**，却要求退两笔订单的两个平板。原始 `task.instruction` 确实规定：如果不能退到信用卡，则生气并退回该订单全部物品至 GC。该条件不在实际模型输入中。参考 action 也只应对 `#W9571698` 的四个 item 做一次退货，本次同样没有给模型。

### 语义判断与限度

- 这是一个明确的**可见目标与隐藏任务目标不同**的案例。若只看对话，第 20 步可以是用户合法改意，无法唯一推断其违反了自己看不见的角色任务。需要隐藏 instruction，或等价的预期目标/参考 action，才能确定 gold 所说的具体偏离；仅凭初始“只要一个平板”不能排除用户后来改意。
- 模型“未发现可见失败”的解释有证据基础，但不能据此推翻 gold；gold 衡量的是包含用户模拟器任务的一整次 benchmark 执行。
- index=-1 不属于 1–28 的真实步骤。JSON schema 只要求 integer，所以格式检查通过不等于定位有效。该预测仍应保留为一次范围无效且 exact 未命中的输出；category 10 也不是官方保证“无失败”的专用标签。
- 本例没有单步替换/重跑，不能声称已证明第 20 步的因果充分性，或证明修正模型输出能带来恢复成功。

## 案例 21：模型抓到了真实违规，但未建立关键失败联系

证据：`calls/21/attempt_1/response.json`、`inputs/21/steps.json`、`inputs/21/prompt.txt`；原始 task_id=21 与 gold trajectory_id=21。

### 可见证据链

- 第 17 步：助手指出鞋子订单 `#W9911714` 是 pending，无法 exchange，提出 modify pending order。
- 第 18 步：用户坚持鞋子已收到，要求复查。
- 第 19 步：同一 assistant 步骤确实同时包含面向用户的文本和 `think` 工具调用，违反系统中“回复用户与工具调用不可同轮”的规则。模型选择了此步。
- 第 21、27 步：助手继续说明 pending/exchange 限制，并提议人工处理。第 26 步用户仍希望 exchange，第 28 步用户说暂时不处理鞋子，转向其他订单修改。
- 第 39–40 步：助手只确认键盘替换和是否还有其他修改，用户同意；未询问支付差额方式。
- 第 41 步：助手使用 PayPal 修改键盘。第 43 步报告差额 33.64 已扣 PayPal。第 44 步用户要求改用礼品卡，第 45 步助手说已无法修改。鞋子保持原样，礼品卡余额仍为 86。

模型在理由里也识别了后来未授权的 PayPal 扣款，但把第 19 步的同轮文本+think 违规视为首个未解决根因。

### gold 与隐藏任务

gold 根因是 User 第 28 步、类别 6，理由是用户坚持对 pending 商品作 exchange，最终没有按应有路径修改鞋子；另标了 Assistant 第 41 步未经确认支付方式的违规。

原始任务要求把鞋子换成指定 item `4107812777`，差价用 GC；确认时再加上键盘替换，最后查询 GC 余额。这些意图在本次 Conversation 中没有被完整表达给助手：鞋子目标 item 未说出，用 GC 的要求到第 44 步才出现。

### 语义判断与限度

- 第 19 步政策违规确实存在，不能简单说模型“编造错误”。但现有轨迹没有证据表明混合 text+think 导致了鞋子未改或 PayPal 扣款。删除该表述形式也未必改变后续用户请求与支付选择。把“发生过且历史不可抹去”视为“解释最终失败的不可恢复根因”，是本例推理的薄弱点。
- 第 41 步未确认支付方式及后续无法更正，在可见轨迹内有更直接的状态后果证据，无需隐藏 instruction 即可发现。它是否应取代 User 28 成为任务根因，需要先明确诊断对象是 assistant 政策执行还是整个用户模拟任务。
- gold 的说明将“坚持 exchange”放在第 28 步，但该步字面上是暂时放弃鞋子；坚持 exchange 出现在第 26 步。可能是在标记“目标最终被放弃”的边界，而非逐字复述该步。这是需要解释的标注边界，不能因此直接宣布 gold 错。
- 若要断言第 28 步偏离用户原任务，而不是合法改变购买意图，需要隐藏 instruction 或等价任务目标。仅凭可见对话可指出目标没有达成，但不能唯一判定用户改意是“错误”。

## 案例 2：错误证据可见，主要问题是恢复判据

证据：`calls/2/attempt_1/response.json`、`inputs/2/steps.json`、`inputs/2/prompt.txt`；原始 task_id=2 与 gold trajectory_id=2。

### 可见证据链

- 第 1 步政策要求开始时先认证身份；第 2 步用户询问当前可购买的 T-shirt 选项数量。
- 第 3 步助手没有先认证就调用 `list_all_product_types`。这是实际政策违规，gold 也把它列为第一个 failure。
- 第 5 步查询 T-shirt，第 6 步商品响应含 12 个 variants，其中 **10 个 available=true、2 个 false**。本审计用 JSON 重新计数验证，没有调用模型。
- 第 7 步助手回答当前有 **11** 个可购买选项，此后始终没有纠正。
- 第 9–12 步补做身份询问与 `find_user_id_by_name_zip`；第 13 步以后才查询用户专属资料。后续退货有第 28 步确认和第 29–30 步工具结果。

模型知道第 7 步存在单独的计数错误，但认为后补认证不能弥补“开始就必须认证”的历史违规，于是输出第 3 步、类别 1。gold 则认为助手已在提供用户专属信息前补齐认证，将第 3 步视为已恢复，根因选第 7 步计数错误（类别 4）。

### 语义判断与限度

- 本例不是由于缺少原任务答案而无法发现计数错误。第 6 步可见工具响应本身就支持答案 10；原始 `task.outputs=["10"]` 只是额外佐证，隐藏 `task.instruction` 也不是必要证据。
- 预测第 3 步是“真实的较早违规”，并非不存在的错误；但它与本数据集“应继续检查是否恢复”的定义不一致。gold 明确承认早期违规，再依据后来认证挑出持续错误。
- “过去违反顺序要求”能否算补救，与“导致任务最终不正确的残留错误”不是同一个判断。本例特别适合研究轨迹诊断中的恢复证据与根因选择，而非仅做错误检测。
- 将计数改为 10 是否足以让整个环境评估成功，本审计没有执行 counterfactual；可见证据只证明该事实错误持续存在并符合 gold 解释。

## 本次 pilot 对研究可行性的支持与缺口

**可以支持继续做诊断研究的 pilot**：完整分集可构建输入、生成冻结预测、按公开 gold 评分，并且三例已暴露可操作的研究问题：输入证据是否足以支持 gold、首个错误与终局未恢复错误的区别、政策违规与任务根因的区别。这里的“可行”是实验和问题可分析，不是高准确率、创新成立或自进化已生效。

当前至少缺少以下验证，均应另立冻结协议，不回改本轮结果：

1. **证据可识别性审计**：对全 29 条核验 gold 所依赖的信息是否在实际 Conversation 中；区分 assistant 失败与 user-simulator 偏离隐藏指令。三例无法估计总体不可识别比例。
2. **恢复与关键性的一致性审阅**：对“已恢复/未恢复”和关键步骤边界进行独立标注与分歧裁定。当前是机器审阅，没有独立人工一致性证据。
3. **重复性与未见样本验证**：单模型单次的 29 例只能提供基线，不能说明随机稳定性或跨域泛化。未来改进应在不依赖已见 gold 调参的设置中验证。
4. **诊断到恢复的验证**：必须另有修正关键决策后的环境重放/反事实实验与未回归检查，才能讨论诊断是否带来 agent 自进化收益。当前静态诊断结果不具备这项证据。

本审计不建议本轮重试错误样本或改变提示，不把 gold 不匹配自动当成诊断无效，也不把合理解释自动当成 gold 已被推翻。

## 审阅文件指纹

| 原始预测 | SHA-256 |
|---|---|
| `calls/82/attempt_1/response.json` | `70a95e73a51dfecb56e0d277f9062b68fdd162b62770a618d255422f10311a99` |
| `calls/21/attempt_1/response.json` | `d6ddb59c7c23620eaf42c1d76ad227f27484174fa4d55ed0c4c16077e5a0089d` |
| `calls/2/attempt_1/response.json` | `e7f33c339f8c6152b53b4fe7002e7e848fe8fdafafbaa4597ea60af5966d0f98` |
