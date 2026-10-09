# Who&When：诊断 benchmark

[原 pilot 与复现入口](pilot_20261009/README.md) · [完整报告](pilot_20261009/REPORT.md) · [迁移后重新验收](acceptance.json) · [人工审计入口](../../../human_audit/benchmarks/who_when/README.md)

12 个独立任务、完整轨迹与 12,000 字符首尾基线、24 次既有真实调用；本轮重验原始事件、输入哈希、406 个冻结源文件及全部分数，没有重新调用模型。完整与预算条件联合命中分别 4/12、3/12。模型没有官方基线所提供的任务标准答案，因此是诊断改编实验，不是官方分数复现。

从仓库根目录离线验收：

```bash
python3 machine_work/benchmarks/_shared/verify_who_when.py
python3 -m unittest discover -s machine_work/benchmarks/who_when/pilot_20261009/tests -v
```

原始冻结文件仅迁移路径；pilot README 更新了可执行目录，其他历史记录保持字节一致。`case_audit.md` 由 Codex 生成，旧文中的“人工审查”不代表本项目真人已审。没有执行持久自进化。
