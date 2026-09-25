"""Run with: python -m unittest discover -s tests."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from pipelines.dense import index as index_module
from pipelines.dense.evaluation import evaluate
from pipelines.dense.matching import load_matching_data, rank
from pipelines.dense.rag import context_for_match


def deterministic_embedding(texts, model_name=None):
    """Exercise index wiring without downloading model weights."""
    vectors = []
    for value in texts:
        vec = np.frombuffer(hashlib.sha256(value.encode("utf-8")).digest(), dtype=np.uint8).astype(np.float32)
        vectors.append(vec / np.linalg.norm(vec))
    return np.stack(vectors)


class DenseSmokeTest(unittest.TestCase):
    def test_index_matching_knowledge_and_metrics(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(index_module, "encode", deterministic_embedding):
            manifest = index_module.build(Path(directory), "test-embedding")
            index = index_module.DenseIndex(directory)
            self.assertGreater(manifest["counts"]["persona"], 0)
            self.assertGreater(manifest["counts"]["knowledge"], 0)
            users, events = load_matching_data()
            matches = rank("U001", index, users, events, top_k=5)
            self.assertLessEqual(len(matches), 5)
            self.assertTrue(matches)
            for item in matches:
                self.assertNotEqual(item["user_id"], "U001")
                self.assertTrue(users[item["user_id"]]["consent"]["matching"])
                self.assertFalse(any(e["type"] in ("unmatch", "pass") and
                                     {e["from_user"], e["about_user"]} == {"U001", item["user_id"]}
                                     for e in events))
            self.assertTrue(index.search("knowledge", "ความรัก", top_k=3))
            self.assertTrue(context_for_match("U001", index)["knowledge"])
            metrics = evaluate(index, top_ks=(5,), thresholds=(0.0,), penalty_weights=(0.0,))
            self.assertEqual(len(metrics), 1)
            self.assertGreater(metrics[0]["queries"], 0)


if __name__ == "__main__":
    unittest.main()
