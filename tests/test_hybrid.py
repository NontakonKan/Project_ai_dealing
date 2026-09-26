"""Hybrid / Graph retrieval / feedback policy — รันได้โดยไม่ต้องเปิด Ollama หรือ Neo4j

python -m unittest discover -s tests
"""
import unittest

from graph import concepts, scorer
from graph.retrieve import GraphKnowledge
from graph.view import GraphView
from pipelines.feedback import policy, sensitive
from pipelines.hybrid.config import HybridConfig
from pipelines.hybrid.fusion import adjust, fuse, minmax
from pipelines.hybrid.router import route


class FusionTests(unittest.TestCase):
    def test_minmax_and_rrf_order(self):
        self.assertEqual(minmax({"a": 1, "b": 3}), {"a": 0.0, "b": 1.0})
        fused = fuse({"a": 0.9, "b": 0.1}, {"a": 0.8, "b": 0.2}, HybridConfig(fusion="rrf"))
        self.assertGreater(fused["a"], fused["b"])

    def test_hard_redflag_removes_candidate(self):
        info = {"a": {"redflags": [{"weight": 1.0}], "appearance": 0.0}, "b": {"redflags": [], "appearance": 0.0}}
        out = adjust({"a": 1.0, "b": 0.5}, info, HybridConfig(hard_redflag=True), 1.0)
        self.assertNotIn("a", out)
        soft = adjust({"a": 1.0, "b": 0.5}, info, HybridConfig(hard_redflag=False, lambda_rf=1.0), 1.0)
        self.assertLess(soft["a"], soft["b"])


class RouterTests(unittest.TestCase):
    def test_routes(self):
        self.assertEqual(route("ค่าเทอมเท่าไร", set()), "dense")
        self.assertEqual(route("anxious เข้ากับใคร", {"attach:anxious"}), "graph")
        self.assertEqual(route("gaslighting คืออะไร", {"rf:gaslighting"}), "hybrid")


class GraphRetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = GraphView.load()

    def test_alias_concepts_and_rules(self):
        self.assertIn("attach:anxious", concepts.by_alias("คนที่เป็น anxious กับ avoidant"))
        res = GraphKnowledge(self.g, use_embedding=False).retrieve("คนที่เป็น anxious กับ avoidant คบกันจะเป็นอย่างไร")
        self.assertTrue(any(it.kind == "graph_fact" and "CONFLICTS_WITH" in it.text for it in res.items))

    def test_offtopic_returns_nothing(self):
        self.assertEqual(GraphKnowledge(self.g, use_embedding=False).retrieve("ราคาทองวันนี้").items, [])

    def test_pair_features_bounded_and_facts_hide_appearance(self):
        users = [n for n in self.g.nodes if n.startswith("U")][:20]
        for a, b in zip(users, users[1:]):
            p = scorer.pair(self.g, a, b, facts=True)
            for v in p["features"].values():
                self.assertGreaterEqual(v, -1.0)
                self.assertLessEqual(v, 1.0)
            text = " ".join(f["text"] for f in p["facts"])
            self.assertFalse(sensitive.detect(text, mode="chat"), "graph_fact ต้องไม่เปิดเผยรูปลักษณ์")


class PolicyTests(unittest.TestCase):
    def test_appearance_never_reported_on_target(self):
        routed = policy.route_unmatch({"red_flags": [{"id": "rf:ghosting", "severity": 0.9}],
                                       "appearance": [{"id": "skin:dark", "severity": 0.6}],
                                       "hygiene": [{"id": "hygiene:self_care", "severity": 0.5}]})
        self.assertEqual([x["id"] for x in routed["report_target"]], ["rf:ghosting"])
        self.assertIn("skin:dark", [x["id"] for x in routed["speaker_avoids"]])


if __name__ == "__main__":
    unittest.main()
