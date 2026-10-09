# Benchmark 选择依据（2026-10-09）

本轮新增 **ALFWorld、WebShop、τ-bench**，保留已执行的 **Who&When**。前三者是交互环境，用于产生可观测轨迹、执行干预并重新评测；Who&When 提供失败归因标签。**交互成功率不能替代诊断准确率**，交互环境本身也不提供人工根因 gold。

“主流”采用可审计的定性标准：除原始 benchmark 论文外，至少三项后续研究在实验部分实际使用，而不是仅出现在参考文献或 GitHub 星标中。下列是已核验的一手实例，不是穷尽引用统计，也不声称取得 citation 总数。

| Benchmark | 后续论文实际使用证据 | 本研究用途 |
|---|---|---|
| ALFWorld | [ReAct](https://arxiv.org/html/2210.03629v3) §4 交互决策实验；[Reflexion](https://arxiv.org/html/2303.11366v4) §4.1、Fig.3 的 134 环境/多次试验；[ExpeL](https://arxiv.org/html/2308.10144v3) §5.1–5.3、Table 5 的经验学习与任务类型结果 | 长程状态、对象与前置条件的轨迹处理；失败后重试、跨任务记忆评测 |
| WebShop | [ReAct](https://arxiv.org/html/2210.03629v3) §4 的交互购物实验；[ExpeL](https://arxiv.org/html/2308.10144v3) §5.1–5.3、Table 5；[LATS](https://arxiv.org/html/2310.04406v3) §5.3、Table 6，明确在 50 条指令比较搜索、反思与强化学习基线 | 搜索证据、商品属性和选择动作的关联；支持诊断后的策略改进和环境重放 |
| τ-bench（历史原版） | [SaMuLe](https://arxiv.org/html/2509.20562v1) §4.4–4.5、Table 3 的反思学习；[AgentRx](https://arxiv.org/html/2602.02475v1) §2，在 115 次 retail rollout 中抽取 29 个失败作诊断标注；[AgentScaler](https://arxiv.org/html/2509.13311v1) §4–5、Table 1/Fig.5 的工具调用评测 | 政策约束、工具参数、数据库副作用；可与 AgentRx 的诊断设定衔接 |

一手全文版本、下载字节数和 SHA-256 见 [research_sources.json](research_sources.json)。官方实现、固定 commit 和数据哈希分别在各 benchmark 的 `protocol.json` / `data_provenance.json`。

## 范围与版本选择

- **Who&When**：已有 12 独立任务、两条件、24 次真实诊断调用。本轮迁入独立 benchmark 目录，重新验收存档。它是直接诊断数据集，不将其“主流程度”与多年交互 benchmark 等同。AgentRx §2/§4 也使用、比较该数据集。
- **τ-bench**：[官方原版 README](https://github.com/sierra-research/tau-bench) 明确警告任务未更新，并建议迁移至修订版。此处为对齐既有 SaMuLe / AgentRx 等研究，固定历史原版进行兼容性 pilot。原版的奖励/任务缺陷可能影响科学有效性；本次通过表示运行与重放成立，不表示所有任务 gold 正确。新论文全量实验需另建修订版任务协议、重新运行，不能混用分数。
- **WebShop**：本轮使用官方支持的 1,000 商品预览设置，不是完整 1.18M 商品库。人类指令由官方代码生成 goal 列表，固定索引 0、1。官方 Drive 链接无法匿名获取，使用两个独立镜像并逐文件哈希交叉核对；未能直接核对官方原件的字节一致性。这项来源限制保留在验收结果中。
- **TRAIL / AgentErrorBench / AgentRx 注释集**：与诊断紧密相关，但不能仅因主题贴合就宣称已被众多论文用作 benchmark。本轮未新增执行这些注释集，也不把 τ-bench 运行称为 AgentRx 方法复现。
- **SWE-bench / WebArena / GAIA / AppWorld**：领域相关，但不是完成同一实验所必需的全部集合。优先建立上述三套可在本机原生执行、可确定性重放的互补环境；后续可按论文问题扩展，不将未执行者列为跑通。

## 事前冻结与验收

新增环境每套固定 **2 个任务、1 次尝试、gpt-6-astra / xhigh**。ALFWorld 从官方 valid_unseen 的 134 个游戏排序后按种子 20261009 抽 2 个；WebShop / τ-bench 使用事前固定的前两个索引，不按模型得分替换。预算分别 40 / 20 / 30 动作。没有执行反思重试、训练或跨任务记忆更新，因此本轮只验收运行链路。

验收条件：真实调用事件与动作一致；输入只包含允许的可见字段；全部预选任务保留；官方环境重放逐步一致；奖励重新计算一致；官方评分器正负对照成立；数据、源代码和运行代码 hash 对应。只有全部验收通过才允许 GitHub 推送。
