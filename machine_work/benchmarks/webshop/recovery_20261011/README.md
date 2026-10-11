# WebShop 2026-10-11 开发修复：2/2 完全成功

同一固定配置的 **attempt_001** 已完成原任务 **0、1**，官方奖励均为 **1.0**，`won=true`、`done=true`。22 次真实 `gpt-6-astra / xhigh` 调用，逐步离线重放通过。[严格验收](acceptance.json) · [固定协议](protocol.json)

| 任务 | 旧运行奖励 | 本次奖励 | 本次步骤 / 模型调用 | 官方重放 |
|---|---:|---:|---:|---|
| 0 | 2/3 | 1 | 15 | PASS |
| 1 | 1 | 1 | 7 | PASS |

本次只有一个完整 attempt，没有跨尝试挑选成功案例。旧 `run_20261009` 的所有文件保持不变，逐文件 SHA-256 存在 [original_run_sha256.json](original_run_sha256.json)。[原始失败证据](../results/run_20261009/case_000/)继续保留。

## 失败原因与实际修复

旧任务 0 购买的商品满足官方商品类型、选项、价格条件，但 `r_att=0`，因此只得 2/3。旧 agent 浏览第一候选的 Features 后就购买，将宽泛的口腔清洁描述视为足够。这个奖励说明未命中官方属性规则，不能单凭它断言该商品在现实中无法维护口腔卫生。

本次仅修改通用 actor 规则：把商品类型、功能/材质/特征、变体和价格拆成需要核验的约束；优先搜索用户明确的功能短语；浏览 Features/Description；证据仅停留在品类层面时比较候选；提交购买前逐项核验。最大动作预算从 20 增至 40，实际使用 15、7 步。环境、商品、goal、任务索引、seed、原生动作和评分代码均未改变。

任务 0 新轨迹在 turn 5（第 6 步）查看第一商品 Description 后，回到搜索并改写查询，自主打开第二候选，其 Features 明确显示 `Regular and thorough oral hygiene`；之后选择 `blue` 并购买。注意：trajectory 的 `turn` 为零基索引，完整可见证据是 turn 9。新官方拆分 `r_type=r_att=r_option=1`、`r_price=true`。

任务 1 读取功能证据后明确选择 `pecan` 与 `4.25 ounce (pack of 12)`，官方所有得分项满足。[任务 0 奖励拆分](results/attempt_001/case_000/reward_breakdown.json) · [任务 1 奖励拆分](results/attempt_001/case_001/reward_breakdown.json)

## 复验

在仓库根目录、已准备的原环境中执行：

```bash
.benchmark_cache/venv/bin/python machine_work/benchmarks/webshop/recovery_20261011/verify.py
.benchmark_cache/venv/bin/python -m unittest discover -s machine_work/benchmarks/webshop/recovery_20261011 -p test_verify.py -v
```

验收不调用模型。它要求同一个完整 attempt 的原始任务 0、1 都达到奖励 1 且终止；从原始 `events.jsonl` 核对每个模型预测和实际动作，在官方环境逐步重放全部观察和奖励，并执行评分器正负对照。同时检查模型、reasoning、全部 command/config、instructions/schema、临时空目录、无工具调用、prompt 的观察白名单、源码 commit 和 staged/untracked 污染、三份数据文件的双镜像 SHA、旧运行文件不变。禁止 `python -O` / `PYTHONOPTIMIZE` 关闭断言。

要新增真实运行，使用从未存在的新 attempt 名称；不能覆盖历史结果：

```bash
.benchmark_cache/venv/bin/python -u machine_work/benchmarks/webshop/recovery_20261011/run.py --attempt attempt_002
```

默认验收最新 attempt；新增低分尝试仍会留在分母与 `all_attempts` 中，不能靠旧成功报告宣布新尝试通过。每次调用保存 prompt、schema、instructions、command、isolation、raw events、prediction、stderr 和 execution。评分拆分仅由事后离线 verifier 生成，不传给 actor。

## 成本与边界

输入 148,590 tokens，其中缓存输入 24,192；输出 2,607 tokens。输入含 Codex 固定运行时开销，缓存是输入的子集；订阅美元成本未知。

这是在已经观察过失败的原两个任务上的开发修复，**不是独立测试集表现，也不是完整 WebShop 分数或自主自进化效果**。提升同时改变了通用提示和动作预算，没有消融，不能分别归因。人工审计仍未进行；官方 Drive 原文件未能匿名核验，沿用两个镜像哈希一致的 1,000 商品预览数据，其来源限制见 [原数据来源](../data_provenance.json)。
