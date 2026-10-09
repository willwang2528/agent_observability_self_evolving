# 运行与验收报告：2026-10-09

新增三套主流交互 benchmark 已完成小样本真实运行，现有 Who&When 诊断 pilot 迁移后重新验收。**四套的工程链路均通过，模型任务结果有成功、部分得分和失败。** 这不构成全量 benchmark 成绩、论文方法复现或自进化收益证据。

[选择依据与一手论文](SELECTION.md) · [最终验收及逐项日志](ACCEPTANCE.json) · [环境与限制](ENVIRONMENT.json) · [结构化运行汇总](RUN_SUMMARY.json)

## 实际模型结果

| 环境 | 任务与模型动作数 | 官方任务结果 | 有效真实模型调用 | 输入 / 输出 tokens |
|---|---|---|---|---|
| [alfworld](alfworld/README.md) | 2 任务；动作 8 + 9 | 成功 2/2；奖励 1.0, 1.0 | actor 17；user 0 | 89,903 / 616 |
| [webshop](webshop/README.md) | 2 任务；动作 6 + 7 | 成功 1/2；奖励 0.6666666666666666, 1.0 | actor 13；user 0 | 76,847 / 772 |
| [tau_bench](tau_bench/README.md) | 2 任务；动作 12 + 12 | 成功 0/2；奖励 0.0, 0.0 | actor 24；user 12 | 326,840 / 13,820 |

统一模型 `gpt-6-astra / xhigh`。新增有效调用 66 次：54 次 actor、12 次 τ-bench 用户模拟。tokens 包含 Codex 固定运行时上下文开销，cached input 是 input 的子集，不额外相加。订阅美元成本未知。

Who&When 使用已有 12 独立任务 × 2 条件 × 1 次预测，共 24 次真实诊断调用；本轮没有重复调用。完整轨迹与首尾预算联合精确命中分别 **4/12、3/12**，弃权分别 3、6，均计零保留在准确率分母内。迁移后 406 个冻结文件（不含为迁移修改的 README）与旧清单哈希一致；24 个原始事件、有效输入和全部指标重新核对一致。

## 逐项验收

- **真实调用**：事件流出现有效 `turn.completed` 与非零 usage；原始 `agent_message` JSON 必须等于保存预测，预测再转换成实际环境动作。禁用模型外部工具、浏览器、记忆与仓库上下文。已知两条配置提示保留；未知提示或工具活动会使验收失败。
- **输入边界**：根据官方环境重建可见 observation、规则、工具 schema 与已观测历史，逐字核对实际 actor prompt。没有参考动作、根因 gold、隐藏 DB 或 expert plan。τ-bench 私有用户 instruction 只给模拟用户，用户输出与实际对话逐次对应。
- **官方重放**：全部 6 个新增预选任务都从初始状态重新执行原始模型动作，不重新请求模型。每步 observation、reward、done 及最终 score 一致；τ-bench 还逐步比较数据库哈希与完整官方奖励结果。
- **正负对照**：ALFWorld 用官方游戏内置 walkthrough 与 `look` 对照；WebShop 用官方目标商品/选项和不匹配商品验证原始 `get_reward`；τ-bench 用官方参考动作改变 DB 与不执行动作对照。每个任务正例为 1、负例为 0。参考动作从未计入模型成绩。
- **防伪造测试**：替换预测、删除完成事件、将 usage 归零或加入未知异常都会被拒绝；动作参数与白名单测试、原 pilot 的评分/隔离测试一并执行。最终共 **54 项测试通过**。

验收只验证可执行性、来源/输入边界及结果一致性。它不自动证明环境 gold、自然语言解释或根因因果关系正确。真人审计仍为 pending，入口在 `human_audit/benchmarks/<name>/`。

## 有研究价值的失败与边界

**WebShop 部分得分。** 第一个任务购买蓝色牙刷，官方重放拆分为 `r_type=1`、`r_option=1`、`r_price=True`、`r_att=0`，最终奖励 2/3；第二个任务全部维度满足，奖励 1。这里缺失的是评分器要求的属性命中，不能误写成选错颜色。详见 [case 0 官方拆分](webshop/results/run_20261009/case_000/reward_breakdown.json) 与[原始轨迹](webshop/results/run_20261009/case_000/trajectory.json)。是否存在自然语言属性和评分规则的语义偏差，仍需人工审计。

**τ-bench 两个零分任务。** 模型在工具返回仅明确 Google Assistant 兼容、用户坚持 Google Home 的情况下保留订单并转人工；两次最终 DB 都不同于参考换货后的 DB，官方奖励均为 0。可见行为支持把“术语与政策证据不足导致转人工”列为候选诊断，不足以认定模型或 gold 哪一方语义错误。两个任务相近且同一用户，不能据此推断总体性能。详见 [case 0](tau_bench/results/run_20261009/case_000/trajectory.json)、[case 1](tau_bench/results/run_20261009/case_001/trajectory.json) 与[官方奖励验收](tau_bench/results/acceptance.json)。

**环境与数据限制。** WebShop 使用官方支持的 1,000 商品预览，只有 13 个可用人工 goal，本轮固定 0、1；官方 Drive 失败后使用两个字节哈希一致的镜像，未能直接与官方原件核对。τ-bench 使用官方已警告过时的历史原版；为新 paper 做效果实验，需固定修订版并重跑，不能混用分数。ALFWorld 仅运行文本 PDDL 环境，未运行 THOR 视觉环境。

## 修复记录与额外成本

WebShop 首次 setup 的动作适配器丢弃了 JSON 参数，实际发出裸 `search`。这是实验实现错误，不能算作有效性能实验；[全部记录](webshop/results/setup_failed_action_encoding/FAILURE.md)保留。修复版本独立冻结，仍运行相同任务、同样预算，没有根据奖励重抽样。首次 setup 的 **8 次已完成模型调用**另计，共 input 35,058 / output 691 tokens；停止进程时未观察到缺少结果的调用目录，无法由日志获知的任何在途成本不填成 0。

ALFWorld 手写 expert 在双物体评分对照中未完成，改用官方游戏自带 walkthrough 验证正例；真实模型轨迹不变。WebShop 验收 fixture 还修正了人类 goal 的选项列表与原评分器要求的字典参数之间的类型映射；不改变真实输入、动作或 reward。当前验收入口为 `webshop/verify.py`，冻结 runner 内的旧 verifier 留作历史版本证据。

## 复验与下一轮使用

从仓库根目录运行：

```bash
python3 machine_work/benchmarks/_shared/prepare.py
.benchmark_cache/venv/bin/python machine_work/benchmarks/_shared/accept_all.py
```

准备入口已在当前机器复用执行，检查了 1,000 文档的真实索引。尚未在另一台干净机器重建；缓存与虚拟环境不会上传。全量任务、新模型、反思重试或持久记忆实验均应另建冻结版本。当前可在这些环境上收集执行轨迹、设计诊断与干预对照；本轮未执行训练、反思重试或跨任务记忆更新，不报告自进化收益。
