"""ด่านความเกี่ยวข้องก่อนส่ง context ให้ LLM — ตอบได้เฉพาะเรื่องที่มีในคลังความรู้ (RAG) เท่านั้น

ปัญหา: retriever คืน chunk เสมอแม้คลังไม่มีเรื่องที่ถาม ("คุยครั้งแรกตอนเดต" ได้บทความคนขี้อาย)
       แล้ว LLM หยิบประโยคที่ใกล้ที่สุดมาตอบ ทั้งที่ไม่ตรงคำถาม
วิธี: cross-encoder (bge-reranker-v2-m3) ให้คะแนน (คำถาม, chunk) ทีละคู่ เก็บเฉพาะ chunk ที่ >= MIN_SCORE
      graph_fact = กฎจาก taxonomy ของเราเอง -> เก็บไว้เสมอ / ไม่เหลืออะไร = ตอบว่าไม่มีข้อมูล (ไม่เรียก LLM)
ด่านหลัง (verify_answer): ตัดประโยคที่ทวนคำถาม / ไม่มีหลักฐานใน passage ใดเลย -> ไม่เหลือ = ตอบว่าไม่มีข้อมูล
วัดจริง (data/eval/rag_questions.json + คำถามที่คลังไม่ครอบคลุม 10 ข้อ):
  คำถามที่ไม่ครอบคลุม/นอกเรื่อง คะแนนสูงสุด <= 0.087 / คำถามที่ตอบได้ 32/33 ยังมี context ผ่านด่านที่ 0.1
"""
import re
from difflib import SequenceMatcher

from .reranker import _model

MIN_SCORE = 0.1


def filter_relevant(query, result, min_score=MIN_SCORE):
    """คืน RetrievalResult เดิมที่เหลือเฉพาะ item ที่เกี่ยวข้อง (ใส่คะแนนไว้ใน meta.relevance)"""
    chunks = [it for it in result.items if it.kind != "graph_fact"]
    pairs = [(i, w) for i, it in enumerate(chunks) for w in _windows(it.text)]   # ส่วนท้าย chunk ยาวต้องถูกอ่านด้วย
    scores = _model().predict([(query, w) for _, w in pairs], show_progress_bar=False) if pairs else []
    best = {}
    for (i, _), s in zip(pairs, scores):
        best[i] = max(best.get(i, 0.0), float(s))
    for i, it in enumerate(chunks):
        it.meta = {**it.meta, "relevance": round(best.get(i, 0.0), 3)}
    result.items = [it for it in result.items if it.kind == "graph_fact" or it.meta["relevance"] >= min_score]
    return result


# ---------- ด่านหลัง LLM เขียนคำตอบ ----------
# วัดจริง (rag_judge 34 คำตอบ, เทียบแต่ละประโยคกับทุก passage ที่บอทได้รับ):
#   ประโยคที่แต่งเกิน ("คุยแชทบ่อยๆ เพื่อให้ความสัมพันธ์ดีขึ้น") 0.008 / ประโยคที่มีหลักฐานจริงต่ำสุด 0.568
#   คำตอบที่แค่ทวนคำถาม ("จีบรุ่นพี่ในคณะดีไหม [10]") -> ตัดด้วยความคล้ายกับคำถาม
MIN_SUPPORT = 0.1
ECHO_NEW_CHARS = 5
WINDOW_CHARS = 600
_SENT = re.compile(r"(?<=\])\s*|\n+")
_CITE = re.compile(r"\[[\d,\s]+\]")


def _windows(text, size=WINDOW_CHARS, step=WINDOW_CHARS - 150):
    """cross-encoder อ่านได้ 512 token -> chunk ยาวถูกตัดท้าย ประโยคที่มาจากท้าย chunk จะได้คะแนนต่ำผิดๆ -> ตัดเป็นช่วงซ้อนกัน"""
    return [text[i:i + size] for i in range(0, max(1, len(text) - 150), step)] or [text]


def _is_echo(body, question) -> bool:
    """ทวนคำถาม = แทบไม่มีเนื้อหาใหม่ (< 5 ตัวอักษร และไม่มีตัวเลข) — "มีกลุ่มตัวอย่าง 433 คน" ไม่นับ"""
    ops = SequenceMatcher(None, question, body).get_opcodes()
    new = "".join(body[j1:j2] for tag, _, _, j1, j2 in ops if tag in ("insert", "replace"))
    return len(new.strip()) < ECHO_NEW_CHARS and not re.search(r"\d", new)


def verify_answer(question, answer, passages, min_support=MIN_SUPPORT):
    """คืน (คำตอบที่เหลือเฉพาะประโยคที่มีหลักฐาน หรือ None, จำนวนประโยคที่ตัดทิ้ง)"""
    kept, dropped = [], 0
    for sent in (s.strip() for s in _SENT.split(answer or "")):
        body = _CITE.sub("", sent).strip(" .:-*")
        if not body:
            continue
        if len(body) >= 8:
            echo = _is_echo(body, question)
            wins = [w for p in passages for w in _windows(p)]
            support = float(max(_model().predict([(body, w) for w in wins], show_progress_bar=False))) if wins else 0.0
            if echo or support < min_support:
                dropped += 1
                continue
        kept.append(sent)
    text = " ".join(kept).strip()
    return (text if _CITE.search(text) else None), dropped
