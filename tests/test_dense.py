"""Run with: python -m unittest discover -s tests."""
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from pipelines.dense import index as index_module
from pipelines.dense.embedding import prepare_texts, resolve_model_name
from pipelines.dense.evaluation import evaluate
from pipelines.dense.matching import load_matching_data, rank
from pipelines.dense.rag import context_for_match


def deterministic_embedding(texts, model_name=None, role="document"):
    """Exercise index wiring without downloading model weights."""
    vectors = []
    for value in texts:
        vec = np.frombuffer(hashlib.sha256(value.encode("utf-8")).digest(), dtype=np.uint8).astype(np.float32)
        vectors.append(vec / np.linalg.norm(vec))
    return np.stack(vectors)


def run_case(directory):
    # Run in a child process so Windows can close Chroma's database files before cleanup.
    roles = []

    def recording_embedding(texts, model_name=None, role="document"):
        roles.append(role)
        return deterministic_embedding(texts, model_name, role)

    with patch.object(index_module, "encode", recording_embedding):
        manifest = index_module.build(Path(directory), "test-embedding")
        assert roles == ["document", "query", "document", "document"]
        index = index_module.DenseIndex(directory)
        assert manifest["counts"]["persona"] > 0
        assert manifest["counts"]["knowledge"] > 0
        assert set(index.collections) == {"persona", "preference", "avoid", "knowledge"}
        users, events = load_matching_data()
        matches = rank("U001", index, users, events, top_k=5)
        assert 0 < len(matches) <= 5
        for item in matches:
            assert item["user_id"] != "U001"
            assert users[item["user_id"]]["consent"]["matching"]
            assert not any(e["type"] in ("unmatch", "pass") and
                           {e["from_user"], e["about_user"]} == {"U001", item["user_id"]}
                           for e in events)
        assert index.search("knowledge", "ความรัก", top_k=3)
        assert roles[-1] == "query"
        tagged = next(row for row in index.rows["knowledge"] if row["concepts"])
        filtered = index.search("knowledge", "ความรัก", top_k=3,
                                category=tagged["category"], concept=tagged["concepts"][0])
        assert filtered and all(row["category"] == tagged["category"] and
                                tagged["concepts"][0] in row["concepts"] for row in filtered)
        assert context_for_match("U001", index)["knowledge"]
        metrics = evaluate(index, top_ks=(5,), thresholds=(0.0,), penalty_weights=(0.0,))
        assert len(metrics) == 1 and metrics[0]["queries"] > 0


class DenseSmokeTest(unittest.TestCase):
    def test_e5_uses_retrieval_prefixes(self):
        model = "intfloat/multilingual-e5-base"
        self.assertEqual(resolve_model_name("e5-base"), model)
        self.assertEqual(prepare_texts(["ข้อความ"], model, "query"), ["query: ข้อความ"])
        self.assertEqual(prepare_texts(["ข้อความ"], model, "document"), ["passage: ข้อความ"])
        self.assertEqual(prepare_texts(["ข้อความ"], "BAAI/bge-m3", "query"), ["ข้อความ"])

    def test_chroma_matching_knowledge_and_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            env = os.environ.copy()
            root = Path(__file__).resolve().parents[1]
            env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
            env["ANONYMIZED_TELEMETRY"] = "False"
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--case", directory],
                                    cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--case":
        run_case(sys.argv[2])
    else:
        unittest.main()
