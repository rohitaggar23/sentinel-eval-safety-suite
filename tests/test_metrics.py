import unittest
from sentinel_eval.metrics import token_f1, keyword_recall, groundedness

class TestMetrics(unittest.TestCase):
    def test_token_f1_partial(self):
        self.assertGreater(token_f1("red team review required", "red team review mandatory"), 0.5)

    def test_keyword_recall(self):
        self.assertEqual(keyword_recall("RAG uses citations", ["RAG", "citations"]), 1.0)

    def test_groundedness(self):
        self.assertGreater(groundedness("red team review mandatory", ["red team review mandatory before launch"]), 0.9)

if __name__ == "__main__":
    unittest.main()
