import copy
import json
import unittest

from graph.build import ROOT, build_graph, load_inputs
from graph.model import content_hash, validate


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs, cls.provenance = load_inputs(ROOT / "data")
        cls.graph, cls.report = build_graph(**cls.inputs)

    def test_all_source_records_are_represented(self):
        self.assertEqual(self.report["nodes_by_label"]["User"], len(self.inputs["users"]))
        self.assertEqual(self.report["nodes_by_label"]["BookChunk"], len(self.inputs["chunks"]))
        event_edges = [e for e in self.graph["relationships"] if "event_id" in e["properties"]]
        self.assertEqual(len(event_edges), len(self.inputs["events"]))
        self.assertEqual(len({e["properties"]["event_id"] for e in event_edges}), len(event_edges))

    def test_output_is_order_independent(self):
        inputs = {**self.inputs, "users": list(reversed(self.inputs["users"])),
                  "events": list(reversed(self.inputs["events"])), "chunks": list(reversed(self.inputs["chunks"]))}
        result, _ = build_graph(**inputs)
        self.assertEqual(self.graph, result)

    def test_oracle_and_extra_fields_never_change_graph(self):
        inputs = copy.deepcopy(self.inputs)
        for user in inputs["users"]:
            user["_ground_truth_flags"] = ["SENTINEL_SECRET"]
            user["_archetype"] = "SENTINEL_SECRET"
            user["unexpected_field"] = "SENTINEL_SECRET"
        for event in inputs["events"]:
            event["gold_extracted"] = [{"id": "SENTINEL_SECRET"}]
            event["raw_reason"] = "SENTINEL_SECRET"
        result, _ = build_graph(**inputs)
        self.assertEqual(self.graph, result)
        self.assertNotIn("SENTINEL_SECRET", json.dumps(result))

    def test_only_usable_reports_and_consent_preserved(self):
        expected = {(u["user_id"], r["id"]) for u in self.inputs["users"]
                    for r in u["reported_traits"] if r["usable"] is True and r["report_count"] >= 3}
        actual = {(e["source"], e["target"]) for e in self.graph["relationships"] if e["type"] == "REPORTED_AS"}
        self.assertEqual(actual, expected)
        consent = {n["id"]: n["properties"]["matching_consent"] for n in self.graph["nodes"] if n["label"] == "User"}
        self.assertEqual(consent, {u["user_id"]: u["consent"]["matching"] for u in self.inputs["users"]})

    def test_unusable_report_ignored_even_with_high_count(self):
        inputs = copy.deepcopy(self.inputs)
        inputs["users"][0]["reported_traits"] = [{"id": "rf:stonewalling", "usable": False, "report_count": 99}]
        result, _ = build_graph(**inputs)
        self.assertFalse(any(e["source"] == "U001" and e["type"] == "REPORTED_AS" for e in result["relationships"]))

    def test_rule_status_and_chunk_provenance(self):
        rules = [e for e in self.graph["relationships"] if e["properties"].get("symmetric")]
        self.assertEqual(len(rules), len(self.inputs["taxonomy"]["compatibility_rules"]))
        self.assertTrue(all(e["properties"]["assertion"] == "unverified_taxonomy_rule" for e in rules))
        chunks = {n["id"]: n for n in self.graph["nodes"] if n["label"] == "BookChunk"}
        for original in self.inputs["chunks"]:
            props = chunks[original["chunk_id"]]["properties"]
            self.assertEqual(props["text"], original["text"])
            self.assertEqual(props["pages"], original["pages"])
        self.assertIn("rf:stonewalling", self.report["concepts_without_chunks"])

    def test_parallel_events_are_not_collapsed(self):
        inputs = copy.deepcopy(self.inputs)
        event = {**inputs["events"][0], "event_id": "E-second-observation"}
        inputs["events"].append(event)
        result, _ = build_graph(**inputs)
        self.assertEqual(len(result["relationships"]), len(self.graph["relationships"]) + 1)

    def test_duplicate_event_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate event"):
            build_graph(**{**self.inputs, "events": self.inputs["events"] * 2})

    def test_bad_reference_and_schema_rejected(self):
        for field, value, message in (("target", "absent", "Dangling"),
                                      ("type", "INJECTED_TYPE", "Unknown relation")):
            graph = copy.deepcopy(self.graph)
            graph["relationships"][0][field] = value
            with self.assertRaisesRegex(ValueError, message):
                validate(graph)
        graph = copy.deepcopy(self.graph)
        edge = next(e for e in graph["relationships"] if e["type"] == "LIKES")
        edge["target"] = "U001"
        with self.assertRaisesRegex(ValueError, "domain/range"):
            validate(graph)

    def test_hash_and_forbidden_property_validation(self):
        graph = copy.deepcopy(self.graph)
        graph["nodes"][0]["properties"]["label_th"] = "changed"
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            validate(graph)
        graph["nodes"][0]["properties"]["_ground_truth_flags"] = []
        graph["snapshot"] = content_hash(graph)
        with self.assertRaisesRegex(ValueError, "Forbidden"):
            validate(graph)

    def test_appearance_policy(self):
        appearance = {n["id"] for n in self.graph["nodes"] if n["label"] in ("BodyType", "SkinTone", "Hygiene")}
        self.assertTrue(appearance)
        reported = {e["target"] for e in self.graph["relationships"] if e["type"] == "REPORTED_AS"}
        self.assertFalse(reported & appearance, "รูปลักษณ์ต้องไม่ถูกรายงานโดยคนอื่น")
        users = {u["user_id"]: u for u in self.inputs["users"]}
        for e in (e for e in self.graph["relationships"] if e["type"] == "SELF_DESCRIBED"):
            declared = {x["id"] for x in users[e["source"]]["appearance"]["self_described"]}
            self.assertIn(e["target"], declared)
            if e["target"].startswith("skin:"):
                self.assertTrue(users[e["source"]]["appearance"]["consent_sensitive"])

    def test_skin_without_consent_is_dropped(self):
        inputs = copy.deepcopy(self.inputs)
        inputs["users"][0]["appearance"] = {"self_described": [{"id": "skin:tan", "source": "self"}], "consent_sensitive": False}
        result, _ = build_graph(**inputs)
        self.assertFalse(any(e["source"] == "U001" and e["type"] == "SELF_DESCRIBED" for e in result["relationships"]))


if __name__ == "__main__":
    unittest.main()
