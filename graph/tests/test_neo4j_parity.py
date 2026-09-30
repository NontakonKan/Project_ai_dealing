"""Neo4jGraphView ต้องให้ผลเท่ากับ GraphView (กราฟในหน่วยความจำ) ทุกจุดที่บอทใช้

ข้ามเองถ้าไม่มี Neo4j / ยังไม่ import / snapshot ไม่ตรงกับข้อมูลในเครื่อง (ต้องรัน graph.import_neo4j ก่อน)
python -m unittest graph.tests.test_neo4j_parity
"""
import random
import unittest

from graph import scorer
from graph.view import GraphView


def _views():
    try:
        from graph.neo4j_view import Neo4jGraphView
        remote = Neo4jGraphView.connect()
    except Exception as e:
        raise unittest.SkipTest(f"Neo4j ไม่พร้อม: {type(e).__name__}")
    local = GraphView.load()
    if remote.snapshot != local.snapshot:
        raise unittest.SkipTest("snapshot ใน Neo4j ไม่ตรงกับข้อมูลในเครื่อง -> python -m graph.import_neo4j")
    return local, remote


class ParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.local, cls.remote = _views()
        users = sorted(n for n, x in cls.local.nodes.items() if x["label"] == "User")
        rnd = random.Random(7)
        cls.pairs = [tuple(rnd.sample(users, 2)) for _ in range(40)]

    def test_match_scores_equal(self):
        for a, b in self.pairs:
            self.assertEqual(scorer.pair(self.local, a, b, facts=True), scorer.pair(self.remote, a, b, facts=True), (a, b))

    def test_match_scores_equal_with_prefetch(self):
        users = sorted({u for p in self.pairs for u in p})
        self.remote.prefetch(users)
        for a, b in self.pairs:
            self.assertEqual(scorer.pair(self.local, a, b), scorer.pair(self.remote, a, b), (a, b))

    def test_rules_and_about_equal(self):
        self.assertEqual(dict(self.local.rules.items()), dict(self.remote.rules.items()))
        concepts = sorted(self.local.about)[:25]
        for c in concepts:
            self.assertEqual(sorted(self.local.about[c]), sorted(self.remote.about.get(c, [])), c)

    def test_knowledge_retrieval_equal(self):
        from graph.retrieve import GraphKnowledge
        for q in ["คนขี้หึงควรทำอย่างไร", "anxious กับ avoidant เข้ากันไหม", "ghosting คืออะไร", "ความรักสามเหลี่ยม"]:
            a = [(it.id, round(it.score, 6)) for it in GraphKnowledge(self.local).retrieve(q, 8).items]
            b = [(it.id, round(it.score, 6)) for it in GraphKnowledge(self.remote).retrieve(q, 8).items]
            self.assertEqual(a, b, q)


if __name__ == "__main__":
    unittest.main()
