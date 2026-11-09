"""实验 A：Agent harness 自优化闭环（冻结模型，只进化 harness）。

harness = 系统提示 + playbook（条目化经验，ACE 式增量更新）。
每一轮：
  1. 当前 harness 在优化集上跑 R 次，得到每题成功率与失败轨迹
  2. 编辑器模型读失败样例，提 K 个候选；每个候选只做一次条目级编辑（add / update / delete）
  3. 候选在同一优化集上跑 R 次（Probe）
  4. 统计门槛：按题配对比较，bootstrap 置信下界 > 0 才算赢（否则 KEEP_BASE）
  5. 赢家再过 held-out 集：观测到的平均差值非负才采纳（非统计非劣检验）
  6. 所有候选（含落选）进档案库，带分数与父代
最后：H0 与最终 harness 在从未参与选择的 test 集上各跑一次对比。

用法：python harness_loop.py --rounds 4
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
from pathlib import Path

from common import EDITOR_MODEL, SOLVER_MODEL, USAGE, append_jsonl, chat, pmap, write_json
from tasks import make_split, score

OUT = Path(__file__).parent / "runs" / time.strftime("harness_%Y%m%d_%H%M%S")

H0 = {"id": "H0", "parent": None, "system": "你是一个助手。回答要简洁。", "playbook": []}


def render(h: dict) -> str:
    if not h["playbook"]:
        return h["system"]
    items = "\n".join(f"[{i}] {x}" for i, x in enumerate(h["playbook"]))
    return f"{h['system']}\n\n## 经验手册（按需使用）\n{items}"


def evaluate(h: dict, tasks: list[dict], repeats: int, tag: str) -> dict:
    """返回 {task_id: 平均分}，并把完整轨迹写进 JSONL（可回放）。"""
    sys_prompt = render(h)
    jobs = [(t, r) for t in tasks for r in range(repeats)]

    def run(job):
        t, r = job
        out = chat(SOLVER_MODEL, [{"role": "system", "content": sys_prompt},
                                  {"role": "user", "content": t["question"]}],
                   temperature=0.7, max_tokens=1500)
        return {"harness": h["id"], "tag": tag, "task": t["id"], "kind": t["kind"],
                "rep": r, "score": score(t, out), "answer": t["answer"], "output": out}

    rows = pmap(run, jobs, workers=12)
    append_jsonl(OUT / "trajectories.jsonl", rows)
    per_task: dict[str, list[float]] = {}
    for row in rows:
        per_task.setdefault(row["task"], []).append(row["score"])
    return {"per_task": {k: sum(v) / len(v) for k, v in per_task.items()}, "rows": rows}


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def paired_gate(base: dict, cand: dict, n_boot: int = 2000, seed: int = 0) -> dict:
    """按题配对：delta_i = cand_i - base_i；bootstrap 分布第 5 百分位 > 0 才通过（中心 90% 区间的下界）。"""
    ids = sorted(base)
    deltas = [cand[i] - base[i] for i in ids]
    r = random.Random(seed)
    boots = sorted(mean([r.choice(deltas) for _ in deltas]) for _ in range(n_boot))
    lo = boots[int(0.05 * n_boot)]
    return {"delta": round(mean(deltas), 4), "ci90_low": round(lo, 4), "pass": lo > 0}


EDIT_PROMPT = """你在优化一个 AI 助手的“经验手册”。助手模型固定不变，你只能改手册。

当前系统提示：
{system}

当前手册条目：
{playbook}

下面是助手在一批题目上答错的样例（题目、正确答案、助手输出节选）：
{failures}

请提出 {k} 个**互不相同**的候选编辑。每个候选只能做一件事：
- add：新增一条经验
- update：改写某条已有经验（给出 index）
- delete：删除某条无用/有害经验（给出 index）

要求：经验必须是**可执行的通用方法**（例如“先逐个字符列出再计数”），
不能写具体题目的答案，不能针对某一道题。每条不超过 80 字。

