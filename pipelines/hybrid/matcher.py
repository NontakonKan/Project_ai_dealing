"""จัดอันดับคู่ 3 โหมดบน candidate ชุดเดียวกัน -> เทียบกันได้ตรงๆ

dense  = rank() ของฟาริก (harmonic mean สองทาง - negative penalty)
graph  = graph_score + red flag + appearance
hybrid = fuse(dense, graph) + red flag + appearance
"""
from ..dense.matching import rank as dense_rank
from graph import scorer as graph_scorer
from .config import HybridConfig
from .fusion import adjust, fuse, minmax
from .reranker import pair_scores


def dense_scores(ctx, user_id, cfg) -> dict:
    key = (user_id, cfg.lambda_neg)
    if key not in ctx.dense_cache:   # คะแนน Dense ไม่ขึ้นกับค่า fusion -> คำนวณครั้งเดียวต่อ grid
        rows = dense_rank(user_id, ctx.dense, ctx.users, ctx.events, top_k=10 ** 6, threshold=-1.0,
                          penalty_weight=cfg.lambda_neg)
        ctx.dense_cache[key] = {r["user_id"]: r for r in rows}
    return ctx.dense_cache[key]


def rank(ctx, user_id, mode="hybrid", cfg=None, top_k=10, explain=False) -> list:
    cfg = cfg or HybridConfig()
    cands = ctx.candidates(user_id)
    g = ctx.graph
    info = {c: graph_scorer.pair(g, user_id, c) for c in cands}
    dense = {c: r["score"] for c, r in dense_scores(ctx, user_id, cfg).items() if c in info} if mode != "graph" else {}
    graph = {c: info[c]["graph_score"] for c in cands}

    if mode == "dense":
        final = dense
    else:
        base = graph if mode == "graph" else fuse(dense, graph, cfg)
        spread = (max(base.values()) - min(base.values())) if base else 1.0
        final = adjust(base, info, cfg, spread or 1.0)
        if cfg.w_values:
            final = {c: v + (spread or 1.0) * cfg.w_values * ctx.values_sim(user_id, c) for c, v in final.items()}
        if cfg.w_values_struct:
            final = {c: v + (spread or 1.0) * cfg.w_values_struct * ctx.values_struct_sim(user_id, c) for c, v in final.items()}

    ordered = sorted(final.items(), key=lambda x: (-x[1], x[0]))
    rr = {}
    if cfg.rerank_top:
        head = dict(ordered[:cfg.rerank_top])
        rr = pair_scores(ctx, user_id, list(head))
        nb, nr = minmax(head), minmax(rr)
        mixed = {c: (1 - cfg.rerank_beta) * nb[c] + cfg.rerank_beta * nr[c] for c in head}
        ordered = sorted(mixed.items(), key=lambda x: (-x[1], x[0])) + ordered[cfg.rerank_top:]
    ordered = ordered[:top_k]
    out = []
    for c, s in ordered:
        row = {"user_id": c, "score": round(s, 6), "dense": round(dense.get(c, 0.0), 4),
               "graph": graph[c], "appearance": info[c]["appearance"],
               "redflags": [h["id"] for h in info[c]["redflags"]], "features": info[c]["features"],
               "rerank": round(rr[c], 4) if c in rr else None}
        if explain:
            row["facts"] = graph_scorer.pair(g, user_id, c, facts=True)["facts"]
        out.append(row)
    return out
