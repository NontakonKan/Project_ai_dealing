"""Cross-encoder rerank สำหรับการค้นความรู้ (knowledge) — ขั้นหลังดึง top-N จาก ChromaDB

bi-encoder (bge-m3) หาเร็วแต่หยาบ: คำถามเรื่อง ghosting เคยได้ chunk งานวิจัยที่ไม่เกี่ยวเป็นอันดับ 1-3
cross-encoder (bge-reranker-v2-m3) อ่านคำถาม+chunk พร้อมกัน -> จัดอันดับใหม่แม่นกว่า แต่ช้า จึงใช้กับ top-N
"""
from functools import lru_cache

MODEL = "BAAI/bge-reranker-v2-m3"


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(MODEL, max_length=512)


def rerank(query: str, rows: list, top_k: int) -> list:
    """rows = ผลจาก DenseIndex.search (มี 'text') -> เรียงใหม่ด้วย cross-encoder, เก็บคะแนนเดิมไว้ใน dense_score"""
    if not rows:
        return rows
    scores = _model().predict([(query, r["text"]) for r in rows], batch_size=16, show_progress_bar=False)
    out = [{**r, "dense_score": r["score"], "score": float(s)} for r, s in zip(rows, scores)]
    return sorted(out, key=lambda x: -x["score"])[:top_k]
