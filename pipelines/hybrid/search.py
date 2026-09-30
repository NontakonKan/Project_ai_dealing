"""ค้นความรู้สำหรับตอบปรึกษา (ใช้ทั้งบอทและ rag_judge ให้เป็นเส้นทางเดียวกัน)

รอบ 1: คำถามเดิม + คำพ้อง (query_expand) -> ด่านความเกี่ยวข้อง
รอบ 2 (เฉพาะเมื่อรอบแรกไม่เจอ/คะแนนต่ำ): ให้ LLM แปลงสถานการณ์เป็นหัวข้อทั่วไปที่เอกสารใช้ แล้วค้น+กรองใหม่
  วัดจริง (log LINE): "ไม่กล้าปฏิเสธ เพราะพ่อแม่ไม่อนุญาต ควรพูดกับเค้ายังไง" หน้าที่เกี่ยวข้องสุด 0.21
     -> หัวข้อ "การตั้งขอบเขตและบอกความต้องการของตัวเอง" ได้บทความ Healthy Boundary 0.63
  "เค้าถามเรื่องส่วนตัว เปลี่ยนเรื่องยังไงดี" 0.10 -> "ช่วงเริ่มคุยกันควรคุยเรื่องส่วนตัวแค่ไหน" วิทยานิพนธ์ หน้า 134 0.78
รอบ 2 ยังดึง chunk ข้างเคียง (ก่อน/หลัง) ของหน้าที่ผ่านด่าน มาให้ด่านให้คะแนนด้วย — เนื้อหามักต่อข้ามรอยตัด chunk
  วัดจริง: บทความ Healthy Boundary c05 ผ่านด่าน (0.15) แต่ตัวอย่างประโยคปฏิเสธอยู่ใน c04 (0.61) ซึ่งหลุดเพราะจำกัด 3 chunk/แหล่ง
หัวข้อจาก LLM ใช้ค้นเท่านั้น — คำตอบยังต้องผ่านด่านเดิม (คะแนนความเกี่ยวข้อง + verify_answer เทียบกับเอกสาร)
"""
import re
from dataclasses import dataclass, field
from functools import lru_cache

from .gate import filter_relevant

REWRITE_BELOW = 0.45    # รอบแรกได้หน้าที่เกี่ยวข้องสูงสุดต่ำกว่านี้ -> ลองแปลงคำถามเพื่อครอบคลุมบริบทที่หลากหลาย
NEIGHBOR_OF = 3         # ดึง chunk ข้างเคียงของหน้าที่ผ่านด่านกี่อันดับแรก
_CID = re.compile(r"^(.*_c)(\d+)$")


@dataclass
class Found:
    result: object
    route: str = "-"
    n_before: int = 0
    topics: list = field(default_factory=list)


@lru_cache(maxsize=1)
def kb_topics() -> tuple:
    """ชื่อเอกสารในคลัง (ตัดวงเล็บผู้แต่ง/หน่วยงาน) ให้ขั้นแปลงคำถามรู้ว่ามีหัวข้ออะไรบ้าง
    วัดจริง: "คนที่คุยในแอปขอยืมเงิน" แปลงเป็น "การถูกขอความช่วยเหลือทางการเงิน" (0.01) — คำแบบเอกสาร
    "คนที่เพิ่งรู้จักในแอปหาคู่ขอเงิน เป็นมิจฉาชีพไหม" ได้ 0.99"""
    from ..ingest.sources import SOURCES
    titles = (re.sub(r"\s*\([^)]*\)\s*$", "", s["title"]).strip() for s in SOURCES)
    return tuple(dict.fromkeys(t for t in titles if t))


def _top(result):
    return max((it.meta.get("relevance", 0.0) for it in result.items), default=0.0)


def _neighbors(g, items):
    """chunk_id ก่อน/หลัง (…_c04 -> …_c03, …_c05) ที่มีอยู่จริงและยังไม่อยู่ในผล"""
    from ..retrieval.contract import RetrievalItem
    have = {it.id for it in items}
    out = []
    for it in [it for it in items if it.kind == "chunk"][:NEIGHBOR_OF]:
        m = _CID.match(it.id)
        if not m:
            continue
        for n in (int(m.group(2)) - 1, int(m.group(2)) + 1):
            cid = f"{m.group(1)}{n:0{len(m.group(2))}d}"
            text = g.chunk_text(cid) if n >= 0 else ""
            if text and cid not in have:
                have.add(cid)
                out.append(RetrievalItem(cid, "chunk", text, 0.0, it.source, {**it.meta, "neighbor_of": it.id}))
    return out


def find(retriever, query, k=8) -> Found:
    query = re.sub(r"\s+", " ", query.strip())
    raw = retriever.retrieve(query, k)
    route = raw.items[0].meta.get("route", "-") if raw.items else "-"
    n_before = len(raw.items)
    first = list(raw.items)                      # filter_relevant ตัด raw.items ทิ้ง -> เก็บทุกตัวไว้เอาคะแนนไปใช้ต่อ
    res = filter_relevant(query, raw)
    if _top(res) >= REWRITE_BELOW:
        return Found(res, route, n_before)
    from ..llm import tasks
    try:
        topics = tasks.rewrite_query(query, kb_topics())
    except Exception:
        topics = []
    if not topics:
        return Found(res, route, n_before)
    res2 = retriever.retrieve(query, k, extra=topics)
    res2.items += _neighbors(retriever.g, res2.items)
    # รอบ 2 ไม่ให้คะแนนคู่ที่รอบแรกให้ไปแล้ว: chunk เดิมเทียบเฉพาะคำถามที่แปลงใหม่ (ผลเท่าเดิม เร็วขึ้น)
    known = {it.id: it.meta["relevance"] for it in first if "relevance" in it.meta}
    res2 = filter_relevant(query, res2, extra=topics, known=known)
    if _top(res2) <= _top(res):
        return Found(res, route, n_before)
    return Found(res2, route, n_before, topics)
