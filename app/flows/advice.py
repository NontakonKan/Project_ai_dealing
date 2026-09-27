"""ปรึกษาเรื่องความรัก: Routed Hybrid RAG (ความรู้ 10 แหล่ง) -> ตอบพร้อมอ้างอิงแหล่งจริง"""
from pipelines.hybrid.retrievers import RoutedKnowledge
from pipelines.llm import tasks

from .. import intent, live
from ..flex import MENU, text

_retriever = None
NO_INFO = ("เรื่องนี้ผมยังไม่มีข้อมูลที่เชื่อถือได้ในคลังความรู้ครับ 🙏 "
           "ผมตอบได้ดีเรื่องทฤษฎีความรัก รูปแบบความผูกพัน red flag การเลิกรา การจัดการอารมณ์ และการตั้งขอบเขตครับ")


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
    res = _retriever.retrieve(query, 8)
    if not res.items:
        return [text(NO_INFO, MENU)]
    out = tasks.rag_answer(msg, res, history=history)
    from .. import log
    log.note(f"route={res.items[0].meta.get('route', '-')} ctx={len(out['refs'])} อ้างอิง={out['citations']['cited']}"
             + (" (ตอบไม่ได้)" if out["citations"]["abstained"] else ""))
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
    ref_line = ("\n\n📚 อ้างอิง: " + " / ".join(sources[:3])) if sources else ""
    return [text(out["answer"] + ref_line, MENU)]
