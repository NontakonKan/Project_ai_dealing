"""ติด metadata ให้ chunk: concepts (taxonomy id), topics, target_trait

ใช้ id ชุดเดียวกับ User Profile และ Knowledge Graph -> กรอง chunk ด้วย red flag/trait ของคู่ได้ตรงๆ
"""
import re
from collections import Counter
from functools import lru_cache

from ..common import taxonomy
from ..common.io_utils import read_json
from ..common.paths import LEXICON_FILE

CONTEXT_WINDOW = 60  # ±ตัวอักษรรอบคำกำกวมที่ต้องมีคำบริบท (context_rules ใน concept_lexicon.json)
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
    rules = lex.get("context_rules", {})
    compile_ = lambda kws: [(re.compile(rf"\b{re.escape(k)}\b" if k.isascii() else re.escape(k), re.I), rules.get(k))
                            for k in kws]
    return ({cid: compile_(k) for cid, k in concept_kw.items() if k},
            {tid: compile_(k) for tid, k in lex["topic_keywords"].items()})


def _ok(text, m, rule) -> bool:
    """คำกำกวม: ต้องมีคำบริบทอยู่ใกล้ๆ และไม่ตามหลังคำปฏิเสธ ("ไม่มั่นคง" ไม่ใช่ secure)"""
    if not rule:
        return True
    before = text[max(0, m.start() - 4):m.start()]
    if any(before.endswith(w) for w in rule.get("not_after", [])):
        return False
    around = text[max(0, m.start() - CONTEXT_WINDOW):m.end() + CONTEXT_WINDOW]
    return any(w in around for w in rule.get("near", []))


def _count(text, pats):
    return sum(_ok(text, m, rule) for p, rule in pats for m in p.finditer(text))


def tag(text: str, category: str, concepts=True) -> dict:
    """concepts=False: ไม่ติด concept ความสัมพันธ์ (เอกสารการแพทย์ -> Graph ไม่ดึงไปตอบเรื่องคู่รัก, Dense ยังค้นเจอ)"""
    concept_pats, topic_pats = _patterns()
    concepts = Counter({cid: c for cid, ps in concept_pats.items() if (c := _count(text, ps))}) if concepts else Counter()
    topics = [tid for tid, ps in topic_pats.items() if _count(text, ps)]
    ranked = [cid for cid, _ in concepts.most_common()]
    return {
        "category": category,
        "concepts": ranked,
        "concept_counts": dict(concepts.most_common()),
        "topics": topics,
        "target_trait": [c for c in ranked if c.split(":")[0] in ("trait", "attach")],
    }
