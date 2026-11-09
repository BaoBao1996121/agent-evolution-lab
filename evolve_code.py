"""实验 B：过程 RSI —— 迷你 AlphaEvolve / OpenEvolve。

问题：在线装箱（bin packing）启发式。物品按顺序到达，体积 (0,1]，箱容量 1。
被进化的是 priority(item, remaining) 函数：对每个能装下的箱子打分，选分最高的箱；
都装不下就开新箱。目标：平均用箱数越少越好（以下界 ceil(sum) 归一）。

与 FunSearch（DeepMind 2023）用的是同一类问题，使用确定性程序评分，但执行生成代码仍可能攻击评估环境。

闭环：
  程序库（档案库，保留所有有效程序 + 分数）
  -> 采样父代（锦标赛选择）+ 灵感程序
  -> LLM 生成新 priority 函数
  -> 级联评估：先语法/AST 过滤，再对子进程中的完整实例集打分
  -> 入库
最后在从未参与选择的 test 实例上复验。

用法：python evolve_code.py --allow-local-code-execution --generations 30
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import time
from pathlib import Path

from common import EDITOR_MODEL, USAGE, chat, write_json

OUT = Path(__file__).parent / "runs" / time.strftime("evolve_%Y%m%d_%H%M%S")

SEED_PROGRAM = '''def priority(item, remaining):
    # First Fit 的等价打分：所有能装下的箱子同分，取第一个
    return 0.0
'''

BEST_FIT = '''def priority(item, remaining):
    # Best Fit：装完后剩余越小越好
    return -(remaining - item)
'''


import ast
import subprocess
import sys
import os
import tempfile

EVAL_SCRIPT = str(Path(__file__).parent / "binpack_eval.py")
TRAIN_SEED, TEST_SEED = 11, 22  # 实例由 seed 在评估子进程内生成

BANNED_NAMES = {"open", "exec", "eval", "globals", "locals", "compile", "input",
                "getattr", "setattr", "vars", "dir", "type", "object"}


def unsafe_reason(src: str) -> str | None:
    """AST 级过滤：只看代码结构；这是有限过滤，不是安全隔离。"""
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return f"SyntaxError: {e.msg}"
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return "banned: import"
        if isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            return f"banned: {node.id}"
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            return "banned: dunder attr"
    return None


def evaluate(src: str, seed: int, timeout: float = 30.0) -> tuple[float | None, str]:
    """级联评估：① AST 语法与有限过滤② 独立子进程 + 受限 builtins + 超时执行打分。
    返回 (平均用箱数/下界, 信息)，越小越好。"""
    reason = unsafe_reason(src)
    if reason:
        return None, reason
    if "def priority" not in src:
        return None, "no priority()"
    try:
        # Do not inherit API credentials. This still is NOT an OS sandbox.
        child_env = {k: v for k, v in os.environ.items()
                     if k.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP"}}
        child_env["PYTHONIOENCODING"] = "utf-8"
        with tempfile.TemporaryDirectory(prefix="binpack-eval-") as temp_dir:
            p = subprocess.run([sys.executable, "-I", "-X", "utf8", EVAL_SCRIPT],
                               input=json.dumps({"src": src, "seed": seed}),
                               capture_output=True, text=True, encoding="utf-8",
                               timeout=timeout, env=child_env, cwd=temp_dir)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    try:
        res = json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        return None, "crash"
    return (res["score"], "ok") if res["ok"] else (None, res["err"])


PROMPT = """你在进化一个在线装箱（bin packing）启发式。物品依次到达，体积在 (0,1]，箱容量为 1。
对每个能装下当前物品的箱子，调用 priority(item, remaining) 打分（remaining 是该箱当前剩余容量，
一定 >= item），选分最高的箱放入；都装不下则开新箱。目标：用的箱子越少越好。

评分 = 平均(用箱数 / 理论下界)，越接近 1 越好。

下面是已有程序及其得分（越小越好）：

{examples}

请写一个**新的、更好的** priority 函数。可以组合、改进上面的思路，也可以尝试全新想法
（例如：考虑装完后剩余是否容易被小物品填满、对“几乎装满”给奖励、对剩余空间分段处理等）。
限制：只能用基本算术和 math 模块（已提供，不要 import），函数必须快。

