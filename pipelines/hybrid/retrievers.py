"""Adapter ให้ Dense / Graph / Hybrid คืน RetrievalResult (สัญญากลาง) -> Local LLM ใช้ได้ทันที

ใช้ 2 แบบ:
  1. คำถามความรู้ (rag_answer):  DenseKnowledge / GraphKnowledge / HybridKnowledge
  2. อธิบายคู่ (explain_match):  pair_context(ctx, a, b)
"""
import time

from ..retrieval.contract import RetrievalItem, RetrievalResult
from graph import scorer as graph_scorer
from graph.retrieve import GraphKnowledge as _GraphKnowledge


class DenseKnowledge:
    mode = "dense"

    def __init__(self, ctx, rerank_pool=0):
        self.ctx, self.rerank_pool = ctx, rerank_pool

    def retrieve(self, query, k=8):
        t0 = time.perf_counter()
        if self.rerank_pool:
            from ..dense.rerank import rerank
            rows = rerank(query, self.ctx.dense.search("knowledge", query, top_k=self.rerank_pool), k)
        else:
            rows = self.ctx.dense.search("knowledge", query, top_k=k)
        items = [RetrievalItem(r["id"], "chunk", r["text"], round(r["score"], 4), "dense",
                               {"concepts": r.get("concepts", []), "category": r.get("category")}) for r in rows]
        return RetrievalResult("dense", query, items, (time.perf_counter() - t0) * 1000)


class GraphKnowledge(_GraphKnowledge):
    """ตัวดึงของ Graph (graph/retrieve.py) ใช้ GraphView ชุดเดียวกับ context"""

    def __init__(self, ctx):
        super().__init__(ctx.graph)


class HybridKnowledge:
    """RRF ของ Dense + Graph (ถ่วงน้ำหนักได้) — ใช้เป็นฐานของ RoutedKnowledge ด้วย"""
    mode = "hybrid"

    def __init__(self, ctx, rrf_k=60, rerank_pool=0, w_dense=1.0, w_graph=1.0):
        self.dense, self.graph = DenseKnowledge(ctx, rerank_pool), GraphKnowledge(ctx)
        self.rrf_k, self.w = rrf_k, {"dense": w_dense, "graph": w_graph}

    def retrieve(self, query, k=8):
        t0 = time.perf_counter()
        fused, best = {}, {}
        for res in (self.dense.retrieve(query, k * 2), self.graph.retrieve(query, k * 2)):
            for rank, it in enumerate(res.items):
                fused[it.id] = fused.get(it.id, 0) + self.w[res.mode] / (self.rrf_k + rank + 1)
                best.setdefault(it.id, it)
        items = []
        for iid, s in sorted(fused.items(), key=lambda x: -x[1])[:k]:
            it = best[iid]
            items.append(RetrievalItem(it.id, it.kind, it.text, round(s, 5), "hybrid", it.meta))
        return RetrievalResult("hybrid", query, items, (time.perf_counter() - t0) * 1000)


class RoutedKnowledge:
    """router เลือกเส้นทาง: dense / graph (ถ่วง Graph x2 + กันที่ให้ graph_fact) / hybrid"""
    mode = "hybrid"
    RESERVED_FACTS = 2

    def __init__(self, ctx, rerank_pool=0):
        from graph import concepts
        self.detect = concepts.detect
        self.routes = {"dense": DenseKnowledge(ctx, rerank_pool),
                       "graph": HybridKnowledge(ctx, rerank_pool=rerank_pool, w_graph=2.0),
                       "hybrid": HybridKnowledge(ctx, rerank_pool=rerank_pool)}

    def retrieve(self, query, k=8):
        from .router import route
        path = route(query, self.detect(query))
        res = self.routes[path].retrieve(query, k)
        if path == "graph":   # คำถามเรื่องความสัมพันธ์: กันที่ให้กฎจากกราฟ (คำตอบตรง สั้น) ไว้ต้นรายการ
            facts = [it for it in self.routes["graph"].graph.retrieve(query, k).items if it.kind == "graph_fact"][:self.RESERVED_FACTS]
            ids = {f.id for f in facts}
            res.items = facts + [it for it in res.items if it.id not in ids][:k - len(facts)]
        for it in res.items:
            it.meta = {**it.meta, "route": path}
        return RetrievalResult("hybrid", query, res.items, res.latency_ms)


def pair_context(ctx, a, b, knowledge_k=3) -> RetrievalResult:
    """context สำหรับ explain_match: โปรไฟล์ B + graph_fact ของคู่ + chunk ความรู้ที่ตรงจุดเสี่ยง/จุดเด่นของคู่"""
    t0 = time.perf_counter()
    g = ctx.graph
    info = graph_scorer.pair(g, a, b, facts=True)
    items = [RetrievalItem(b, "candidate", ctx.users[b]["summaries"]["persona_text"], info["graph_score"], "hybrid")]
    items += [RetrievalItem(f["id"], "graph_fact", f["text"], 1.0, "graph", {"path": f["path"]}) for f in info["facts"]]
    concepts = {c for f in info["facts"] for c in f.get("concepts", [])}
    chunk_score = {}
    for c in concepts:
        for cid, count in g.about.get(c, []):
            chunk_score[cid] = chunk_score.get(cid, 0) + count
    for cid, s in sorted(chunk_score.items(), key=lambda x: -x[1])[:knowledge_k]:
        items.append(RetrievalItem(cid, "chunk", g.chunk_text(cid), s / 10, "graph"))
    if len(chunk_score) < knowledge_k:   # ไม่มี chunk ใน Graph -> ใช้ Dense หาเพิ่ม
        q = " ".join(f["text"] for f in info["facts"]) or ctx.users[b]["summaries"]["persona_text"]
        for r in ctx.dense.search("knowledge", q, top_k=knowledge_k - len(chunk_score)):
            items.append(RetrievalItem(r["id"], "chunk", r["text"], round(r["score"], 4), "dense"))
    return RetrievalResult("hybrid", f"{a}->{b}", items, (time.perf_counter() - t0) * 1000)
