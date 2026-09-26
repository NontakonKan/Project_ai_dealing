"""รวมคะแนน Dense + Graph

rrf:      score = 1/(k + rank_dense) + 1/(k + rank_graph)       ไม่สน scale ของคะแนน
weighted: score = alpha * minmax(dense) + (1-alpha) * minmax(graph)
แล้ว: - red flag (hard filter หรือหัก lambda_rf) + appearance (soft, w_appearance)
"""


def minmax(scores: dict) -> dict:
    if not scores:
        return {}
    lo, hi = min(scores.values()), max(scores.values())
    return {k: (v - lo) / (hi - lo) if hi > lo else 0.5 for k, v in scores.items()}


def ranks(scores: dict) -> dict:
    return {k: i + 1 for i, (k, _) in enumerate(sorted(scores.items(), key=lambda x: (-x[1], x[0])))}


def fuse(dense: dict, graph: dict, cfg) -> dict:
    ids = set(dense) | set(graph)
    if cfg.fusion == "rrf":
        rd, rg = ranks(dense), ranks(graph)
        worst = len(ids) + 1
        return {i: 1 / (cfg.rrf_k + rd.get(i, worst)) + 1 / (cfg.rrf_k + rg.get(i, worst)) for i in ids}
    nd, ng = minmax(dense), minmax(graph)
    return {i: cfg.alpha * nd.get(i, 0.0) + (1 - cfg.alpha) * ng.get(i, 0.0) for i in ids}


def adjust(base: dict, pair_info: dict, cfg, scale: float) -> dict:
    """penalty / appearance บนคะแนนที่ fuse แล้ว; scale = ช่วงของ base เพื่อให้หน่วยเทียบกันได้"""
    out = {}
    for i, s in base.items():
        info = pair_info[i]
        if info["redflags"] and cfg.hard_redflag:
            continue
        rf = sum(h["weight"] for h in info["redflags"])
        out[i] = s + scale * (cfg.appearance_weight * info["appearance"] - cfg.lambda_rf * rf)
    return out
