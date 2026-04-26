import os, tempfile, unittest, json
from sentinel_eval.adapters import RuleBasedMockAdapter
from sentinel_eval.runner import EvalRunner

class TestRunner(unittest.TestCase):
    def test_run_suite(self):
        path = os.path.join(os.path.dirname(__file__), "..", "data", "eval_cases.jsonl")
        report = EvalRunner(RuleBasedMockAdapter()).run(path)
        self.assertEqual(report.total_cases, 4)
        self.assertGreaterEqual(report.pass_rate, 0.75)
        self.assertEqual(report.safety_summary["secret_leak_cases"], 0)

if __name__ == "__main__":
    unittest.main()
