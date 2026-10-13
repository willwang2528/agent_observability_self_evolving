# AgentRx 诊断 benchmark — 固定公开τ快照29条

**已完成29/29真实诊断调用与评分。** 步骤exact 9/29，根因类别 9/29，联合 7/29。独立验收见 [INDEPENDENT_AUDIT.md](INDEPENDENT_AUDIT.md)。

[结果报告](REPORT.md) · [实际过程](PROCESS.md) · [冻结协议](plan.json) · [候选与来源](SELECTION.md) · [逐例结果](evaluation/per_case.csv) · [机器验收](evaluation/acceptance.json) · [真人审计入口](../../../../human_audit/benchmarks/agentrx/README.md)

这是官方baseline在现有模型上的一次运行。范围为固定GitHub快照的全部29条，不等同最新论文tau39条或全量170条，也未执行AgentRx完整约束生成方法。

## 目录

```text
upstream/                 # 固定原始代码/数据/gold/许可
inputs/<id>/              # 完整IR步骤和实际user prompt
calls/<id>/attempt_1/     # 实际命令、起止时间、events、response、stderr
plan.json                 # 全29例与冻结源/输入/运行器哈希
protocol.py               # 原样加载官方IR、prompt和评分函数
runtime.py / run.py       # 隔离模型调用和流式原始事件保存
score.py                  # 全分母门禁、官方评分和算术/负面对照
evaluation/               # 官方结果、逐例分数、验收
independent_verify.py     # 独立subagent编写的离线复核
```

## 离线复核现有结果（不调用模型）

在仓库根目录：

```bash
.benchmark_cache/venv/bin/python -m unittest discover -s machine_work/benchmarks/agentrx/diagnosis_20261013 -p 'test_*.py' -v
.benchmark_cache/venv/bin/python machine_work/benchmarks/agentrx/diagnosis_20261013/score.py --output /tmp/agentrx-offline-rescore
.benchmark_cache/venv/bin/python machine_work/benchmarks/agentrx/diagnosis_20261013/independent_verify.py --run-dir "$PWD/machine_work/benchmarks/agentrx/diagnosis_20261013" --output-prefix /tmp/agentrx-independent-rescore
```

另一台机器只需Python3.11+、安装 `requirements.txt`。离线评分不需要Codex登录、Azure、启动tau交互环境或任何模型请求。上游源码和小规模原始数据均随本目录保存。此主机已实际验收；尚未验证全新机器环境重建。

## 新一轮真实调用

已完成目录拒绝覆盖plan；`run.py run`只跳过已经验证的调用，最多重试传输/格式失败，不依据gold提分。新实验应创建新的空目录，复制 `upstream/`、`run.py`、`score.py`、`protocol.py`、`runtime.py`、`test_protocol.py`、`test_events.py`，再执行：

```bash
python run.py prepare
python run.py run
python score.py
```

真实运行需要本机可用且已认证的Codex CLI。`runtime.py`固定其安装路径、模型和隔离参数，`prepare`记录实际版本；新环境改动应在新实验中重新冻结。不会读取或发布认证材料。

失败预测完整保留。测试集观察不能用于悄悄修改同一轮prompt；未来方法应另开版本、报告全部试验与数据划分。官方模板与输入不一致、版本及telemetry差异见 [RUN_NOTES.md](RUN_NOTES.md)。
