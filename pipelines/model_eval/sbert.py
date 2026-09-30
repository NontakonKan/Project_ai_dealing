"""SBERT (bi-encoder) 5 ตัว: ค้น chunk ด้วย cosine ทั้งคลัง + แยกเจตนาแบบเทียบประโยคตัวอย่าง

งานที่บอทใช้ SBERT จริง: Dense RAG (bge-m3) และแยกเจตนา (app/intent_model.py)
"""
import time

import numpy as np

from ..dense.embedding import encode
from .data import chunks, gold, questions

MODELS = {
    "bge-m3 (ใช้จริง)": "BAAI/bge-m3",
    "e5-large": "intfloat/multilingual-e5-large",
    "e5-base": "intfloat/multilingual-e5-base",
    "LaBSE": "sentence-transformers/LaBSE",
    "MiniLM-L12": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
}
K = 5


def _intent_sets():
    from app.intent_eval import TEST, TEST_FRESH
    from app.intent_model import INTENTS, ROUTE
    examples = [(name, e) for name, (_, ex) in INTENTS.items() for e in ex]
    tests = [(ROUTE.get(k, k), t) for s in (TEST, TEST_FRESH) for k, ts in s.items() for t in ts]
    return examples, tests, ROUTE


def evaluate(name, model_id, docs=None, qs=None) -> dict:
    docs, qs = docs or chunks(), qs or questions()
    labels = gold(qs, docs)
    t0 = time.perf_counter()
    dv = encode([t for _, t in docs], model_id, role="document")
    enc_s = time.perf_counter() - t0
    asked = [q for q in qs if q["qid"] in labels]
    qv = encode([q["question"] for q in asked], model_id, role="query")
    hit = mrr = 0.0
    for q, v in zip(asked, qv):
        top = np.argsort(-(dv @ v))[:K]
        ranks = [i for i, j in enumerate(top) if docs[j][0] in labels[q["qid"]]]
        hit += bool(ranks)
        mrr += 1 / (ranks[0] + 1) if ranks else 0.0
    # แยกเจตนา: เทียบกับประโยคตัวอย่าง เฉลี่ย 2 ตัวอย่างที่ใกล้สุดต่อเจตนา (วิธีเดียวกับ intent_model)
    examples, tests, route = _intent_sets()
    ev = encode([e for _, e in examples], model_id, role="document")
    tv = encode([t for _, t in tests], model_id, role="query")
    correct = 0
    for (want, _), v in zip(tests, tv):
        sims = ev @ v
        per = {}
        for (lab, _), s in zip(examples, sims):
            per.setdefault(lab, []).append(float(s))
        pred = max(per, key=lambda k: np.mean(sorted(per[k], reverse=True)[:2]))
        correct += route.get(pred, pred) == want
    return {"model": name, "model_id": model_id, f"Hit@{K}": round(hit / len(asked), 3),
            f"MRR@{K}": round(mrr / len(asked), 3), "intent_acc": round(correct / len(tests), 3),
            "n_questions": len(asked), "n_intent": len(tests), "dim": int(dv.shape[1]),
            "chunks_per_s": round(len(docs) / enc_s, 1)}


def run(log=print) -> list:
    docs, qs = chunks(), questions()
    rows = []
    for name, mid in MODELS.items():
        rows.append(evaluate(name, mid, docs, qs))
        log(f"  SBERT {name}: Hit@5 {rows[-1]['Hit@5']} MRR {rows[-1]['MRR@5']} intent {rows[-1]['intent_acc']}")
    return rows
