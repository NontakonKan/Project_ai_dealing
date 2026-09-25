"""Build and load a local exact cosine-search vector index."""
import json
from pathlib import Path

import numpy as np

from pipelines.common.io_utils import read_json, read_jsonl
from pipelines.common.paths import MOCK, PROCESSED, DATA
from .embedding import DEFAULT_MODEL, encode

DEFAULT_INDEX = DATA / "dense_index"


def documents():
    users = read_json(MOCK / "users.json")
    chunks = read_jsonl(PROCESSED / "book_chunks.jsonl")
    docs = {kind: [] for kind in ("persona", "preference", "avoid", "knowledge")}
    for user in users:
        if not user.get("consent", {}).get("matching"):
            continue
        uid = user["user_id"]
        demographic = user["demographic"]
        metadata = {"user_id": uid, "gender": demographic["gender"],
                    "seeking": demographic["seeking"], "age": demographic["age"],
                    "consent": True}
        for kind, field in (("persona", "persona_text"), ("preference", "preference_text"),
                            ("avoid", "avoid_text")):
            value = user.get("summaries", {}).get(field, "").strip()
            if value:
                docs[kind].append({"id": uid, "text": value, **metadata})
    for chunk in chunks:
        value = chunk.get("text", "").strip()
        if value:
            docs["knowledge"].append({"id": chunk["chunk_id"], "text": value,
                                      "category": chunk.get("category"),
                                      "concepts": chunk.get("concepts", []),
                                      "topics": chunk.get("topics", []),
                                      "source_id": chunk.get("source_id")})
    return docs


def build(directory=DEFAULT_INDEX, model_name=DEFAULT_MODEL):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    docs = documents()
    manifest = {"model": model_name, "counts": {kind: len(rows) for kind, rows in docs.items()}}
    for kind, rows in docs.items():
        if not rows:
            raise ValueError(f"No documents for {kind}")
        vectors = encode([row["text"] for row in rows], model_name)
        np.save(directory / f"{kind}.npy", vectors, allow_pickle=False)
        (directory / f"{kind}.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    (directory / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


class DenseIndex:
    def __init__(self, directory=DEFAULT_INDEX):
        directory = Path(directory)
        self.manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        self.rows = {}
        self.vectors = {}
        self.positions = {}
        for kind in self.manifest["counts"]:
            self.rows[kind] = json.loads((directory / f"{kind}.json").read_text(encoding="utf-8"))
            self.vectors[kind] = np.load(directory / f"{kind}.npy", allow_pickle=False)
            self.positions[kind] = {row["id"]: i for i, row in enumerate(self.rows[kind])}
            if len(self.rows[kind]) != len(self.vectors[kind]):
                raise ValueError(f"Index length mismatch: {kind}")

    def similarity(self, left_kind, left_id, right_kind, right_id):
        a = self.vectors[left_kind][self.positions[left_kind][left_id]]
        b = self.vectors[right_kind][self.positions[right_kind][right_id]]
        return float(a @ b)

    def search(self, kind, query, top_k=5, threshold=-1.0, category=None, concept=None):
        query_vec = encode([query], self.manifest["model"])[0]
        scores = self.vectors[kind] @ query_vec
        found = []
        for i, row in enumerate(self.rows[kind]):
            if category and row.get("category") != category:
                continue
            if concept and concept not in row.get("concepts", []):
                continue
            if scores[i] >= threshold:
                found.append({**row, "score": float(scores[i])})
        return sorted(found, key=lambda x: (-x["score"], x["id"]))[:top_k]
