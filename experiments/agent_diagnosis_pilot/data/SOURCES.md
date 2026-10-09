# 数据来源与复现依据

本 pilot 使用 Who&When 公开数据，下载时固定官方仓库提交 `f4d2b6da464a826580e59b3a0eae15ea2d642d7c`。未执行或安装上游代码。

- [官方仓库固定提交](https://github.com/ag2ai/Agents_Failure_Attribution/tree/f4d2b6da464a826580e59b3a0eae15ea2d642d7c)：本地 184 条 JSON 和 MIT LICENSE 的来源。
- [固定提交数据目录](https://github.com/ag2ai/Agents_Failure_Attribution/tree/f4d2b6da464a826580e59b3a0eae15ea2d642d7c/Who%26When)：Algorithm-Generated 与 Hand-Crafted 两个子集。
- [官方 README](https://github.com/ag2ai/Agents_Failure_Attribution/blob/f4d2b6da464a826580e59b3a0eae15ea2d642d7c/README.md)：任务定义、184 条规模、三种诊断基线及论文引用。
- [官方诊断实现](https://github.com/ag2ai/Agents_Failure_Attribution/blob/f4d2b6da464a826580e59b3a0eae15ea2d642d7c/Automated_FA/Lib/utils.py)：步骤采用从 0 开始的编号；官方 prompt 提供任务答案。本 pilot 省略该答案，不宣称严格复现论文分数。
- [官方评分实现](https://github.com/ag2ai/Agents_Failure_Attribution/blob/f4d2b6da464a826580e59b3a0eae15ea2d642d7c/Automated_FA/evaluate.py)：包含 substring 匹配；pilot 使用严格匹配和明确的代理名规范化。
- [论文 ICML 2025 页面](https://openreview.net/forum?id=GazlTYxZss) / [arXiv](https://arxiv.org/abs/2505.00212)：Which Agent Causes Task Failures and When? On Automated Failure Attribution of LLM Multi-Agent Systems。
- [官方 README 链接的数据镜像](https://huggingface.co/datasets/Kevin355/Who_and_When)：本轮未使用该镜像下载，避免版本混用。

归档 URL、提交号、归档 SHA-256、逐文件 SHA-256 见 `source_manifest.json`；原始官方 README/代码文本见 `source_evidence.json`。模型输入只包含问题、可选系统提示及独立清洗后的轨迹，不提供任务答案和诊断标签。
