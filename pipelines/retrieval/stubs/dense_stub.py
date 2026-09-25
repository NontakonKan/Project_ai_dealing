"""Dense placeholder: ใช้ character trigram overlap แทน embedding (ส่วน 2 แทนด้วย bge-m3 + Vector DB)"""
import time

from ...common.io_utils import read_jsonl
from ...common.paths import PROCESSED
from ..contract import RetrievalItem, RetrievalResult


def _grams(text, n=3):
    t = "".join(text.lower().split())
    return {t[i:i + n] for i in range(len(t) - n + 1)}


class DenseStub:
    mode = "dense"

    def __init__(self):
        self.chunks = read_jsonl(PROCESSED / "book_chunks.jsonl")
        self.index = [(c, _grams(c["text"])) for c in self.chunks]

    def retrieve(self, query, k=8):
        t0 = time.perf_counter()
        q = _grams(query)
        scored = sorted(((len(q & g) / (len(q) or 1), c) for c, g in self.index), key=lambda x: -x[0])[:k]
        items = [RetrievalItem(id=c["chunk_id"], kind="chunk", text=c["text"], score=round(s, 4), source="dense",
                               meta={"section_title": c["section_title"], "concepts": c["concepts"]}) for s, c in scored]
        return RetrievalResult("dense", query, items, (time.perf_counter() - t0) * 1000)
