"""เทียบ Dense-only / Graph-only / Hybrid บนเฉลยและ candidate ชุดเดียวกัน

metric เดียวกับ pipelines/dense/evaluation.py (ของฟาริก): P@K, R@K, MRR, nDCG@K, Violation@K
อ่านเฉลยเฉพาะในไฟล์นี้ — matcher/graph/dense ไม่เคยเห็น ground truth
"""
import time
from math import log2

from ..common.io_utils import read_json
from ..common.paths import MOCK
from . import matcher
from .config import HybridConfig

GRID = [
    ("dense (λneg=0)", "dense", HybridConfig(lambda_neg=0.0)),
    ("dense (λneg=0.15)", "dense", HybridConfig(lambda_neg=0.15)),
    ("graph (no rf filter)", "graph", HybridConfig(hard_redflag=False, lambda_rf=0.0, w_appearance=0.0)),
    ("graph", "graph", HybridConfig()),
    ("hybrid rrf (no rf filter)", "hybrid", HybridConfig(hard_redflag=False, lambda_rf=0.0)),
    ("hybrid rrf", "hybrid", HybridConfig(fusion="rrf")),
    ("hybrid weighted α=0.3", "hybrid", HybridConfig(fusion="weighted", alpha=0.3)),
    ("hybrid weighted α=0.5", "hybrid", HybridConfig(fusion="weighted", alpha=0.5)),
    ("hybrid weighted α=0.7", "hybrid", HybridConfig(fusion="weighted", alpha=0.7)),
    ("hybrid rrf w_app=0", "hybrid", HybridConfig(fusion="rrf", w_appearance=0.0)),
    ("hybrid rrf w_app=0.4", "hybrid", HybridConfig(fusion="rrf", w_appearance=0.4)),
    ("hybrid: graph + dense values facet w=0.3", "graph", HybridConfig(w_values=0.3)),
    ("hybrid α=0.3 + values facet w=0.3", "hybrid", HybridConfig(fusion="weighted", alpha=0.3, w_values=0.3)),
    ("hybrid α=0.2 + values facet w=0.3", "hybrid", HybridConfig(fusion="weighted", alpha=0.2, w_values=0.3)),
    ("hybrid: graph + LLM-structured values w=0.15", "graph", HybridConfig(w_values_struct=0.15)),
    ("hybrid: graph + LLM-structured values w=0.3", "graph", HybridConfig(w_values_struct=0.3)),
    ("hybrid α=0.2 + LLM-structured values w=0.3", "hybrid", HybridConfig(fusion="weighted", alpha=0.2, w_values_struct=0.3)),
    ("dense + rerank top30", "dense", HybridConfig(rerank_top=30, rerank_beta=0.5)),
    ("graph + rerank top30", "graph", HybridConfig(rerank_top=30, rerank_beta=0.5)),
    ("hybrid α=0.3 + rerank top30 β=0.3", "hybrid", HybridConfig(fusion="weighted", alpha=0.3, rerank_top=30, rerank_beta=0.3)),
    ("hybrid α=0.3 + rerank top30 β=0.5", "hybrid", HybridConfig(fusion="weighted", alpha=0.3, rerank_top=30, rerank_beta=0.5)),
    ("hybrid α=0.3 + rerank top30 β=0.7", "hybrid", HybridConfig(fusion="weighted", alpha=0.3, rerank_top=30, rerank_beta=0.7)),
]


def _metrics(found, relevant, excluded, k):
    hits = [int(u in relevant) for u in found[:k]]
    ideal = sum(1 / log2(i + 2) for i in range(min(k, len(relevant))))
    return {"p": sum(hits) / k, "r": sum(hits) / len(relevant),
            "mrr": next((1 / (i + 1) for i, h in enumerate(hits) if h), 0.0),
            "ndcg": sum(h / log2(i + 2) for i, h in enumerate(hits)) / ideal if ideal else 0.0,
            "viol": len(excluded & set(found[:k])) / k}


def evaluate(ctx, grid=GRID, ks=(5, 10), limit=None, log=print) -> list:
    truth = [r for r in read_json(MOCK / "ground_truth_pairs.json") if r["relevant"] and r["user_id"] in ctx.users][:limit]
    out = []
    for name, mode, cfg in grid:
        t0 = time.perf_counter()
        sums = {k: {"p": 0, "r": 0, "mrr": 0, "ndcg": 0, "viol": 0} for k in ks}
        for row in truth:
            found = [x["user_id"] for x in matcher.rank(ctx, row["user_id"], mode, cfg, top_k=max(ks))]
            rel, exc = {x["user_id"] for x in row["relevant"]}, set(row["must_exclude"])
            for k in ks:
                for m, v in _metrics(found, rel, exc, k).items():
                    sums[k][m] += v
        ms = (time.perf_counter() - t0) * 1000 / len(truth)
        for k in ks:
            n = len(truth)
            out.append({"config": name, "mode": mode, "K": k, "P@K": round(sums[k]["p"] / n, 4),
                        "R@K": round(sums[k]["r"] / n, 4), "MRR": round(sums[k]["mrr"] / n, 4),
                        "nDCG@K": round(sums[k]["ndcg"] / n, 4), "Violation@K": round(sums[k]["viol"] / n, 4),
                        "ms_per_user": round(ms, 1), "queries": n})
        log(f"  {name}: done ({ms:.0f} ms/user)")
    return out
