"""Run only against a disposable/project database: GRAPH_NEO4J_TEST=1."""
import copy
import os
import unittest

from graph.build import ROOT, build_graph, load_inputs
from graph.neo4j_store import connect, database, import_graph, read_graph
from graph.queries import QUERIES


@unittest.skipUnless(os.environ.get("GRAPH_NEO4J_TEST") == "1", "Set GRAPH_NEO4J_TEST=1 for live integration")
class Neo4jTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs, _ = load_inputs(ROOT / "data")
        cls.graph, _ = build_graph(**cls.inputs)
        cls.driver = connect()
        cls.db = database()
        import_graph(cls.driver, cls.graph, cls.db)

    @classmethod
    def tearDownClass(cls):
        import_graph(cls.driver, cls.graph, cls.db)
        cls.driver.close()

    def test_import_is_idempotent_and_every_query_executes(self):
        first = import_graph(self.driver, self.graph, self.db)
        second = import_graph(self.driver, self.graph, self.db)
        self.assertEqual(first, second)
        params = {"user_id": "U001", "other_id": "U002", "concept_id": "attach:secure"}
        for name, query in QUERIES.items():
            with self.subTest(query=name):
                result = read_graph(self.driver, query, params, self.db)
                self.assertIsInstance(result, list)
                if name in {"profile", "rules", "reports", "chunks", "summary"}:
                    self.assertTrue(result)
        self.assertEqual(len(read_graph(self.driver, QUERIES["rules"], db=self.db)), 14)
        self.assertEqual(len(read_graph(self.driver, QUERIES["reports"], db=self.db)), 17)

    def test_new_snapshot_removes_stale_reports_and_updates_consent(self):
        inputs = copy.deepcopy(self.inputs)
        target = next(u for u in inputs["users"] if any(r["usable"] for r in u["reported_traits"]))
        target["reported_traits"] = []
        target["consent"]["matching"] = False
        changed, _ = build_graph(**inputs)
        try:
            import_graph(self.driver, changed, self.db)
            reports = read_graph(self.driver, QUERIES["reports"], db=self.db)
            self.assertFalse(any(r["user_id"] == target["user_id"] for r in reports))
            profile = read_graph(self.driver, QUERIES["profile"], {"user_id": target["user_id"]}, self.db)
            self.assertTrue(profile)
            self.assertTrue(all(row["matching_consent"] is False for row in profile))
            self.assertNotEqual(changed["snapshot"], self.graph["snapshot"])
        finally:
            import_graph(self.driver, self.graph, self.db)

    def test_missing_concept_has_no_invented_evidence(self):
        rows = read_graph(self.driver, QUERIES["chunks"], {"concept_id": "rf:stonewalling"}, self.db)
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
