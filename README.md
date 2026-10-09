# Agent Observability & Self-Evolving Agents

研究链路：**执行轨迹与可观测数据处理 → 失败诊断 → 诊断驱动改进 → 在未见任务上验证收益**。

当前完成四套 benchmark 的小样本链路验收：新增 ALFWorld、WebShop、历史原版 τ-bench，保留 Who&When 诊断 pilot。**这不是全量 benchmark 成绩，也尚未证明自进化有效。** [最终验收记录](machine_work/benchmarks/ACCEPTANCE.json) · [选择依据与一手论文](machine_work/benchmarks/SELECTION.md) · [运行报告](machine_work/benchmarks/REPORT.md)

| Benchmark | 本轮范围 | 实际结果 | 验收 |
|---|---|---|---|
| [Who&When](machine_work/benchmarks/who_when/README.md) | 12 独立任务、2 条件、24 次既有诊断调用 | 联合命中：完整 4/12，首尾预算 3/12 | 原始事件、406 个冻结文件和全部评分复核通过 |
| [ALFWorld](machine_work/benchmarks/alfworld/README.md) | valid_unseen 固定抽 2 个游戏 | 官方成功 2/2，17 个模型动作 | 官方环境逐步重放、评分器正负对照通过 |
| [WebShop](machine_work/benchmarks/webshop/README.md) | 1,000 商品预览中 13 个人工 goal 的固定索引 0、1 | 完全成功 1/2；奖励 2/3、1；13 个模型动作 | Lucene 搜索、官方重放和评分器对照通过 |
| [τ-bench](machine_work/benchmarks/tau_bench/README.md) | 历史原版 retail，固定 test 索引 0、1 | 成功 0/2；24 个模型动作、12 次用户模拟 | 真实对话、工具调用、DB 哈希与官方重放通过 |

统一使用 `gpt-6-astra / xhigh`；新增有效运行共 66 次真实模型调用。低奖励和失败保留，不用参考动作冒充模型成绩。WebShop 另有一次适配器错误的无效 setup 运行，已保留并单列用量。54 项测试通过，最终验收不调用模型。

## 两个工作目录

```text
human_audit/
├── README.md
├── REVIEW_TEMPLATE.md
└── benchmarks/
    ├── who_when/                 # 真人审计入口，尚未真人审计
    ├── alfworld/
    ├── webshop/
    └── tau_bench/
machine_work/
├── README.md
└── benchmarks/
    ├── SELECTION.md              # 选择标准、后续论文实际使用证据
    ├── REPORT.md                 # 实际结果、限制、可定位证据
    ├── ACCEPTANCE.json           # 全部验收门禁及日志
    ├── _shared/                  # 固定版本准备、运行和独立验收代码
    ├── who_when/pilot_20261009/   # 原冻结 pilot，迁移后原始证据不变
    ├── alfworld/                 # 协议、来源、真实输出、评分、重放验收
    ├── webshop/                  # 独立修复版 runner、失败 setup 与正式结果
    └── tau_bench/
```

**真人审计尚未完成。** Codex 生成的验收和解释均属于机器工作；旧 `case_audit.md` 中的“人工审查”表述不准确，不能作为真人已审记录。人工请在对应 benchmark 目录使用[模板](human_audit/REVIEW_TEMPLATE.md)另存审计人、日期、证据及异议，不覆盖 gold 或冻结结果。

## 本地准备与重新验收

从仓库根目录执行；需要 `uv`、Java 21。环境准备入口已在本机实际复用验证，尚未在其他干净机器验证。

```bash
python3 machine_work/benchmarks/_shared/prepare.py
.benchmark_cache/venv/bin/python machine_work/benchmarks/_shared/accept_all.py
```

准备会下载固定版本的公开源码与数据、安装隔离 Python 3.11 环境并建立真实商品索引。验收只读已有模型响应，逐步重放并重新评分，不请求模型。真实运行入口见各 benchmark README；现有结果拒绝覆盖，新实验另建版本。

## 研究与结果边界

- Who&When 有诊断 gold；ALFWorld / WebShop / τ-bench 是生成轨迹和执行改进的交互环境，本身不提供人工根因标签，任务成功率不能替代诊断准确率。
- WebShop 官方 Drive 无法匿名下载，本轮使用两个逐文件哈希一致的镜像；未直接核对官方原件。使用 1,000 商品与 13 个可用人工 goal，不能与全量设置混报。
- τ-bench 官方原版已警告任务过时；本轮对齐历史研究设置，完整论文实验需另建修订版协议。两个任务相似，不能推断泛化或总体性能。
- 本轮未执行持久记忆更新、训练或诊断后的干预；没有自进化效果结论。程序跑通、任务成功、诊断正确、解释可信和干预有效分别记录。

源版本、数据 SHA-256、实际 prompt、原始事件、模型响应与官方评分均保留；缓存、虚拟环境和凭证不发布。只有最终验收门禁通过后才同步 GitHub。
