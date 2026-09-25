"""แปลงคำอิสระ -> รหัส taxonomy (3 ชั้น เร็วไปช้า)

  1. exact   ตรงกับ label/alias พอดี
  2. contains มี alias อยู่ในคำ (เลือก alias ที่ยาวที่สุด)
  3. embedding bge-m3 เทียบกับ label+aliases (cosine >= threshold)
  ไม่ผ่านทั้งหมด -> unmapped_terms.jsonl ให้คนมาตรวจแล้วเพิ่มใน taxonomy
"""
import json
import math
from functools import lru_cache

from ..common import taxonomy
from ..common.io_utils import read_json, write_json
from ..common.paths import PROCESSED
from ..llm import ollama_client

EMBED_MODEL = "bge-m3"
THRESHOLD = 0.72   # 0.62 จับ "ปั่นจักรยาน" -> trait:adventurous (0.68) ผิด; "เงียบๆ ไม่ค่อยพูด" -> introvert = 0.77
CACHE = PROCESSED / "taxonomy_embeddings.json"
UNMAPPED = PROCESSED / "unmapped_terms.jsonl"


def _norm(s):
    return "".join(s.lower().split())


def _allowed(groups):
    return {i for g in (groups or taxonomy.GROUPS) for i in taxonomy.ids(g)}


@lru_cache(maxsize=1)
def _alias_index():
    labels, idx = taxonomy.labels(), []
    for tid, als in taxonomy.aliases().items():
        for a in {*als, labels[tid]}:
            idx.append((_norm(a), tid))
    return sorted(idx, key=lambda x: -len(x[0]))


def _cos(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)) or 1)


@lru_cache(maxsize=1)
def _tax_vectors():
    key = f"{taxonomy.load()['version']}|{EMBED_MODEL}"
    if CACHE.exists():
        cached = read_json(CACHE)
        if cached.get("key") == key:
            return cached["vectors"]
    labels = taxonomy.labels()
    ids = list(labels)
    texts = [f"{labels[i]} {' '.join(taxonomy.aliases().get(i, []))}" for i in ids]
    vecs = dict(zip(ids, ollama_client.embed(EMBED_MODEL, texts)))
    write_json(CACHE, {"key": key, "vectors": vecs})
    return vecs


def normalize(term: str, groups=None, use_embedding=True) -> dict:
    allowed, t = _allowed(groups), _norm(term)
    for a, tid in _alias_index():
        if tid in allowed and a == t:
            return {"term": term, "id": tid, "method": "exact", "score": 1.0}
    for a, tid in _alias_index():
        if tid in allowed and len(a) >= 3 and a in t:
            return {"term": term, "id": tid, "method": "contains", "score": round(len(a) / len(t), 2)}
    if use_embedding:
        qv = ollama_client.embed(EMBED_MODEL, [term])[0]
        best = max(((_cos(qv, v), tid) for tid, v in _tax_vectors().items() if tid in allowed), default=(0, None))
        if best[0] >= THRESHOLD:
            return {"term": term, "id": best[1], "method": "embedding", "score": round(best[0], 3)}
    _log_unmapped(term, groups)
    return {"term": term, "id": None, "method": "unmapped", "score": 0.0}


def _log_unmapped(term, groups):
    UNMAPPED.parent.mkdir(parents=True, exist_ok=True)
    with UNMAPPED.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"term": term, "groups": list(groups or [])}, ensure_ascii=False) + "\n")
