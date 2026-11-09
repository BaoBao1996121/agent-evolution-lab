"""Offline checks: archive consistency and deterministic bin-packing replay.

This does not replay historical LLM calls or recompute their bootstrap intervals.
Only the inspected, fixed winning function in evidence/binpack/final.json is run.
"""
from pathlib import Path
import json

from evolve_code import BEST_FIT, SEED_PROGRAM, evaluate

ROOT = Path(__file__).resolve().parent


def load(name):
    return json.loads((ROOT / "evidence" / name).read_text(encoding="utf-8"))


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def verify():
    small = load("harness-small/final.json")
    large = load("harness-large/final.json")
    small_a = load("harness-small/archive.json")
    large_a = load("harness-large/archive.json")
    small_r = load("harness-small/rounds.json")
    large_r = load("harness-large/rounds.json")
    require(small["final_id"] == "H0" and small["final_playbook"] == [], "small final changed")
    require(len(small_a) - 1 == 12 and not any(x.get("gate", {}).get("pass") for x in small_a), "small candidates mismatch")
    require(len(small_r) == 4 and all(x["decision"] == "KEEP_BASE" for x in small_r), "small decisions mismatch")
    adopted = [x for x in large_a if x["status"] == "adopted"]
    require(len(large_a) - 1 == 9 and len(adopted) == 1, "large candidate counts mismatch")
    require(adopted[0]["id"] == large["final_id"] == "R2C0", "large final mismatch")
    require(adopted[0]["playbook"] == large["final_playbook"], "large playbook mismatch")
    require(large_r[1]["decision"] == "ADOPT R2C0", "large decision mismatch")
    require(adopted[0]["held_gate"]["delta"] >= 0 and not adopted[0]["held_gate"]["pass"], "held-out limitation no longer matches archive")

    final = load("binpack/final.json")
    history = load("binpack/history.json")
    require(len(history) == final["args"]["generations"] == 20, "history length mismatch")
    require(history[-1]["best_id"] == final["best_id"] == "g13_1", "binpack winner mismatch")
    require(history[-1]["best"] == final["train_best"], "train score mismatch")
    results = {}
    programs = {"first_fit": SEED_PROGRAM, "best_fit": BEST_FIT, "evolved_best": final["best_src"]}
    for seed in (11, 22):
        results[str(seed)] = {}
        for label, src in programs.items():
            value, info = evaluate(src, seed)
            require(value is not None, f"replay failed: {label}/{seed}/{info}")
            value = round(value, 5)
            results[str(seed)][label] = value
            if seed == 22:
                require(value == final["test"][label], f"test score mismatch: {label}")
        if seed == 11:
            require(results[str(seed)]["evolved_best"] == final["train_best"], "winner train mismatch")
            require(results[str(seed)]["best_fit"] == history[0]["best"], "baseline train mismatch")
    return {"archive_consistency": "passed", "binpack_replay": results,
            "model_api_calls": 0, "historical_llm_outputs_replayed": False,
            "historical_bootstrap_recomputed": False}


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