只输出一个 Python 代码块，内含 def priority(item, remaining): ...
函数体不超过 25 行，注释最多 3 行，不要写文档字符串。"""


def extract_code(txt: str) -> str:
    m = re.search(r"```(?:python)?\s*\n(.*?)(?:```|$)", txt, re.S)  # 兼容未闭合的代码块
    src = (m.group(1) if m else txt).strip()
    # math 已在评估器里提供；去掉模型习惯性写的 import math，其他 import 仍会被拒
    src = re.sub(r"^\s*(import math|from math import \*)\s*$", "", src, flags=re.M)
    return src + "\n"


def tournament(db: list[dict], rng: random.Random, k: int = 3) -> dict:
    return min(rng.sample(db, min(k, len(db))), key=lambda x: x["score"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--generations", type=int, default=30)
    ap.add_argument("--batch", type=int, default=4, help="每代并行生成数")
    ap.add_argument("--allow-local-code-execution", action="store_true",
                    help="acknowledge generated code execution; use an isolated disposable environment")
    args = ap.parse_args()
    if min(args.generations, args.batch) <= 0:
        ap.error("generations/batch must be positive")
    if not args.allow_local_code_execution:
        ap.error("generated Python execution is disabled by default; read docs/safety-and-limits.md")
    from common import validate_config
    validate_config(require_solver=False)

    train = TRAIN_SEED   # 选择用
    test = TEST_SEED     # 只在最后复验
    rng = random.Random(7)

    db: list[dict] = []
    for name, src in [("first_fit", SEED_PROGRAM), ("best_fit", BEST_FIT)]:
        s, info = evaluate(src, train)
        db.append({"id": name, "parent": None, "gen": 0, "score": s, "src": src})
        print(f"[seed] {name}: {s:.4f}")
    stats = {"valid": 0, "invalid": 0, "errors": {}}
    history = []

    from concurrent.futures import ThreadPoolExecutor

    def gen_one(idx_gen):
        idx, g = idx_gen
        parent = tournament(db, rng)
        others = rng.sample([x for x in db if x is not parent], min(2, len(db) - 1))
        shown = sorted([parent] + others, key=lambda x: -x["score"])  # 差的在前、好的在后
        ex = "\n\n".join(f"# 得分 {x['score']:.4f}\n{x['src']}" for x in shown)
        txt = chat(EDITOR_MODEL, [{"role": "user", "content": PROMPT.format(examples=ex)}],
                   temperature=1.0, max_tokens=2000)
        return parent["id"], extract_code(txt), f"g{g}_{idx}"

    for g in range(1, args.generations + 1):
        with ThreadPoolExecutor(args.batch) as ex:
            outs = list(ex.map(gen_one, [(i, g) for i in range(args.batch)]))
        for pid, src, cid in outs:
            s, info = evaluate(src, train)
            if s is None:
                stats["invalid"] += 1
                key = info.split(":")[0]
                stats["errors"][key] = stats["errors"].get(key, 0) + 1
                print(f"  [invalid {cid}] {info[:80]}")
                continue
            stats["valid"] += 1
            db.append({"id": cid, "parent": pid, "gen": g, "score": s, "src": src})
        best = min(db, key=lambda x: x["score"])
        history.append({"gen": g, "best": round(best["score"], 5), "best_id": best["id"], "db": len(db)})
        print(f"[gen {g:02d}] best={best['score']:.5f} ({best['id']}) db={len(db)} "
              f"valid={stats['valid']} invalid={stats['invalid']}")

    best = min(db, key=lambda x: x["score"])
    test_scores = {}
    for name in ["first_fit", "best_fit"]:
        test_scores[name] = evaluate(next(x["src"] for x in db if x["id"] == name), test)[0]
    test_scores["evolved_best"] = evaluate(best["src"], test)[0]

    # 族谱：从最优程序回溯到种子
    lineage, cur = [], best
    while cur:
        lineage.append({"id": cur["id"], "gen": cur["gen"], "score": round(cur["score"], 5)})
        cur = next((x for x in db if x["id"] == cur["parent"]), None)

    final = {"train_best": round(best["score"], 5), "best_id": best["id"], "best_src": best["src"],
             "test": {k: round(v, 5) for k, v in test_scores.items()},
             "lineage": lineage, "stats": stats, "usage": dict(USAGE),
             "editor": EDITOR_MODEL, "args": vars(args)}
    write_json(OUT / "db.json", db)
    write_json(OUT / "history.json", history)
    write_json(OUT / "final.json", final)
    print(json.dumps(final, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
