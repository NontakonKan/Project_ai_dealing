"""ประเมินการดึงความรู้ (ไม่ใช้ LLM): Dense / +rerank / Graph / Hybrid / Routed บนคำถามชุดเดียวกัน

relevant = chunk ที่มีคำคาดหวังอย่างน้อยครึ่งหนึ่ง (expected_keywords ใน data/eval/rag_questions.json)
metric: Hit@K, MRR@K (คำถามที่ตอบได้), Empty-rate บนคำถามที่ตอบไม่ได้ (ดึงว่าง = ช่วยให้ LLM ปฏิเสธถูก)
"""
import math
import time

from ..llm.bench.datasets import rag
from .retrievers import DenseKnowledge, GraphKnowledge, HybridKnowledge, RoutedKnowledge


def configs(ctx):
    return [("dense", DenseKnowledge(ctx)), ("dense + rerank20", DenseKnowledge(ctx, rerank_pool=20)),
            ("graph", GraphKnowledge(ctx)), ("hybrid rrf", HybridKnowledge(ctx)),
            ("hybrid rrf + rerank20", HybridKnowledge(ctx, rerank_pool=20)),
            ("routed", RoutedKnowledge(ctx)), ("routed + rerank20", RoutedKnowledge(ctx, rerank_pool=20))]


def _relevant(text, kws):
    need = math.ceil(len(kws) / 2)
    return sum(k.lower() in text.lower() for k in kws) >= need


def evaluate(ctx, k=5, log=print) -> list:
    qs = rag()
    rows = []
    for name, r in configs(ctx):
        hit = mrr = empty = 0
        t0 = time.perf_counter()
        per_style = {}
        for q in qs:
            items = r.retrieve(q["question"], k).items
            if not q["answerable"]:
                empty += not items
                continue
            rel = [i for i, it in enumerate(items) if _relevant(it.text, q["expected_keywords"])]
            h = bool(rel)
            hit += h
            mrr += 1 / (rel[0] + 1) if rel else 0
            per_style.setdefault(q.get("style", "direct"), []).append(h)
        n_ans = sum(q["answerable"] for q in qs)
        n_un = len(qs) - n_ans
        rows.append({"config": name, f"Hit@{k}": round(hit / n_ans, 3), f"MRR@{k}": round(mrr / n_ans, 3),
                     "hit_paraphrase": round(sum(per_style.get("paraphrase", [])) / max(1, len(per_style.get("paraphrase", []))), 3),
                     "empty_on_unanswerable": f"{empty}/{n_un}",
                     "ms_per_query": round((time.perf_counter() - t0) * 1000 / len(qs), 1)})
        log(f"  {name}: done")
    return rows
