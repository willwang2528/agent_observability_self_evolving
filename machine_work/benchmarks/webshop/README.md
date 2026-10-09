# WebShop：真实环境 pilot

官方 1,000 商品预览环境与 Lucene 搜索；该商品子集只有 13 个可用人工 goal，固定索引 0、1；不是全量 12,087 指令或 1.18M 商品实验。

原始来源、commit、模型、任务与预算在 [protocol.json](protocol.json)；数据来源与 SHA-256 在 [data_provenance.json](data_provenance.json)。[选择依据](../SELECTION.md)核对了后续论文的实际使用。

## 复现与验收

从仓库根目录执行环境准备：

```bash
python3 machine_work/benchmarks/_shared/prepare.py
```

要求 `uv`、Java 21（本机使用 Azul ARM JDK 21）、Python 3.11；准备入口会创建忽略 Git 的 `.benchmark_cache/venv`，固定依赖快照见 [requirements.lock](../requirements.lock)。这是文本环境的实际运行快照，不安装原论文神经基线训练栈；flat snapshot 用 `--no-deps` 安装。本机环境见 [ENVIRONMENT.json](../ENVIRONMENT.json)。准备脚本已实际复用验证，尚未在另一台干净机器验证。

离线验收，不调用模型：

```bash
.benchmark_cache/venv/bin/python machine_work/benchmarks/webshop/verify.py
```

真实运行命令如下，使用本机既有 Codex 登录及冻结的 `gpt-6-astra / xhigh`；`run_20261009` 已存在时主动拒绝覆盖。要进行新实验，应复制到独立版本并冻结新协议，不删除已有证据。

```bash
.benchmark_cache/venv/bin/python machine_work/benchmarks/webshop/runner/run.py webshop
```

## 实际证据

- [验收结果](results/acceptance.json)：各任务真实调用计数、usage、官方奖励、逐步重放及评分器正负对照。
- [正式原始运行](results/run_20261009/)：每个 `case_*/trajectory.json` 和 `score.json`；`actor_calls/<step>/` 保留实际 prompt、命令、原始事件、预测与执行状态。
- 模型只能读到规则、工具 schema、可见历史、当前 observation 与 available actions；没有参考动作、隐藏 DB、expert plan 或根因标签输入。
- 验收从原始 `agent_message` 核对实际执行动作，再在官方环境从初始状态逐步重放，比较每步 observation、reward、done 和最终评分。
- 正负对照使用官方参考数据，只用于评分器校验，与模型运行分开；不能作为模型完成任务的成绩。
- [人工审计入口](../../../human_audit/benchmarks/webshop/README.md)：待真人审计，机器验收不代表已有人审。

**解释边界：** 这是两个任务、每任务一次的链路 pilot。低奖励保留在分母内；运行验收通过不表示所有任务成功，更不表示完成全量 benchmark、复现论文方法或证明自进化收益。订阅调用的美元成本未知；usage 包含 Codex 固定运行时开销。

## 运行修复与来源限制

[首次无效 setup 运行](results/setup_failed_action_encoding/FAILURE.md)保留原始模型调用：旧适配器丢弃 `search` 的 JSON 参数，不能计作有效性能实验。修复后的动作序列化 runner 独立冻结于 `runner/`，正式运行仍为相同两个任务、相同预算。当前验收入口 `verify.py` 使用共享新版 verifier；`runner/verify.py` 是冻结时的旧副本，其中正例 fixture 将列表误传为字典参数，已由当前入口纠正，不改变任何实际运行结果。

官方 Drive 下载不可匿名读取；两个独立镜像的三个文件哈希一致，但未能直接与官方原件核对。不能将镜像互相一致写成已验证官方字节一致。默认人工 goal 与商品库交集稀疏，本轮仅 13 个 goal。
