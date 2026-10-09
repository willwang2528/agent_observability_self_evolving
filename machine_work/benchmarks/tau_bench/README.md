# τ-bench（历史原版 retail）：真实环境 pilot

官方 115 个 retail test 任务的固定索引 0、1。任务高度相似，仅偏好条件不同，不能据此评价跨领域泛化。官方原版已过时；本轮只验收历史设置的可执行性。

原始来源、commit、模型、任务与预算在 [protocol.json](protocol.json)；数据来源与 SHA-256 在 [data_provenance.json](data_provenance.json)。[选择依据](../SELECTION.md)核对了后续论文的实际使用。

## 复现与验收

从仓库根目录执行环境准备：

```bash
python3 machine_work/benchmarks/_shared/prepare.py
```

要求 `uv`、Java 21（本机使用 Azul ARM JDK 21）、Python 3.11；准备入口会创建忽略 Git 的 `.benchmark_cache/venv`，固定依赖快照见 [requirements.lock](../requirements.lock)。这是文本环境的实际运行快照，不安装原论文神经基线训练栈；flat snapshot 用 `--no-deps` 安装。本机环境见 [ENVIRONMENT.json](../ENVIRONMENT.json)。准备脚本已实际复用验证，尚未在另一台干净机器验证。

离线验收，不调用模型：

```bash
.benchmark_cache/venv/bin/python machine_work/benchmarks/tau_bench/../_shared/verify.py tau_bench
```

真实运行命令如下，使用本机既有 Codex 登录及冻结的 `gpt-6-astra / xhigh`；`run_20261009` 已存在时主动拒绝覆盖。要进行新实验，应复制到独立版本并冻结新协议，不删除已有证据。

```bash
.benchmark_cache/venv/bin/python machine_work/benchmarks/tau_bench/../_shared/run.py tau_bench
```

## 实际证据

- [验收结果](results/acceptance.json)：各任务真实调用计数、usage、官方奖励、逐步重放及评分器正负对照。
- [正式原始运行](results/run_20261009/)：每个 `case_*/trajectory.json` 和 `score.json`；`actor_calls/<step>/` 保留实际 prompt、命令、原始事件、预测与执行状态。
- 模型只能读到规则、工具 schema、可见历史、当前 observation 与 available actions；没有参考动作、隐藏 DB、expert plan 或根因标签输入。
- 验收从原始 `agent_message` 核对实际执行动作，再在官方环境从初始状态逐步重放，比较每步 observation、reward、done 和最终评分。
- 正负对照使用官方参考数据，只用于评分器校验，与模型运行分开；不能作为模型完成任务的成绩。
- [人工审计入口](../../../human_audit/benchmarks/tau_bench/README.md)：待真人审计，机器验收不代表已有人审。

**解释边界：** 这是两个任务、每任务一次的链路 pilot。低奖励保留在分母内；运行验收通过不表示所有任务成功，更不表示完成全量 benchmark、复现论文方法或证明自进化收益。订阅调用的美元成本未知；usage 包含 Codex 固定运行时开销。

## 用户模拟与评分

使用官方 `LLMUserSimulationEnv` 的系统提示及对话协议，模型传输替换为隔离的 Codex；user 与 actor 均为 `gpt-6-astra / xhigh`，不匹配原论文默认用户模型。私有 instruction 只送用户模拟器；actor 只收到用户实际说出的信息。`user_calls/` 同样保存真实事件与 usage。`get_total_cost()` 接口返回 0 仅为兼容官方接口，不能当作实际免费：tokens 单独累计，美元成本未知。

官方奖励比较环境数据库与参考动作导致的最终数据库哈希，部分任务还检查回答输出。它会在评分时修改内存状态，因此每次正式评分后不再继续执行该任务；验收在全新环境重放。原版任务标注与语义可能有缺陷，奖励命中不代表政策或语义全面正确。
