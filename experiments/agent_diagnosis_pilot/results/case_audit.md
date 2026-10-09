# Pilot 个案证据审查

这是独立的事后人工审查，依据冻结的原始数据、已保存的模型输入与真实预测。它不产生新 gold，不修改标签、提示词或评分，也没有追加模型调用。四例用于解释现象，不代表总体频率或显著性结论。

## 输入完整性核对

- 24/24 个保存的 prompt 与计划中的 SHA-256、输入元数据和从固定源文件重新生成的文本一致；6 个代码／协议文件的冻结哈希一致。
- 将每份源记录中 question、system_prompt、history 以外的所有顶层字段删除或改为哨兵值，24 个 prompt 均不变。模型输入没有显式 ground_truth、mistake_agent、mistake_step、mistake_reason、question_ID、is_correct 或 is_corrected 字段。
- algorithm_106、algorithm_038、algorithm_083、algorithm_101 的两个条件输入文本及 SHA-256 完全相同，分别由独立进程、独立临时目录和新 ephemeral session 调用。
- 本文件四例的可见步骤还直接从 prompt 的 `[step N]` 标记抽取，并与 input_metadata.json 对照通过。下述“可见”指真实保存的模型输入，不仅指裁剪算法的预计结果。
- runner 不读取独立的 data/gold.json，输入构造不使用答案或诊断标签。原始 JSON 在 Python 中载入时仍含这些字段，因此不能声称注释从未进入程序内存；上述反事实检查验证它们不影响模型输入。

## 1. handcrafted_012：保留错误步骤，仍可能失去诊断所需的来源证据

原 gold 为 Assistant，step 16。任务要求比较两个票房榜单的前十名，计算交集。

原始轨迹中：

- step 8 的来源表给出 worldwide 排名，前十包含 Demon Slayer。
- step 12 的另一张表按 domestic 票房排序，其第十个数据行是 Demon Slayer，第十一个是 Wonder Woman 1984；表内 Rank 一列仍是原 worldwide 排名，不能把该列当成当前排序的行序号。
- step 16 的 Assistant 整理 domestic 前十时将 Demon Slayer 换成 Wonder Woman 1984，随后对自己展示的两份列表算出交集为 5。该算术相对于已经抄错的列表是自洽的；对照 step 8 与 step 12 的原始前十，交集应为 6。

| 条件 | 真实输入可见步骤 | 真实预测 | 模型引用证据 | 严格 joint |
|---|---|---|---|---|
| full | 0–19 | Assistant @ 16 | 8、12、16 | 1 |
| head_tail_12000_chars | 0–4、14–19 | 有效弃权，agent/step 均 null | 0、16 | 0 |

预算输入保留了 gold step 16，却删除了两张来源表所在的 step 8 和 step 12。预算条件的模型说明：step 16 内部确实能算出 5，来源获取过程缺失，无法确认哪张列表不正确以及由谁引入。完整条件则明确定位了第十名替换错误。

**可支持的个案判断：** 错误步骤可见性不足以衡量诊断证据的保留；本例需要“来源表 → 摘录列表 → 计算结论”的跨步骤证据链。此处尚未测试任何新的证据选择方法。

证据文件：data/upstream/Who&When/Hand-Crafted/12.json，以及 results/runs/handcrafted_012__{full,head_tail_12000_chars}/{prompt.txt,input_metadata.json,result.json}。

## 2. algorithm_106：发现核验失败，但归因停在下游确认环节

原 gold 为 DataAnalysis_Expert，step 0，理由是最初提供的信息错误并导致错误结论。

- step 0 已将 5,200,000 美元作为待确认的最高价格，并陈述多个房地产站点的价格摘要；轨迹没有相应交易记录供检查。
- step 1 的 Verification_Expert 复述价格摘要，将地点、年份与楼型条件视为满足，确认该数字。
- step 3 的 RealEstate_Expert 再次称核验充分并重复结论。

两个条件的真实输入均完整保留 step 0–5，文本和 SHA-256 相同。两次独立调用均预测 Verification_Expert @ 1，引用 0、1、3；who、when、joint exact 均为 0，步骤距离为 1。

模型指出了“把继承的摘要当成经过核验的交易事实”，但将责任定位在首个明确确认环节，而原标签定位在最初价格信息的引入。它没有将 step 0 的信息起点作为 decisive step。

