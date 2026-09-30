"""ข้อมูลร่วมของทุกกลุ่ม: คำถาม 52 ข้อ (rag_questions.json) + chunk 1,035 อัน + เกณฑ์ "chunk ที่ตอบได้"

เกณฑ์ความเกี่ยวข้องเดียวกับ pipelines/hybrid/knowledge_eval.py: chunk มีคำคาดหวัง >= ครึ่งหนึ่ง
คำถามที่ไม่มี chunk ใดผ่านเกณฑ์ในคลังเลย ไม่นำมาคิดคะแนนการค้น (วัดไม่ได้ ไม่ใช่ความผิดของโมเดล)
"""
import json

from ..common.paths import DATA, PROCESSED
from ..hybrid.knowledge_eval import _relevant
from ..llm.bench.datasets import rag

OUT = DATA / "eval" / "model_compare"
CONTEXT_FILE = OUT / "frozen_contexts.json"


def questions():
    return rag()


def chunks():
    with open(PROCESSED / "book_chunks.jsonl", encoding="utf-8") as f:
        return [(c["chunk_id"], c["text"]) for c in map(json.loads, f)]


def relevant(text, keywords) -> bool:
    return bool(keywords) and _relevant(text, keywords)


def gold(qs, docs) -> dict:
    """qid -> {chunk_id ที่ตอบได้} (เฉพาะคำถามที่ตอบได้และมี chunk ผ่านเกณฑ์)"""
    out = {}
    for q in qs:
        if q["answerable"]:
            ids = {cid for cid, text in docs if relevant(text, q["expected_keywords"])}
            if ids:
                out[q["qid"]] = ids
    return out


def frozen_contexts(rebuild=False) -> dict:
    """context ของแต่ละคำถามถูกสร้างครั้งเดียวแล้วบันทึกไว้ -> LLM ทุกตัวอ่าน context เดียวกันทุกตัวอักษร

    ใช้เส้นทางค้นจริงของบอท (Routed Hybrid + ด่านความเกี่ยวข้อง) ถ้าไม่มีอะไรผ่านด่าน (มักเป็นคำถามนอกคลัง)
    ใส่ 3 อันดับแรกที่ค้นเจอแทน เพื่อวัดว่า LLM ยอมตอบว่า "ไม่มีข้อมูล" เองได้ไหมเมื่อ context ไม่ตรงคำถาม"""
    if CONTEXT_FILE.exists() and not rebuild:
        return json.loads(CONTEXT_FILE.read_text(encoding="utf-8"))
    from ..hybrid.context import HybridContext
    from ..hybrid.gate import filter_relevant
    from ..hybrid.retrievers import RoutedKnowledge
    from ..llm.config import TASKS
    from ..llm.context import build
    from ..retrieval.contract import RetrievalResult
    retriever = RoutedKnowledge(HybridContext())
    out = {}
    for q in questions():
        raw = retriever.retrieve(q["question"], 8)
        top3 = list(raw.items[:3])
        res = filter_relevant(q["question"], raw)
        gated = bool(res.items)
        if not gated:
            res = RetrievalResult(raw.mode, q["question"], top3)
        pack = build(res, TASKS["rag_answer"].context_budget)
        texts = {it.id: it.text for it in res.items}
        out[q["qid"]] = {"context": pack.text, "refs": pack.refs, "passages": [texts[r] for r in pack.refs],
                         "passed_gate": gated}
    OUT.mkdir(parents=True, exist_ok=True)
    CONTEXT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
