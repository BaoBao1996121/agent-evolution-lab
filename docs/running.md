# 运行说明

## 先离线，再决定是否付费运行

仓库根目录执行 `python verify_evidence.py` 和 `python -m unittest discover -s tests -v`。只需 Python 标准库。第一次检查的结果用于确认本地代码与已保存结果能对上，不是重现在线模型实验。

## 在线实验 A

使用单独的虚拟环境，再安装在线调用依赖：

```bash
python -m venv .venv
# 按操作系统激活该环境后：
python -m pip install openai
```

需要显式提供以下环境变量。密钥通过你自己的安全输入或秘密管理器注入，不要写进仓库、聊天记录或共享终端历史。

| 环境变量 | 含义 |
|---|---|
| `RSI_API_KEY` | 你获准使用的 API 密钥 |
| `RSI_BASE_URL` | 对应账号的 OpenAI 兼容 API 基址，不得含访问凭据 |
| `RSI_EDITOR_MODEL` | 提出候选编辑的模型 |
| `RSI_SOLVER_MODEL` | 执行实验 A 任务的模型 |
| `RSI_DISABLE_THINKING` | 仅当服务支持 `enable_thinking` 时设为 `1`；否则不要设置 |

没有默认模型、默认地区或备用线路。不同服务的参数支持并不相同，接口兼容性需要自行验证。本轮没有验证所有提供商。

先用小规模检查配置：

```bash
python harness_loop.py --rounds 1 --k 1 --repeats 1 --per-type 1
```

这一配置只用于检查能否完成调用与记录，不能支持效果结论。确认预算后再考虑历史配置：

```bash
python harness_loop.py --rounds 4 --k 3 --repeats 2 --per-type 6
python harness_loop.py --rounds 3 --k 3 --repeats 3 --per-type 10
```

历史大样本记录约 103 万输入加输出 token；这不是费用上限。失败重试、供应商计费和不同输出长度都会改变费用。程序没有硬性费用上限；请在供应商侧设置额度并观察运行。

## 在线实验 B

它会执行模型生成的代码。先准备 [安全说明](safety-and-limits.md) 要求的隔离环境，确认环境中没有个人或生产秘密，再执行：

```bash
python evolve_code.py --allow-local-code-execution --generations 20 --batch 4
```

显式参数仅表示允许执行，不会创建沙箱。子进程不继承 API 凭据环境变量，但主进程仍需要调用模型，所以整机隔离依然重要。

## 输出与可复现性

新运行写到 `runs/`，默认被 Git 忽略。它可能含题目、模型输出和候选代码，应检查后再分享。历史结果保存在 `evidence/`，不要覆盖。

即使沿用相同种子，远程模型版本、采样和服务端实现也可能变化；不承诺在线分数与归档逐项一致。历史配置用的模型名称只保留在结果文件中，不表示目前仍可调用。