**可支持的个案判断：** 识别出无证据核验链，与准确定位标注所要求的最初错误，存在差距。由于 trace-only 协议没有提供任务正确答案、真实交易数据或反事实执行，本例不能独立证明哪个实际价格正确，也不能把两个相同输入条件的结果解释为裁剪效应。

证据文件：data/upstream/Who&When/Algorithm-Generated/106.json，以及 results/runs/algorithm_106__{full,head_tail_12000_chars}/{prompt.txt,input_metadata.json,result.json}。

## 3. handcrafted_021：任务未完成、环境异常与责任标签之间的边界

原 gold 为 WebSurfer，step 4；标注理由是未能及时定位论文及其致谢部分，延误 NASA award number 的识别。

- step 4 是针对文章作者、日期与网站的初始搜索，结果包括后续打开的目标文章；仅从该步不能直接读出一个清楚的不可恢复错误。
- 后续页面滚动位置从 9%、18%、27% 推进到 37%；Orchestrator 的 ledger 同时将重复滚动描述为循环或缺少进展。
- step 24 包含 Azure content-filter 拒绝导致的异常栈，发生在 Orchestrator 的 ledger 更新调用。轨迹随后打印最终答案，但没有展示从论文致谢取得该答案的来源证据。

| 条件 | 真实输入可见步骤 | 真实预测 | 模型引用证据 | gold step 4 可见 |
|---|---|---|---|---|
| full | 0–24 | 有效弃权 | 20、24 | 是 |
| head_tail_12000_chars | 0–3、21–24 | 有效弃权 | 21、22、24 | 否 |

模型在两条件下都未将“检索迟缓”直接等同于“导致环境 API 中断的 agent 错误”；完整条件还指出滚动仍在推进。两次弃权按冻结协议计 0 分，不修改原标签。

**可支持的个案判断：** trace-only 因果诊断与该数据集的人工责任归因可能存在目标边界。这里至少需要区分任务未完成、步骤效率问题、环境中断以及最终答案缺少来源证据。人工审查不据此断言原标签错误，也不声称已确认 content-filter 的触发原因。

证据文件：data/upstream/Who&When/Hand-Crafted/21.json，以及 results/runs/handcrafted_021__{full,head_tail_12000_chars}/{prompt.txt,input_metadata.json,result.json}。

## 4. handcrafted_031：删除早期决策后，定位从最初接受候选漂移到最终错误确认

原 gold 为 Orchestrator，step 9；标注理由是没有确认搜索结果完整，就转为逐一检查候选。

- step 8 的搜索列表混合了 Point Pleasant, WV 与 Mount Pleasant 的候选，未给出满足驾驶距离约束的完整验证。
- step 9 接受列表为“附近健身房”，把后续验证缩窄为设施类型（fitness center 与 gymnastics center）。
- step 24 和 step 28 分别展示候选位于 South Carolina 的地址；step 29 仍宣布所有候选已满足 West Virginia 目标地点附近的距离条件并完成核验。

| 条件 | 真实输入可见步骤 | 真实预测 | 模型引用证据 | 严格 joint |
|---|---|---|---|---|
| full | 0–31 | Orchestrator @ 9 | 8、9、24、25、29 | 1 |
| head_tail_12000_chars | 0–4、26–31 | Orchestrator @ 29 | 0、28、29 | 0 |

预算条件删除 step 8 和 gold step 9，但保留了 step 28 的 South Carolina 地址和 step 29 的完成声明。因此预算条件仍能发现同一个 Agent 的地理约束核验失败，却定位到更晚的显性错误确认；相对原标注步骤偏移 20。

**可支持的个案判断：** 保留末尾明显矛盾有利于发现异常，但可能丢失最初接受错误候选的决策位置。还应注意：完整条件虽命中原 gold 的 agent/step，其解释强调地理约束失守，而原标签解释强调搜索完整性；定位命中不能替代对自然语言解释质量的单独检查。

证据文件：data/upstream/Who&When/Hand-Crafted/31.json，以及 results/runs/handcrafted_031__{full,head_tail_12000_chars}/{prompt.txt,input_metadata.json,result.json}。

## 解释范围

上述四例只支持提出待检验问题：轨迹缩减应保存哪些跨步骤来源与决策依赖；怎样区分错误引入、错误传播和最终失败；何时证据不足应允许弃权。它们不构成新方法的有效性证据，也没有验证诊断后修复或在未见任务上的持久自进化。