只输出 JSON 数组，例如：
[{{"op":"add","text":"...","why":"针对哪类失败、预期机制"}},
 {{"op":"update","index":0,"text":"...","why":"..."}}]"""


def propose(h: dict, fail_rows: list[dict], k: int, rng: random.Random) -> list[dict]:
    sample = rng.sample(fail_rows, min(10, len(fail_rows)))
    failures = "\n---\n".join(
        f"题目: {x['question'][:160]}\n正确答案: {x['answer']}\n助手输出: {x['output'][-300:]}"
        for x in sample)
    pb = "\n".join(f"[{i}] {t}" for i, t in enumerate(h["playbook"])) or "（空）"
    txt = chat(EDITOR_MODEL, [{"role": "user", "content": EDIT_PROMPT.format(
        system=h["system"], playbook=pb, failures=failures, k=k)}],
        temperature=0.9, max_tokens=1500)
    m = re.search(r"\[.*\]", txt, re.S)
    try:
        edits = json.loads(m.group(0)) if m else []
    except json.JSONDecodeError:
        edits = []
    return [e for e in edits if isinstance(e, dict) and e.get("op") in {"add", "update", "delete"}][:k]


def apply_edit(h: dict, e: dict, new_id: str) -> dict | None:
    pb = list(h["playbook"])
    idx = e.get("index")
    if e["op"] == "add" and e.get("text"):
        pb.append(e["text"].strip())
    elif e["op"] == "update" and isinstance(idx, int) and 0 <= idx < len(pb) and e.get("text"):
        pb[idx] = e["text"].strip()
    elif e["op"] == "delete" and isinstance(idx, int) and 0 <= idx < len(pb):
        pb.pop(idx)
    else:
        return None
    return {"id": new_id, "parent": h["id"], "system": h["system"], "playbook": pb, "edit": e}


def by_kind(rows: list[dict]) -> dict:
    agg: dict[str, list[float]] = {}
    for r in rows:
        agg.setdefault(r["kind"], []).append(r["score"])
    return {k: round(mean(v), 3) for k, v in sorted(agg.items())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--k", type=int, default=3, help="每轮候选数")
    ap.add_argument("--repeats", type=int, default=2, help="每题重复次数")
    ap.add_argument("--per-type", type=int, default=6)
    args = ap.parse_args()
    if min(args.rounds, args.k, args.repeats, args.per_type) <= 0:
        ap.error("rounds/k/repeats/per-type must be positive")
    from common import validate_config
    validate_config(require_solver=True)

    # 三个不同种子生成的任务集（应检查内容重复）：优化集（给编辑器看失败）、held-out（只做门槛）、test（只在最后用一次）
    opt = make_split(seed=1, per_type=args.per_type)
    held = make_split(seed=2, per_type=args.per_type)
    test = make_split(seed=3, per_type=args.per_type)
    rng = random.Random(42)

    archive, log = [], []
    cur = H0
    cur_eval = evaluate(cur, opt, args.repeats, "opt")
    cur_held = evaluate(cur, held, args.repeats, "held")
    archive.append({**cur, "opt": mean(list(cur_eval["per_task"].values())),
                    "held": mean(list(cur_held["per_task"].values())), "status": "base"})
    print(f"[H0] opt={archive[0]['opt']:.3f} held={archive[0]['held']:.3f} by_kind={by_kind(cur_eval['rows'])}")

    for rnd in range(1, args.rounds + 1):
        fails = [r | {"question": next(t["question"] for t in opt if t["id"] == r["task"])}
                 for r in cur_eval["rows"] if r["score"] == 0]
        if not fails:
            print(f"[R{rnd}] 优化集已全对，停止"); break
        edits = propose(cur, fails, args.k, rng)
        results = []
        for j, e in enumerate(edits):
            cand = apply_edit(cur, e, f"R{rnd}C{j}")
            if cand is None:
                continue
            ev = evaluate(cand, opt, args.repeats, "opt")
            gate = paired_gate(cur_eval["per_task"], ev["per_task"], seed=rnd * 10 + j)
            results.append((cand, ev, gate))
            archive.append({**cand, "opt": mean(list(ev["per_task"].values())),
                            "gate": gate, "status": "candidate"})
            print(f"  [{cand['id']}] {e['op']}: {e.get('text', '')[:50]!r} -> delta={gate['delta']:+.3f} "
                  f"ci_low={gate['ci90_low']:+.3f} pass={gate['pass']}")

        winners = sorted([x for x in results if x[2]["pass"]], key=lambda x: -x[2]["delta"])
        decision = "KEEP_BASE"
        if winners:
            cand, ev, gate = winners[0]
            hv = evaluate(cand, held, args.repeats, "held")
            held_gate = paired_gate(cur_held["per_task"], hv["per_task"], seed=rnd)
            # held-out 仅要求观测平均差值非负；不代表统计意义的不退步
            if held_gate["delta"] >= 0:
                decision = f"ADOPT {cand['id']}"
                cur, cur_eval, cur_held = cand, ev, hv
                for a in archive:
                    if a["id"] == cand["id"]:
                        a["status"], a["held"], a["held_gate"] = "adopted", mean(list(hv["per_task"].values())), held_gate
            else:
                decision = f"REJECT {cand['id']} (held-out delta={held_gate['delta']:+.3f})"
        log.append({"round": rnd, "decision": decision, "playbook": cur["playbook"]})
        print(f"[R{rnd}] {decision}; 当前 playbook 条数={len(cur['playbook'])}")

    # 最终验收：test 集只在这里用一次
    t0 = evaluate(H0, test, args.repeats, "test")
    t1 = evaluate(cur, test, args.repeats, "test")
    final = {
        "H0_test": round(mean(list(t0["per_task"].values())), 3),
        "final_test": round(mean(list(t1["per_task"].values())), 3),
        "final_id": cur["id"],
        "test_gate": paired_gate(t0["per_task"], t1["per_task"], seed=999),
        "H0_by_kind": by_kind(t0["rows"]),
        "final_by_kind": by_kind(t1["rows"]),
        "final_playbook": cur["playbook"],
        "usage": dict(USAGE),
        "solver": SOLVER_MODEL, "editor": EDITOR_MODEL, "args": vars(args),
    }
    write_json(OUT / "archive.json", archive)
    write_json(OUT / "rounds.json", log)
    write_json(OUT / "final.json", final)
    print(json.dumps(final, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
