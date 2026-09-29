"""หา concept (รหัส taxonomy) ในคำถาม — 3 ชั้น

1. alias/label ตรงตัว (เร็ว แม่น แต่พลาดเมื่อผู้ใช้เล่าเป็นประโยค)
2. เปรียบเทียบข้อความกับคำอธิบาย concept; รับเฉพาะอันดับที่ชัดเจน
3. embedding (bge-m3 ผ่าน Ollama) เทียบคำถามกับ label + definition + aliases ของ concept
   เก็บเมื่อ cosine >= MIN_SCORE และห่างจากอันดับ 1 ไม่เกิน MARGIN
   วัดจริง: "สงสัยว่าตัวเองจำผิด" -> rf:gaslighting 0.66 / คำถามนอกเรื่อง (ค่าเทอม) สูงสุด 0.39
"""
import math
from functools import lru_cache

from pipelines.common import taxonomy

GROUPS = ("red_flags", "attachment_styles", "love_components", "traits", "comm_styles", "research_factors")
EXTRA_KEYS = {"anxious": "attach:anxious", "avoidant": "attach:avoidant", "secure": "attach:secure",
              "fearful": "attach:fearful", "dismissing": "attach:avoidant",
              "หมางเมิน": "attach:avoidant", "sternberg": "love:intimacy", "สามเหลี่ยม": "love:intimacy"}
EMBED_MODEL, MIN_SCORE, MARGIN = "bge-m3", 0.62, 0.08
DESCRIPTION_MIN_SCORE, DESCRIPTION_MARGIN = 0.30, 0.12


def by_alias(query: str) -> set:
    q = query.lower()
    labels = taxonomy.labels()
    found = {cid for cid, als in taxonomy.aliases().items() if any(a.lower() in q for a in als if len(a) >= 3)}
    found |= {cid for cid, lab in labels.items() if len(lab) >= 4 and lab in query}
    found |= {cid for key, cid in EXTRA_KEYS.items() if key in q}
    return found


@lru_cache(maxsize=1)
def _description_index():
    from sklearn.feature_extraction.text import TfidfVectorizer

    tax = taxonomy.load()
    rows = [item for group in GROUPS for item in tax.get(group, [])]
    if not rows:
        return [], None, None
    texts = [f"{item['label_th']} {item.get('definition', '')} {' '.join(item.get('aliases', []))}"
             for item in rows]
    vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 4), sublinear_tf=True)
    return [item["id"] for item in rows], vectorizer, vectorizer.fit_transform(texts)


def by_description(query: str) -> set:
    """Use a concept definition only when its lexical match is unambiguous."""
    ids, vectorizer, vectors = _description_index()
    if not ids:
        return set()
    scores = (vectors @ vectorizer.transform([query]).T).toarray().ravel()
    order = scores.argsort()[::-1]
    best, runner_up = float(scores[order[0]]), float(scores[order[1]]) if len(order) > 1 else 0.0
    return {ids[order[0]]} if best >= DESCRIPTION_MIN_SCORE and best - runner_up >= DESCRIPTION_MARGIN else set()


@lru_cache(maxsize=1)
def _concept_vectors():
    from pipelines.llm import ollama_client
    tax = taxonomy.load()
    rows = [t for g in GROUPS for t in tax.get(g, [])]
    texts = [f"{t['label_th']} {t.get('definition', '')} {' '.join(t.get('aliases', []))}".strip() for t in rows]
    return [t["id"] for t in rows], ollama_client.embed(EMBED_MODEL, texts)


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a) * sum(y * y for y in b)) or 1)


def by_embedding(query: str) -> dict:
    from pipelines.llm import ollama_client
    ids, vecs = _concept_vectors()
    qv = ollama_client.embed(EMBED_MODEL, [query])[0]
    scored = sorted(((_cos(qv, v), i) for i, v in zip(ids, vecs)), reverse=True)
    top = scored[0][0] if scored else 0
    return {i: round(s, 3) for s, i in scored if s >= MIN_SCORE and s >= top - MARGIN}


def detect(query: str, use_embedding=True) -> set:
    found = by_alias(query)
    if not found:
        found = by_description(query)
    if use_embedding and not found:
        try:
            found |= set(by_embedding(query))
        except Exception:
            pass   # Ollama ไม่ได้เปิด -> ใช้ alias อย่างเดียว
    return found
