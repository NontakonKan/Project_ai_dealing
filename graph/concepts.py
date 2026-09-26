"""หา concept (รหัส taxonomy) ในคำถาม — 2 ชั้น

1. alias/label ตรงตัว (เร็ว แม่น แต่พลาดเมื่อผู้ใช้เล่าเป็นประโยค)
2. embedding (bge-m3 ผ่าน Ollama) เทียบคำถามกับ label + definition + aliases ของ concept
   เก็บเมื่อ cosine >= MIN_SCORE และห่างจากอันดับ 1 ไม่เกิน MARGIN
   วัดจริง: "สงสัยว่าตัวเองจำผิด" -> rf:gaslighting 0.66 / คำถามนอกเรื่อง (ค่าเทอม) สูงสุด 0.39
"""
import math
from functools import lru_cache

from pipelines.common import taxonomy

GROUPS = ("red_flags", "attachment_styles", "love_components", "traits", "comm_styles", "research_factors")
EXTRA_KEYS = {"anxious": "attach:anxious", "avoidant": "attach:avoidant", "secure": "attach:secure",
              "fearful": "attach:fearful", "sternberg": "love:intimacy", "สามเหลี่ยม": "love:intimacy"}
EMBED_MODEL, MIN_SCORE, MARGIN = "bge-m3", 0.62, 0.08


def by_alias(query: str) -> set:
    q = query.lower()
    labels = taxonomy.labels()
    found = {cid for cid, als in taxonomy.aliases().items() if any(a.lower() in q for a in als if len(a) >= 3)}
    found |= {cid for cid, lab in labels.items() if len(lab) >= 4 and lab in query}
    found |= {cid for key, cid in EXTRA_KEYS.items() if key in q}
    return found


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
    if use_embedding:
        try:
            found |= set(by_embedding(query))
        except Exception:
            pass   # Ollama ไม่ได้เปิด -> ใช้ alias อย่างเดียว
    return found
