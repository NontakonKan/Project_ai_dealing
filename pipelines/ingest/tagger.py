"""ติด metadata ให้ chunk: concepts (taxonomy id), topics, target_trait

ใช้ id ชุดเดียวกับ User Profile และ Knowledge Graph -> กรอง chunk ด้วย red flag/trait ของคู่ได้ตรงๆ
"""
import re
from collections import Counter
from functools import lru_cache

from ..common import taxonomy
from ..common.io_utils import read_json
from ..common.paths import LEXICON_FILE

MIN_ALIAS_LEN = 4  # alias สั้น (เช่น "วีน", "ด่า") match ผิดในข้อความวิชาการบ่อย
SKIP_PREFIXES = ("hobby:",)  # งานอดิเรกไม่ใช่ความรู้เชิงจิตวิทยา + match ผิดบ่อย ("วาดภาพ" เชิงเปรียบเทียบ)


@lru_cache(maxsize=1)
def _patterns():
    lex = read_json(LEXICON_FILE)
    concept_kw = {cid: set(kws) for cid, kws in lex["concepts"].items()}
    labels = taxonomy.labels()
    for cid, als in taxonomy.aliases().items():
        if cid.startswith(SKIP_PREFIXES):
            continue
        kws = concept_kw.setdefault(cid, set())
        kws.update(a for a in als if len(a) >= MIN_ALIAS_LEN)
        if len(labels.get(cid, "")) >= MIN_ALIAS_LEN and " " not in labels[cid]:
            kws.add(labels[cid])
    compile_ = lambda kws: [re.compile(rf"\b{re.escape(k)}\b" if k.isascii() else re.escape(k), re.I) for k in kws]
    return ({cid: compile_(k) for cid, k in concept_kw.items() if k},
            {tid: compile_(k) for tid, k in lex["topic_keywords"].items()})


def _count(text, pats):
    return sum(len(p.findall(text)) for p in pats)


def tag(text: str, category: str) -> dict:
    concept_pats, topic_pats = _patterns()
    concepts = Counter({cid: c for cid, ps in concept_pats.items() if (c := _count(text, ps))})
    topics = [tid for tid, ps in topic_pats.items() if _count(text, ps)]
    ranked = [cid for cid, _ in concepts.most_common()]
    return {
        "category": category,
        "concepts": ranked,
        "concept_counts": dict(concepts.most_common()),
        "topics": topics,
        "target_trait": [c for c in ranked if c.split(":")[0] in ("trait", "attach")],
    }
