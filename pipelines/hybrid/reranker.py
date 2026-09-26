"""Cross-encoder rerank (BAAI/bge-reranker-v2-m3) — ขั้นสุดท้ายหลัง fusion

ทำไม: bi-encoder (bge-m3) แยกค่านิยมตรงข้ามได้แย่ ("อยากมีลูก" vs "ไม่อยากมีลูก" cosine 0.70 vs 0.63)
      cross-encoder อ่านสองข้อความพร้อมกัน แยกได้ชัดกว่า (0.33 vs 0.02) แต่ช้า -> ใช้กับ top-N เท่านั้น
คะแนนคู่ = harmonic mean ของสองทิศ (สเปก A vs ตัวตน B, สเปก B vs ตัวตน A) เหมือน Dense ของฟาริก
"""
from functools import lru_cache

MODEL = "BAAI/bge-reranker-v2-m3"


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(MODEL, max_length=512)


def pair_scores(ctx, user_id, candidate_ids) -> dict:
    cache = ctx.__dict__.setdefault("rerank_cache", {})
    todo = [c for c in candidate_ids if (user_id, c) not in cache]
    if todo:
        s = lambda u: ctx.users[u]["summaries"]
        pairs = [(s(user_id)["preference_text"], s(c)["persona_text"]) for c in todo] + \
                [(s(c)["preference_text"], s(user_id)["persona_text"]) for c in todo]
        out = _model().predict(pairs, batch_size=32, show_progress_bar=False)
        n = len(todo)
        for i, c in enumerate(todo):
            f, r = float(out[i]), float(out[n + i])
            cache[(user_id, c)] = 2 * f * r / (f + r) if f + r > 0 else 0.0
    return {c: cache[(user_id, c)] for c in candidate_ids}
