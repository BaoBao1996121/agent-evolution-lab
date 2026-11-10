# Agent 优化实验室：把“进化了”变成可以检查的问题

两个小实验，三组历史运行。最有价值的结果之一是：**最终版本根本没变，分数却涨了。**

本仓库整理自 2026-11 的个人实验笔记，保留生成、评估、拒绝、采纳和结果边界。代码与说明含 AI 辅助产出，不把教学实验称为生产系统或通用智能提升。

## 三分钟看懂

| 实验 | 改什么 | 检查什么 | 留下的结果 |
|---|---|---|---|
| A：经验手册优化 | 模型外的 playbook 条目 | 五类合成任务的确定答案 | 小样本没有采纳；大样本采纳一条 |
| B：装箱启发式搜索 | `priority(item, remaining)` | 用箱数除以容量下界的平均值 | 保存的胜出程序可离线复算 |

先读 [结果与限制](docs/findings.md)，再看 [代码地图](docs/code-map.md)。背景概念在 [学习笔记](https://github.com/BaoBao1996121/ai-agent-notes)，工作方法在 [工程手册](https://github.com/BaoBao1996121/agent-engineering-playbook)。

## 零密钥、零模型费用的本地检查

需要 Python 3.10+。在仓库根目录运行：

```bash
python verify_evidence.py
python -m unittest discover -s tests -v
```

第一条只读取已公开的 JSON，并对仓库内已审阅的装箱胜出函数做本地复算；不生成新代码、不调用模型、不读取个人秘密文件。它能核对装箱分数及归档记录之间的一致性，**不能重新证明历史在线模型输出**。

验证范围和本轮结果见 [VERIFICATION.md](VERIFICATION.md)。

## 想自己重跑模型实验

先读 [运行说明](docs/running.md) 和 [安全与局限](docs/safety-and-limits.md)。在线运行会产生费用，默认不提供模型和端点，也不会寻找你电脑里的密钥。

实验 B 会执行模型生成的 Python，默认关闭。AST 过滤、子进程和超时都不等于安全沙箱；重跑时需要自行准备无秘密、受资源限制的隔离环境。

## 如何阅读证据

- [小样本最终记录](evidence/harness-small/final.json)：最终仍为 H0。
- [大样本采纳过程](evidence/harness-large/rounds.json)：第二轮采纳 R2C0。
- [全部已归档候选](evidence/harness-large/archive.json)：也保留落选和删除提议。
- [装箱历史](evidence/binpack/history.json)：训练分数的改善与平台期。
- [装箱最终程序及族谱](evidence/binpack/final.json)：可读的函数与记录。

完整原始轨迹和整个候选程序库未发布。因此，在线分数的逐输出审计与独立重建 bootstrap 区间，不属于这个公开证据包已完成的验证。

## 来源

更多 RAG、Agent、记忆、评估与部署材料见 [AI 研究与实践归档](https://github.com/BaoBao1996121/ai-research-archive)；归档资料与本仓库可离线复算的实验结果分开标明验证范围。

原报告标注 2026-11-06，原运行目录标注 2026-11-05。公开仓库建立于 2026-11-09，不补造历史提交。见 [来源清单](PROVENANCE.md) 与 [内容与权利说明](CONTENT_POLICY.md)。
