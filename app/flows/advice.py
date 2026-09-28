"""ปรึกษาเรื่องความรัก: Routed Hybrid RAG (ความรู้ 10 แหล่ง) -> ตอบพร้อมอ้างอิงแหล่งจริง"""
from pipelines.hybrid import search
from pipelines.hybrid.gate import verify_answer
from pipelines.hybrid.query_expand import hint
from pipelines.hybrid.retrievers import RoutedKnowledge
from pipelines.llm import parsing, tasks

import re

from .. import intent, live
from ..flex import MENU, text

_retriever = None
NO_INFO = ("เรื่องนี้ยังไม่มีในคลังความรู้ของผมครับ 🙏 ผมจะตอบเฉพาะจากเอกสารที่ตรวจสอบแล้วเท่านั้น\n"
           "ผมตอบได้ดีเรื่องทฤษฎีความรัก รูปแบบความผูกพัน red flag การเลิกรา การจัดการอารมณ์ และการตั้งขอบเขตครับ")


RE_DOMAIN = re.compile(r"(?:https?://)?(?:[A-Za-z0-9-]+\.)*?([A-Za-z0-9-]+)\.(?:co\.th|ac\.th|or\.th|go\.th|com|co|org|net|th|io)"
                       r"(?:/[^\s)]*)?")


def _plain(answer):
    """LINE ไม่แสดง markdown -> ตัด ** / # / ` ที่ psu-gemma ชอบใส่"""
    return re.sub(r"\*\*|__|`|^#+\s*", "", answer, flags=re.M)


def _no_link(title):
    """LINE แปลงข้อความที่ดูเหมือนโดเมน (xxx.co) เป็นลิงก์อัตโนมัติ -> อ้างอิงให้เห็นเป็นชื่อแหล่ง ไม่ใช่ลิงก์"""
    return RE_DOMAIN.sub(r"\1", title)


def handle(line_user, msg, history=None):
    global _retriever
    history = history or []
    # Only carry the old topic into a clear follow-up, not every new question.
    history = history if intent.is_followup(msg) else []
    query = msg
    if intent.is_followup(msg):
        if not history:
            return [text("หมายถึงเรื่องไหนครับ ช่วยบอกหัวข้อหรือคำถามก่อนหน้าอีกนิดได้ไหมครับ", MENU)]
        try:
            query = tasks.rewrite_question(msg, history)
        except tasks.AmbiguousFollowup:
            return [text("ช่วยระบุเรื่องที่อยากถามต่ออีกนิดได้ไหมครับ เพื่อให้ผมค้นข้อมูลได้ตรงเรื่อง", MENU)]
        except Exception:
            # The model being unavailable does not mean conversation memory is missing.
            return [text("ตอนนี้ผมประมวลผลคำถามต่อเนื่องไม่สำเร็จครับ ลองส่งอีกครั้งได้ไหมครับ", MENU)]
    if _retriever is None:
        _retriever = RoutedKnowledge(live.ctx())
    # Resolve conversation references before topic expansion and evidence filtering.
    found = search.find(_retriever, query)
    res, route, n_before = found.result, found.route, found.n_before
    if found.topics:
        route += f" หัวข้อ={found.topics}"
    if not res.items:
        from .. import log
        log.note(f"route={route} ไม่มีความรู้ที่ตรงคำถาม (0/{n_before} ผ่านด่าน) → ตอบว่าไม่มีข้อมูล")
        return [text(NO_INFO, MENU)]
    out = tasks.rag_answer(hint(msg, found.topics), res, history=history)
    dropped = 0
    if not out["citations"]["abstained"]:   # ด่านหลัง: ตัดประโยคที่ทวนคำถาม/ไม่มีหลักฐาน กันหลอน
        passages = [it.text for it in res.items if it.id in out["refs"]]
        checked, dropped = verify_answer(query, out["answer"], passages)
        if checked is None:
            out["citations"]["abstained"] = True
        else:
            out["answer"], out["citations"] = checked, parsing.citations(checked, len(out["refs"]))
    from .. import log
    log.note(f"route={route} ผ่านด่าน {len(res.items)}/{n_before} ctx={len(out['refs'])} อ้างอิง={out['citations']['cited']}"
             + (f" ตัดประโยคไม่มีหลักฐาน {dropped}" if dropped else "") + (" (ตอบไม่ได้)" if out["citations"]["abstained"] else ""))
    if out["citations"]["abstained"]:
        return [text(NO_INFO, MENU)]
    g = live.ctx().graph
    sources = []
    for n in out["citations"]["cited"]:
        if 1 <= n <= len(out["refs"]):
            ref = out["refs"][n - 1]
            src = g.prop(ref, "source_id") if not ref.startswith("rule:") else "taxonomy"
            title = g.prop(f"source:{src}", "title") if src != "taxonomy" else "กฎความเข้ากันได้ (taxonomy)"
            if title and title not in sources:
                sources.append(title)
    ref_line = ("\n\n📚 อ้างอิง: " + " / ".join(_no_link(t) for t in sources[:3])) if sources else ""
    return [text(_plain(out["answer"]) + ref_line, MENU)]
