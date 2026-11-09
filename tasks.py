"""可程序判定的任务集：每个任务有确定答案，评估器不需要 LLM。

这是 RSI 能落地的前提：本例答案由程序生成，减少主观判分；仍需审查任务与评分器。
任务刻意选“弱模型直接答容易错、讲究方法就能做对”的类型，
这样 harness（系统提示 / 经验）是否真的起作用一眼可见。
"""
from __future__ import annotations

import datetime as dt
import random
import string

WORDS = ["strawberry", "raspberry", "banana", "parallel", "bookkeeper", "mississippi",
         "committee", "occurrence", "programming", "referral", "barrel", "terror",
         "letter", "assessment", "successful", "possession", "embarrass", "tomorrow"]
WEEK = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
FORMAT = "\n\n请在最后一行严格按“答案: <结果>”输出。"


def _letter_count(r: random.Random):
    ws = r.sample(WORDS, 6)
    ch = r.choice("rseplt")
    s = "".join(ws)
    return f"字符串 “{s}” 中字母 {ch} 一共出现几次？", str(s.count(ch))


def _multiply(r: random.Random):
    a, b = r.randint(23456, 98765), r.randint(2345, 9876)
    return f"计算 {a} × {b}。", str(a * b)


def _weekday(r: random.Random):
    base = dt.date(2025, 1, 1) + dt.timedelta(days=r.randint(0, 700))
    n = r.randint(1000, 5000)
    q = (f"{base.isoformat()} 是{WEEK[base.weekday()]}。从这一天往后数 {n} 天是星期几？"
         "（用“星期X”回答）")
    return q, WEEK[(base + dt.timedelta(days=n)).weekday()]


def _reverse(r: random.Random):
    s = "".join(r.choice(string.ascii_lowercase) for _ in range(r.randint(16, 22)))
    return f"把字符串 {s} 完全倒序输出。", s[::-1]


def _kth(r: random.Random):
    xs = r.sample(range(100, 999), 28)
    k = r.randint(8, 20)
    return f"数列 {xs} 中第 {k} 小的数是多少？", str(sorted(xs)[k - 1])


GENERATORS = {
    "letter_count": _letter_count,
    "multiply": _multiply,
    "weekday": _weekday,
    "reverse": _reverse,
    "kth": _kth,
}


def make_split(seed: int, per_type: int) -> list[dict]:
    r = random.Random(seed)
    tasks = []
    for kind, gen in GENERATORS.items():
        for i in range(per_type):
            q, a = gen(r)
            tasks.append({"id": f"{kind}-{seed}-{i}", "kind": kind,
                          "question": q + FORMAT, "answer": a})
    return tasks


def extract_answer(text: str) -> str | None:
    """取最后一个“答案:”之后的内容，做轻度规范化。"""
    for line in reversed(text.strip().splitlines()):
        line = line.strip().replace("：", ":")
        if line.startswith("答案:") or line.startswith("**答案"):
            v = line.split(":", 1)[1] if ":" in line else ""
            return v.strip().strip("*`。. ").replace(",", "")
    return None


def score(task: dict, output: str) -> float:
    """程序判定：完全匹配得 1，否则 0。评估器不读 harness，也不被 harness 读到。"""
    got = extract_answer(output)
    return 1.0 if got is not None and got == task["answer"] else 0.0
