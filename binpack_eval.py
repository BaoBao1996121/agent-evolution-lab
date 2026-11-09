"""装箱评估器：作为独立子进程运行（stdin 读 JSON，stdout 写 JSON）。

本脚本会 exec 代码；受限 builtins 不是安全沙箱。仅在隔离、无秘密的环境评估不可信代码。
父进程做 AST 过滤与超时，但不提供操作系统隔离、内存限制或网络隔离。
实例由 seed 在子进程内重建，避免跨进程传大数据。
"""
from __future__ import annotations

import json
import math
import random
import sys

SAFE_BUILTINS = {"abs": abs, "min": min, "max": max, "float": float, "int": int,
                 "round": round, "pow": pow, "range": range, "len": len, "sum": sum}


def make_instances(seed: int, n_inst: int = 20, n_items: int = 300):
    r = random.Random(seed)
    insts = []
    for _ in range(n_inst):
        items = []
        for _ in range(n_items):
            # 混合分布：偏大物品 + 均匀小物品，给“聪明”的启发式留空间
            if r.random() < 0.5:
                x = min(0.99, max(0.02, r.weibullvariate(0.45, 3.0)))
            else:
                x = r.uniform(0.02, 0.35)
            items.append(round(x, 4))
        insts.append(items)
    return insts


def pack(priority, items):
    bins = []  # 每个箱子的剩余容量
    for it in items:
        best, best_s = -1, -math.inf
        for i, rem in enumerate(bins):
            if rem + 1e-9 >= it:
                s = priority(it, rem)
                if s > best_s:
                    best, best_s = i, s
        if best < 0:
            bins.append(1.0 - it)
        else:
            bins[best] -= it
    return len(bins)


def score(src: str, seed: int) -> float:
    ns: dict = {}
    exec(src, {"__builtins__": SAFE_BUILTINS, "math": math}, ns)
    f = ns["priority"]
    insts = make_instances(seed)
    ratios = [pack(f, items) / math.ceil(sum(items)) for items in insts]
    return sum(ratios) / len(ratios)


if __name__ == "__main__":
    req = json.loads(sys.stdin.read())
    try:
        print(json.dumps({"ok": True, "score": score(req["src"], req["seed"])}))
    except Exception as e:
        print(json.dumps({"ok": False, "err": f"{type(e).__name__}: {e}"[:200]}))
