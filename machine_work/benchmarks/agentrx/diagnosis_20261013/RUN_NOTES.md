# 冻结协议补充说明

不修改 `plan.json` 及其冻结文件，以下为审计后对措辞的澄清。

1. plan 中 split 的“entire public failed set”指固定 GitHub 快照公开29条，不指论文 v2 的39条 tau 或170条总量。
2. plan 中 gold “not read by prepare”措辞过强：prepare 为冻结源文件会读取 gold 字节计算SHA-256；它不解析 gold 内容、不用于选择样本或生成 prompt。gold 标签值只在离线评分使用。模型从空临时目录运行，无文件/网络工具；不会因 scorer 文件与代码同目录就获取 gold。
3. 官方 `Correct cases` 是根因类别命中，非联合命中。联合 step+category 是本地补充指标，单独报告。
4. 允许整数越界 step 和 category=0 的预测参与评分且记错；这类诊断语义错误不是传输失败，不能为提分重试。
5. 官方 `analysis` 输出的 token/time 默认0，因为其 Azure telemetry 未接入CLI；本地实际用量与时间来自原始 CLI events 和 metadata，见 evaluation/metrics.json。
6. 官方 loader 有未显式关闭文件引发的 ResourceWarning；源函数保持不变，测试及实际转换通过。
