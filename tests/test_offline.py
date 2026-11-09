import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tasks import make_split, score, extract_answer
from harness_loop import H0, paired_gate, apply_edit
from evolve_code import unsafe_reason
from common import validate_config


class OfflineTests(unittest.TestCase):
    def test_task_splits_are_disjoint_for_archived_sizes(self):
        for n in (6, 10):
            splits = [make_split(seed, n) for seed in (1, 2, 3)]
            questions = [{t["question"] for t in part} for part in splits]
            self.assertEqual([len(x) for x in questions], [5*n]*3)
            for i in range(3):
                for j in range(i):
                    self.assertFalse(questions[i] & questions[j])

    def test_score_rejects_wrong_and_missing_answers(self):
        task = {"answer": "123"}
        self.assertEqual(score(task, "说明\n答案：123"), 1)
        self.assertEqual(score(task, "答案: 124"), 0)
        self.assertEqual(score(task, "可能是123"), 0)
        self.assertEqual(extract_answer("答案: 1\n答案: 2"), "2")

    def test_gate_rejects_no_change_and_regression(self):
        base = {str(i): .5 for i in range(10)}
        self.assertFalse(paired_gate(base, base)["pass"])
        self.assertFalse(paired_gate(base, {k: 0 for k in base})["pass"])

    def test_gate_accepts_consistent_improvement(self):
        base = {str(i): 0 for i in range(10)}
        result = paired_gate(base, {k: 1 for k in base})
        self.assertEqual(result, {"delta": 1.0, "ci90_low": 1.0, "pass": True})

    def test_edits_do_not_mutate_parent(self):
        before = json.dumps(H0, ensure_ascii=False)
        child = apply_edit(H0, {"op":"add", "text":"先核对长度"}, "C1")
        self.assertEqual(child["parent"], "H0")
        self.assertEqual(json.dumps(H0, ensure_ascii=False), before)
        self.assertIsNone(apply_edit(child, {"op":"delete", "index":99}, "C2"))
        self.assertEqual(apply_edit(child, {"op":"delete", "index":0}, "C2")["playbook"], [])

    def test_ast_filter_rejects_code_not_comment(self):
        self.assertIsNone(unsafe_reason("def priority(i, r):\n    # open a new bin\n    return 0"))
        self.assertIsNotNone(unsafe_reason("import os"))
        self.assertIsNotNone(unsafe_reason("open('file')"))
        self.assertIsNotNone(unsafe_reason("x.__class__"))

    def test_missing_config_never_loads_personal_files(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                validate_config(require_solver=True)

    def test_embedded_credentials_are_rejected(self):
        env = {"RSI_API_KEY":"dummy", "RSI_BASE_URL":"https://user:pass@example.com/v1",
               "RSI_EDITOR_MODEL":"dummy"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(SystemExit):
                validate_config()

    def test_generated_execution_is_disabled_by_default(self):
        result = subprocess.run([sys.executable, str(ROOT/'evolve_code.py'), '--generations', '1'],
                                capture_output=True, text=True, encoding='utf-8', timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("generated Python execution is disabled", result.stderr)


if __name__ == '__main__':
    unittest.main()
