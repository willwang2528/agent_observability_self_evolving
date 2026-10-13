# Agent Observability & Self-Evolving Agents

研究链路：**执行轨迹与可观测数据处理 → 失败诊断 → 诊断驱动改进 → 在未见任务上验证收益**。

**2026-10-13：新增 [AgentRx 轨迹诊断 benchmark](machine_work/benchmarks/agentrx/README.md)，固定公开快照29条已全部真实运行并评分。** 根因步骤 9/29、类别 9/29、联合 7/29；原始调用、来源筛选、过程和独立复核保存在新目录。范围与论文最新版39条τ/170条全量有区别，见[报告](machine_work/benchmarks/agentrx/diagnosis_20261013/REPORT.md)。

**2026-10-11：WebShop 与 τ-bench 原有四个固定 pilot 任务已全部真实成功，并通过独立官方环境重放。** 本次修复任务完成；原失败记录保留。当前是小样本开发修复结果，尚未完成全量 benchmark 或证明自进化泛化收益。

[10-11 交互修复验收](machine_work/benchmarks/SUCCESS_ACCEPTANCE.json) · [10-11 修复状态](machine_work/benchmarks/TASK_STATUS.json) · [10-11 修复报告](machine_work/benchmarks/REPORT.md) · [交互 benchmark 选择依据](machine_work/benchmarks/SELECTION.md)

| Benchmark | 固定范围 | 当前实际结果 | 验收证据 |
|---|---|---|---|
| [AgentRx 轨迹诊断](machine_work/benchmarks/agentrx/README.md) | 固定官方GitHub快照τ全29条、1次/条 | 步骤 9/29；类别 9/29；联合 7/29 | 29次原始模型事件、官方评分、独立全分母复核 |
| [Who&When](machine_work/benchmarks/who_when/README.md) | 12 任务、2 条件、24 次既有诊断调用 | 联合命中：完整 4/12，首尾预算 3/12；本次未重跑 | 原始输入、事件与评分已复核；不是全部诊断正确 |
| [ALFWorld](machine_work/benchmarks/alfworld/README.md) | valid_unseen 固定 2 个游戏 | 官方成功 2/2；本次未重跑 | 既有官方逐步重放与评分器对照 |
| [WebShop](machine_work/benchmarks/webshop/README.md) | 1,000 商品预览环境中的原 goal 0、1 | **成功 2/2，奖励 1、1**；动作 15 + 7 | 新运行、原始模型动作、逐步重放和奖励拆分 |
| [τ-bench](machine_work/benchmarks/tau_bench/README.md) | 历史原版 retail，原 test 0、1 | **成功 2/2，奖励 1、1**；动作 9 + 10 | 用户确认、工具动作、DB 终态与官方重放 |

2026-10-11 交互修复使用 `gpt-6-astra / xhigh`，共 52 次真实调用：WebShop actor 22 次，τ-bench actor 19 次、user 11 次。WebShop 从旧 1/2、τ-bench 从旧 0/2 出发修改通用策略后重跑，属于观察过失败的开发任务；全部历史和新尝试保留，不将选出的成功运行报告成未调试的 pass@1。

## 两个工作目录

```text
human_audit/
├── README.md
├── REVIEW_TEMPLATE.md
└── benchmarks/
    ├── agentrx/                  # 新增轨迹诊断；待真人审计
    ├── who_when/                 # 待真人审计
    ├── alfworld/
    ├── webshop/
    └── tau_bench/
machine_work/
├── README.md
└── benchmarks/
    ├── REPORT.md                 # 10-11 交互修复报告
    ├── REPORT_20261009.md        # 原失败报告保留
    ├── SUCCESS_ACCEPTANCE.json   # 10-11 交互任务成功门禁
    ├── TASK_STATUS.json          # 10-11 修复完成状态
    ├── _shared/accept_success.py # 新门禁；旧 runner 保持不变
    ├── agentrx/diagnosis_20261013/ # 新增29条诊断证据
    ├── who_when/pilot_20261009/
    ├── alfworld/
    ├── webshop/recovery_20261011/ # 修复策略、全部新调用、成功验收
    └── tau_bench/recovery_20261011/
```

**真人审计仍待完成。** Codex 的验收和语义复核属于机器工作；旧 `case_audit.md` 中的“人工审查”表述不能作为真人已审记录。人工入口按 benchmark 分目录，使用[审计模板](human_audit/REVIEW_TEMPLATE.md)记录实际审计人、日期和证据。

## 准备与验收

```bash
python3 machine_work/benchmarks/_shared/prepare.py
.benchmark_cache/venv/bin/python machine_work/benchmarks/_shared/accept_success.py
```

需要 `uv`、Java 21；环境准备已在本机复用验证，尚未在另一台干净机器重建。验收不调用模型，要求固定任务 0、1 每个均 `reward=1、won=true、done=true`，同时检查真实模型输出、官方重放、来源版本、数据和用户模拟输入。验收开始或失败时撤销本轮发布许可，全部通过才允许同步 GitHub。真实运行入口见各 benchmark README，已有结果拒绝覆盖。

AgentRx离线复核（不调用模型）：

```bash
.benchmark_cache/venv/bin/python machine_work/benchmarks/agentrx/diagnosis_20261013/score.py --output /tmp/agentrx-offline-rescore
```

## 结果边界

- Who&When 的诊断命中率与交互环境的任务成功率分别报告。四个修复任务的成功不能替代诊断准确率或全量 benchmark 结果。
- WebShop 的通用购买策略增加约束逐项核验与候选比较，步数预算从 20 调至 40；原商品、goal、搜索索引和评分器未修改。预览环境仅 13 个可用人工 goal，数据来自两个哈希一致的镜像，未直接核对官方 Drive 原件。
- τ-bench 通过目录原词澄清顾客意图，真实用户模拟回复明确确认后才换货；未宣称设备兼容保证。使用历史原版任务和 Codex 用户模拟，重新生成的对话也可能影响结果。
- 2026-10-11 交互实验是针对已观察任务的诊断后修复，没有训练、持久记忆更新或未见任务评估，不能声称自进化效果或策略的因果提升。

原始失败、全部输入输出与官方评分都保留；缓存、虚拟环境和凭证不发布。历史工程可运行验收见 [2026-10-09 记录](machine_work/benchmarks/ACCEPTANCE.json)，2026-10-11交互修复发布以该严格成功门禁为准；2026-10-13 AgentRx诊断另有独立的验收和发布清单。
