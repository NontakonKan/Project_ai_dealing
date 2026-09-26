"""ปรึกษาเรื่องความรัก: Routed Hybrid RAG (ความรู้ 10 แหล่ง) -> ตอบพร้อมอ้างอิงแหล่งจริง"""
from pipelines.hybrid.retrievers import RoutedKnowledge
from pipelines.llm import tasks

from .. import live
from ..flex import MENU, text

_retriever = None
NO_INFO = ("เรื่องนี้ผมยังไม่มีข้อมูลที่เชื่อถือได้ในคลังความรู้ครับ 🙏 "
           "ผมตอบได้ดีเรื่องทฤษฎีความรัก รูปแบบความผูกพัน red flag การเลิกรา การจัดการอารมณ์ และการตั้งขอบเขตครับ")


def handle(line_user, msg):
    global _retriever
    if _retriever is None:
        _retriever = RoutedKnowledge(live.ctx())
    res = _retriever.retrieve(msg, 8)
    if not res.items:
        return [text(NO_INFO, MENU)]
    out = tasks.rag_answer(msg, res)
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
