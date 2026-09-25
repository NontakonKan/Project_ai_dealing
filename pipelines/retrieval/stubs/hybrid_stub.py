"""Hybrid placeholder: Reciprocal Rank Fusion ของ Dense + Graph (ส่วน 4 แทนด้วย fusion/penalty ที่จูนแล้ว)"""
import time

from ..contract import RetrievalResult
from .dense_stub import DenseStub
from .graph_stub import GraphStub


class HybridStub:
    mode = "hybrid"

    def __init__(self, dense=None, graph=None, rrf_k=60):
        self.dense, self.graph, self.rrf_k = dense or DenseStub(), graph or GraphStub(), rrf_k

    def retrieve(self, query, k=8):
        t0 = time.perf_counter()
        fused, best = {}, {}
        for res in (self.dense.retrieve(query, k * 2), self.graph.retrieve(query, k * 2)):
            for rank, it in enumerate(res.items):
                fused[it.id] = fused.get(it.id, 0) + 1 / (self.rrf_k + rank + 1)
                best.setdefault(it.id, it)
        items = []
        for iid, s in sorted(fused.items(), key=lambda x: -x[1])[:k]:
            it = best[iid]
            it.score, it.source = round(s, 5), "hybrid"
            items.append(it)
        return RetrievalResult("hybrid", query, items, (time.perf_counter() - t0) * 1000)
