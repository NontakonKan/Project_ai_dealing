"""Graph retrieval (ส่วน 3) -> คืน RetrievalResult ตามสัญญากลาง (pipelines/retrieval/contract.py)

GraphKnowledge.retrieve(query):
  concept ในคำถาม (graph.concepts: alias + embedding)
    -> กฎ COMPATIBLE_WITH / CONFLICTS_WITH / OPPOSITE_OF ที่แตะ concept นั้น  => graph_fact
    -> BookChunk ที่ ABOUT concept นั้น (ถ่วงด้วยจำนวนครั้งที่พบ)           => chunk
ทำงานบน GraphView ในหน่วยความจำ (ผลเดียวกับ Cypher `knowledge` ใน queries.py)
"""
import time

from pipelines.retrieval.contract import RetrievalItem, RetrievalResult

from . import concepts as concept_detector
from .view import GraphView


class GraphKnowledge:
    mode = "graph"

    def __init__(self, view: GraphView = None, use_embedding=True):
        self.g = view or GraphView.load()
        self.use_embedding = use_embedding

    def retrieve(self, query, k=8):
        t0 = time.perf_counter()
        g, found = self.g, concept_detector.detect(query, self.use_embedding)
        items, seen = [], set()
        for (a, b), (rel, w, reason) in g.rules.items():
            key = tuple(sorted((a, b)))
            if key in seen or not ({a, b} & found):
                continue
            seen.add(key)
            items.append(RetrievalItem(f"rule:{key[0]}:{key[1]}", "graph_fact",
                                       f"({g.label(a)}) -[{rel}]-> ({g.label(b)})" + (f": {reason}" if reason else ""),
                                       round(w * len({a, b} & found), 3), "graph", {"path": [a, rel, b]}))
        chunk_score = {}
        for c in found:
            for chunk_id, count in g.about.get(c, []):
                chunk_score[chunk_id] = chunk_score.get(chunk_id, 0) + count / 10
        claim_paths = {}
        for concept in found:
            for claim_id in g.claims_about.get(concept, []):
                for cid in g.rel(claim_id, "SUPPORTED_BY"):
                    if claim_id not in claim_paths.setdefault(cid, set()):
                        chunk_score[cid] = chunk_score.get(cid, 0) + 0.1
                        claim_paths[cid].add(claim_id)
        for cid, s in chunk_score.items():
            # จำกัดคะแนน chunk ไม่เกิน 1 -> กฎที่ตรงกับ 2 concept (น้ำหนัก x2) ขึ้นก่อน chunk ที่แค่กล่าวถึงบ่อย
            items.append(RetrievalItem(cid, "chunk", g.chunk_text(cid), round(min(1.0, s), 3), "graph",
                                       {"path": (["Concept", "ABOUT (incoming)", "Claim", "SUPPORTED_BY", cid]
                                                 if cid in claim_paths else ["BookChunk", "ABOUT", *sorted(found)]),
                                        "concepts": sorted(found),
                                        "claim_ids": sorted(claim_paths.get(cid, []))}))
        items = sorted(items, key=lambda x: -x.score)[:k]
        return RetrievalResult("graph", query, items, (time.perf_counter() - t0) * 1000)
