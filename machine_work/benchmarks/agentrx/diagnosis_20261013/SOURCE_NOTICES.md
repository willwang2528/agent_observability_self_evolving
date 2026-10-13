# 来源、许可与适配

- 作品：AgentRx: Diagnosing AI Agent Failures from Execution Trajectories。作者 Shraddha Barke、Arnav Goyal、Alind Khare、Avaljot Singh、Suman Nath、Chetan Bansal。
- [官方代码](https://github.com/microsoft/AgentRx)，commit `7a18c79708e7671be15124460f4f7296107c2a55`。本目录 `upstream/` 中源码与数据逐字复制，无修改。代码 MIT，完整声明见 `upstream/LICENSE.txt`。
- [官方数据卡片](https://huggingface.co/datasets/microsoft/AgentRx) 标注 CC-BY-4.0：[许可证](https://creativecommons.org/licenses/by/4.0/)。数据取自同作者官方 GitHub 公开文件，无需接受 HF gated 访问条款。
- 论文：[v1](https://arxiv.org/abs/2602.02475v1)、[v2](https://arxiv.org/abs/2602.02475v2)。当前 v2 宣称 170 总轨迹、39 条 tau；本快照只有 29 条配对的 tau。只运行快照内 29 条。
- 本地适配：AST 抽取官方 IR / baseline prompt / Report.compute_stats / analysis 的原始函数，避开 Azure 初始化；模型传输替换为隔离 Codex CLI，结构化 JSON 输出；`gpt-6-astra / xhigh` 单次运行。不是论文 gpt-5 三次实验的数值复现。
- `inputs/` 是官方 IR 转换结果，完整保留 1064 个步骤；模型只看到 steps，未额外添加 task.instruction、参考动作、参考输出或诊断标签。最终响应和调用日志是本地新结果。
- 官方模板声称提供参考 actions，但官方实际 baseline 未传入；本轮保留该不一致，不在测试集上改 prompt。

许可来源差异：最新论文v2 Appendix I 将其 benchmark 写作 MIT，而官方 HF 卡片标注 CC-BY-4.0。本副本同时保留官方 GitHub MIT 文件、作者归属、数据来源和适配说明，不将两处声明混为同一文本。
