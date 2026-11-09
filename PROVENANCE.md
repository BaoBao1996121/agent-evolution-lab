# 来源与公开处理

公开整理：2026-11-09。以下源文件均全文阅读后用于本批发布；不包含整库内容或全部原始轨迹。

原运行日期来自目录名与报告自述，不能视为外部时间认证。SHA-256 只能识别这次本地快照，不能独立证明实验真实执行或作者身份。

| 原始来源 | 公开位置 | 处理 |
|---|---|---|
| `experiments/rsi_lab/tasks.py` | [tasks.py](tasks.py) | 保留算法与评分行为；校订文档中的安全或统计用词 |
| `experiments/rsi_lab/binpack_eval.py` | [binpack_eval.py](binpack_eval.py) | 保留算法与评分行为；校订文档中的安全或统计用词 |
| `experiments/rsi_lab/evolve_code.py` | [evolve_code.py](evolve_code.py) | 保留算法与评分行为；校订文档中的安全或统计用词；不继承凭据环境变量，评估使用临时工作目录；生成代码执行默认关闭，须显式启用（仍不是安全沙箱） |
| `experiments/rsi_lab/harness_loop.py` | [harness_loop.py](harness_loop.py) | 保留算法与评分行为；校订文档中的安全或统计用词；在线运行前校验显式配置与正整数参数 |
| `experiments/rsi_lab/common.py` | [common.py](common.py) | 移除个人秘密文件与固定账号端点；必须显式配置模型与线路；API 包延迟导入；并发计数加锁；在线兼容性未重跑 |
| `experiments/rsi_lab/runs/evolve_20261105_234223/final.json` | [evidence/binpack/final.json](evidence/binpack/final.json) | 全文阅读后按原始字节保存；历史模型与结果字段不改写；不是本轮在线重跑 |
| `experiments/rsi_lab/runs/evolve_20261105_234223/history.json` | [evidence/binpack/history.json](evidence/binpack/history.json) | 全文阅读后按原始字节保存；历史模型与结果字段不改写；不是本轮在线重跑 |
| `experiments/rsi_lab/runs/harness_20261105_232532/final.json` | [evidence/harness-small/final.json](evidence/harness-small/final.json) | 全文阅读后按原始字节保存；历史模型与结果字段不改写；不是本轮在线重跑 |
| `experiments/rsi_lab/runs/harness_20261105_232532/rounds.json` | [evidence/harness-small/rounds.json](evidence/harness-small/rounds.json) | 全文阅读后按原始字节保存；历史模型与结果字段不改写；不是本轮在线重跑 |
| `experiments/rsi_lab/runs/harness_20261105_232532/archive.json` | [evidence/harness-small/archive.json](evidence/harness-small/archive.json) | 全文阅读后按原始字节保存；历史模型与结果字段不改写；不是本轮在线重跑 |
| `experiments/rsi_lab/runs/harness_20261105_235005/final.json` | [evidence/harness-large/final.json](evidence/harness-large/final.json) | 全文阅读后按原始字节保存；历史模型与结果字段不改写；不是本轮在线重跑 |
| `experiments/rsi_lab/runs/harness_20261105_235005/rounds.json` | [evidence/harness-large/rounds.json](evidence/harness-large/rounds.json) | 全文阅读后按原始字节保存；历史模型与结果字段不改写；不是本轮在线重跑 |
| `experiments/rsi_lab/runs/harness_20261105_235005/archive.json` | [evidence/harness-large/archive.json](evidence/harness-large/archive.json) | 全文阅读后按原始字节保存；历史模型与结果字段不改写；不是本轮在线重跑 |
| `reports/01-理论与架构/R168_Agent与过程RSI落地方案_2026-11-06.md` | [docs/findings.md](docs/findings.md) | 全文阅读，核对代码与选定结果；重新撰写，撤回安全沙箱、统计不退步、普遍收益和未附数据的结论 |
| `experiments/rsi_lab/README.md` | [README.md](README.md) | 全文阅读后重写；替换个人环境说明，区分离线验证与在线重跑 |

完整校验值见 [source-manifest.json](source-manifest.json)。

未发布：原始模型输出轨迹、完整候选程序库、个人端点配置及原始控制台日志。在线结论只核对选定归档和实现，不声称完成逐输出审计。

代码保留原有教学算法；公开适配主要改变凭据取得、运行默认值、子进程环境以及说明。原始文件保留在本地。
