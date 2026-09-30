"""BERT cross-encoder 5 ตัว: เรียงผู้สมัครใหม่ (rerank) + แยกคำถามที่ตอบได้/ตอบไม่ได้จากคะแนนสูงสุด

งานที่บอทใช้จริง: ด่านความเกี่ยวข้อง + ตรวจหลักฐาน (bge-reranker-v2-m3)
ผู้สมัคร = 30 อันดับแรกจาก bge-m3 ของทุกคำถาม (ชุดเดียวกันทุกโมเดล -> วัดแค่ความสามารถในการเรียงใหม่)
AUROC = โอกาสที่คำถามตอบได้ได้คะแนนสูงสุดมากกว่าคำถามนอกคลัง (1.0 = แยกได้หมด, 0.5 = เดาสุ่ม)
"""
import time

import numpy as np

from ..dense.embedding import encode
from .data import chunks, gold, questions

MODELS = {
    "bge-reranker-v2-m3 (ใช้จริง)": "BAAI/bge-reranker-v2-m3",
    "bge-reranker-large": "BAAI/bge-reranker-large",
    "bge-reranker-base": "BAAI/bge-reranker-base",
    "mMiniLM-L12 (mMARCO)": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
    "BERT-multilingual (MS MARCO)": "amberoad/bert-multilingual-passage-reranking-msmarco",
}
POOL = 30


def candidates(docs, qs):
    dv = encode([t for _, t in docs], "BAAI/bge-m3", role="document")
    qv = encode([q["question"] for q in qs], "BAAI/bge-m3", role="query")
    return {q["qid"]: [int(j) for j in np.argsort(-(dv @ v))[:POOL]] for q, v in zip(qs, qv)}


def _auroc(pos, neg):
    """Mann-Whitney: สัดส่วนคู่ (ตอบได้, ตอบไม่ได้) ที่ตอบได้ได้คะแนนสูงกว่า (เสมอ = ครึ่ง)"""
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def evaluate(name, model_id, docs, qs, pool) -> dict:
    from sentence_transformers import CrossEncoder
    labels = gold(qs, docs)
    model = CrossEncoder(model_id, max_length=512)
    hit1 = mrr = n = 0
    best_pos, best_neg, n_pairs = [], [], 0
    t0 = time.perf_counter()
    for q in qs:
        cand = pool[q["qid"]]
        s = np.asarray(model.predict([(q["question"], docs[j][1]) for j in cand], show_progress_bar=False))
        s = s[:, -1] if s.ndim == 2 else s        # โมเดลแบบ 2 คลาส: ใช้คะแนนคลาส "เกี่ยวข้อง"
        n_pairs += len(cand)
        (best_pos if q["answerable"] else best_neg).append(float(s.max()))
        if q["qid"] in labels and any(docs[j][0] in labels[q["qid"]] for j in cand):
            order = [cand[i] for i in np.argsort(-s)][:5]
            ranks = [i for i, j in enumerate(order) if docs[j][0] in labels[q["qid"]]]
            hit1 += bool(ranks) and ranks[0] == 0
            mrr += 1 / (ranks[0] + 1) if ranks else 0.0
            n += 1
    ms = (time.perf_counter() - t0) * 1000 / n_pairs
    return {"model": name, "model_id": model_id, "Hit@1": round(hit1 / n, 3), "MRR@5": round(mrr / n, 3),
            "AUROC": round(_auroc(best_pos, best_neg), 3), "ms_per_pair": round(ms, 1), "n_questions": n}


def run(log=print) -> list:
    docs, qs = chunks(), questions()
    pool = candidates(docs, qs)
    rows = []
    for name, mid in MODELS.items():
        rows.append(evaluate(name, mid, docs, qs, pool))
        log(f"  BERT {name}: Hit@1 {rows[-1]['Hit@1']} MRR {rows[-1]['MRR@5']} AUROC {rows[-1]['AUROC']}")
    return rows
