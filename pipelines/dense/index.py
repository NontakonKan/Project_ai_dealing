"""Build and query persistent ChromaDB indexes with multilingual embeddings."""
import json
from pathlib import Path

import chromadb
import numpy as np

from pipelines.common.io_utils import read_json, read_jsonl
from pipelines.common.paths import MOCK, PROCESSED, DATA
from .embedding import DEFAULT_MODEL, encode, resolve_model_name

DEFAULT_INDEX = DATA / "chroma_db"
COLLECTIONS = {"persona": "persona_vec", "preference": "preference_vec",
               "avoid": "avoid_vec", "knowledge": "knowledge_vec"}


def _concept_key(concept):
    """A unique scalar metadata key for Chroma's `where` filter."""
    return "concept_" + concept.encode("utf-8").hex()


def documents():
    users = read_json(MOCK / "users.json")
    chunks = read_jsonl(PROCESSED / "book_chunks.jsonl")
    docs = {kind: [] for kind in COLLECTIONS}
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


def _metadata(kind, row):
    if kind == "knowledge":
        result = {"concepts_json": json.dumps(row["concepts"], ensure_ascii=False),
                  "topics_json": json.dumps(row["topics"], ensure_ascii=False)}
        for name in ("category", "source_id"):
            if row.get(name) is not None:
                result[name] = row[name]
        result.update({_concept_key(concept): True for concept in row["concepts"]})
        return result
    return {"user_id": row["user_id"], "gender": row["gender"],
            "seeking_json": json.dumps(row["seeking"], ensure_ascii=False),
            "age": row["age"], "consent": row["consent"]}


def _row(kind, uid, text, metadata):
    if kind == "knowledge":
        return {"id": uid, "text": text, "category": metadata.get("category"),
                "concepts": json.loads(metadata["concepts_json"]),
                "topics": json.loads(metadata["topics_json"]),
                "source_id": metadata.get("source_id")}
    return {"id": uid, "text": text, "user_id": metadata["user_id"],
            "gender": metadata["gender"], "seeking": json.loads(metadata["seeking_json"]),
            "age": metadata["age"], "consent": metadata["consent"]}


def build(directory=DEFAULT_INDEX, model_name=DEFAULT_MODEL):
    model_name = resolve_model_name(model_name)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    docs = documents()
    manifest = {"model": model_name, "store": "chromadb", "space": "cosine",
                "query_collection": "preference_vec",
                "counts": {kind: len(rows) for kind, rows in docs.items()}}
    client = chromadb.PersistentClient(path=str(directory))
    existing = {collection.name for collection in client.list_collections()}
    for kind, rows in docs.items():
        if not rows:
            raise ValueError(f"No documents for {kind}")
        name = COLLECTIONS[kind]
        if name in existing:
            client.delete_collection(name)
        collection = client.create_collection(
            name=name, configuration={"hnsw": {"space": "cosine"}}, embedding_function=None)
        role = "query" if kind == "preference" else "document"
        vectors = encode([row["text"] for row in rows], model_name, role=role)
        collection.add(ids=[row["id"] for row in rows], embeddings=vectors.tolist(),
                       documents=[row["text"] for row in rows],
                       metadatas=[_metadata(kind, row) for row in rows])
    (directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


class DenseIndex:
    def __init__(self, directory=DEFAULT_INDEX):
        directory = Path(directory)
        self.manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if self.manifest.get("store") != "chromadb":
            raise ValueError("Build a ChromaDB index with `python -m pipelines.dense.run build`")
        self.client = chromadb.PersistentClient(path=str(directory))
        self.collections = {}
        self.rows = {}
        self.vectors = {}
        self.positions = {}
        for kind, name in COLLECTIONS.items():
            collection = self.client.get_collection(name=name, embedding_function=None)
            result = collection.get(include=["embeddings", "documents", "metadatas"])
            self.collections[kind] = collection
            self.rows[kind] = [_row(kind, uid, doc, meta) for uid, doc, meta in
                               zip(result["ids"], result["documents"], result["metadatas"])]
            self.vectors[kind] = np.asarray(result["embeddings"], dtype=np.float32)
            self.positions[kind] = {row["id"]: i for i, row in enumerate(self.rows[kind])}
            if len(self.rows[kind]) != self.manifest["counts"][kind] or len(self.rows[kind]) != len(self.vectors[kind]):
                raise ValueError(f"Collection count mismatch: {kind}; rebuild the index")

    def similarity(self, left_kind, left_id, right_kind, right_id):
        a = self.vectors[left_kind][self.positions[left_kind][left_id]]
        b = self.vectors[right_kind][self.positions[right_kind][right_id]]
        return float(a @ b)

    def candidate_ids(self, user_id, limit=None):
        """Retrieve candidate personas from Chroma before applying two-way scoring."""
        if user_id not in self.positions["preference"]:
            return []
        seeking = self.rows["preference"][self.positions["preference"][user_id]]["seeking"]
        if not seeking:
            return []
        gender_filter = {"gender": seeking[0]} if len(seeking) == 1 else {"gender": {"$in": seeking}}
        n = min(limit or len(self.rows["persona"]), len(self.rows["persona"]))
        query = self.vectors["preference"][self.positions["preference"][user_id]]
        result = self.collections["persona"].query(
            query_embeddings=[query.tolist()], n_results=n, where=gender_filter,
            include=["distances"])
        return result["ids"][0]

    def search(self, kind, query, top_k=5, threshold=-1.0, category=None, concept=None):
        if top_k < 1:
            return []
        filters = []
        if category:
            filters.append({"category": category})
        if concept:
            filters.append({_concept_key(concept): True})
        where = filters[0] if len(filters) == 1 else {"$and": filters} if filters else None
        vector = encode([query], self.manifest["model"], role="query")[0]
        result = self.collections[kind].query(
            query_embeddings=[vector.tolist()], n_results=min(top_k, len(self.rows[kind])),
            where=where, include=["distances"])
        found = []
        for uid, distance in zip(result["ids"][0], result["distances"][0]):
            score = 1.0 - float(distance)
            if score >= threshold:
                found.append({**self.rows[kind][self.positions[kind][uid]], "score": score})
        return sorted(found, key=lambda x: (-x["score"], x["id"]))
