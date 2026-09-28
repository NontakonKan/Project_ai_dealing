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

from .query_expand import normalize
from .reranker import _model

MIN_SCORE = 0.1
RELATIVE_MIN = 0.3      # chunk ต้องได้คะแนนอย่างน้อย 30% ของอันดับ 1 (ไม่ให้ chunk อ่อนเบียดที่ใน context)


_RULE = re.compile(r"^\((.+?)\) -\[(\w+)\]-> \((.+?)\)(?::\s*(.*))?$", re.S)
_REL_TH = {"COMPATIBLE_WITH": "มักเข้ากันได้ดี", "CONFLICTS_WITH": "มักมีปัญหากัน", "OPPOSITE_OF": "ตรงข้ามกัน"}


def _score_text(it):
    """ข้อความที่ให้ cross-encoder อ่าน: กฎจาก Graph แปลงเป็นประโยคธรรมดา (ข้อความที่ส่งให้ LLM ไม่เปลี่ยน)
    วัดจริง: "(ทักแชทบ่อย ตอบไว) -[CONFLICTS_WITH]-> (ตอบแชทช้า…)" ได้ 0.02 กับ "คุยกับแฟนผ่านแชทบ่อยแค่ไหนถึงจะพอดี"
    เพราะ reranker ไม่เข้าใจรูปแบบลูกศร"""
    m = _RULE.match(it.text.strip()) if it.kind == "graph_fact" else None
    if not m:
        return it.text
    a, rel, b, reason = m.groups()
    return f"คนแบบ{a} กับคนแบบ{b} {_REL_TH.get(rel, 'มีความสัมพันธ์กัน')}" + (f" เพราะ{reason}" if reason else "")


def filter_relevant(query, result, min_score=MIN_SCORE, extra=()):
    """คืน RetrievalResult เดิมที่เหลือเฉพาะ item ที่เกี่ยวข้อง (ใส่คะแนนไว้ใน meta.relevance)
    ใช้คะแนนสูงสุดของทุกแบบคำถาม (คนคุย / แฟน / อีกฝ่าย) — ดู query_expand.py"""
    from .query_expand import variants
    # กฎจากกราฟก็ต้องผ่านด่านเดียวกัน — วัดจริง "จะทักแชทคนที่แอบชอบก่อนดีไหม": กฎ "ทักแชทบ่อย/ตอบแชทช้า" 0.02
    # เคยข้ามด่านและถูกวางเป็น [1] เหนือหน้าวิทยานิพนธ์ที่ตอบตรง (0.65) -> LLM ตอบว่าไม่มีข้อมูล
    chunks = list(result.items)
    pairs = [(i, q, w) for i, it in enumerate(chunks) for w in _windows(_score_text(it)) for q in variants(query, extra)]
    scores = _model().predict([(q, w) for _, q, w in pairs], show_progress_bar=False) if pairs else []
    best = {}
    for (i, _, _), s in zip(pairs, scores):
        best[i] = max(best.get(i, 0.0), float(s))
    for i, it in enumerate(chunks):
        it.meta = {**it.meta, "relevance": round(best.get(i, 0.0), 3)}
    keep = [it for it in chunks if it.meta["relevance"] >= min_score]
    top = max((it.meta["relevance"] for it in keep), default=0.0)
    # ใช้คะแนนความเกี่ยวข้องเป็นลำดับสุดท้าย (context.build เรียงตาม score) และตัด chunk ที่ห่างจากอันดับ 1 มาก
    # วัดจริง "ควรเริ่มทักยังไงดี": chunk ที่ตอบตรง 0.884 เคยถูกใส่คู่กับบทความคนขี้อาย 0.107 เพราะเรียงตามคะแนนค้นหาเดิม
    keep = sorted((it for it in keep if it.meta["relevance"] >= top * RELATIVE_MIN), key=lambda it: -it.meta["relevance"])
    for it in keep:
        it.score = it.meta["relevance"]
    result.items = keep
    return result


# ---------- ด่านหลัง LLM เขียนคำตอบ ----------
# วัดจริง (rag_judge 34 คำตอบ, เทียบแต่ละประโยคกับทุก passage ที่บอทได้รับ):
#   ประโยคที่แต่งเกิน ("คุยแชทบ่อยๆ เพื่อให้ความสัมพันธ์ดีขึ้น") 0.008 / ประโยคที่มีหลักฐานจริงต่ำสุด 0.568
#   คำตอบที่แค่ทวนคำถาม ("จีบรุ่นพี่ในคณะดีไหม [10]") -> ตัดด้วยความคล้ายกับคำถาม
MIN_SUPPORT = 0.1
ECHO_NEW_CHARS = 5
MIN_CLAUSE = 40         # ท่อนสั้นกว่านี้รวมกับท่อนถัดไป (ท่อนสั้นมากคะแนนไม่นิ่ง)
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


def _clauses(body, min_len=MIN_CLAUSE):
    """แบ่งประโยคยาวเป็นท่อนตามช่องว่าง (ภาษาไทยเว้นวรรคระหว่างวลี) รวมท่อนสั้นให้ยาวอย่างน้อย min_len"""
    out, cur = [], ""
    for piece in body.split():
        cur = f"{cur} {piece}".strip()
        if len(cur) >= min_len:
            out.append(cur)
            cur = ""
    if cur:
        if out and len(cur) < min_len:
            out[-1] = f"{out[-1]} {cur}"
        else:
            out.append(cur)
    return out


def verify_answer(question, answer, passages, min_support=MIN_SUPPORT):
    """คืน (คำตอบที่เหลือเฉพาะท่อนที่มีหลักฐาน หรือ None, จำนวนท่อนที่ตัดทิ้ง)

    ตรวจทีละท่อน ไม่ใช่ทีละประโยค: LLM มักใส่อ้างอิงครั้งเดียวท้ายย่อหน้า ถ้าให้คะแนนทั้งย่อหน้า
    ท่อนที่แต่งเพิ่มจะได้คะแนนของท่อนจริงไปด้วย (วัดจริง: "เค้าไม่ให้ความสำคัญกับความสัมพันธ์" 0.043)
    """
    wins = [normalize(w) for p in passages for w in _windows(p)]   # "คนคุย" ในคำตอบ = "แฟน" ในแหล่ง
    kept, dropped = [], 0
    for sent in (s.strip() for s in _SENT.split(answer or "")):
        cites = " ".join(_CITE.findall(sent))
        body = _CITE.sub("", sent).strip(" .:-*")
        if not body:
            continue
        good = []
        for clause in _clauses(body):
            if len(clause) >= 8 and (_is_echo(clause, question) or not wins or float(max(
                    _model().predict([(normalize(clause), w) for w in wins], show_progress_bar=False))) < min_support):
                dropped += 1
                continue
            good.append(clause)
        if good:
            kept.append(" ".join(good) + (f" {cites}" if cites else ""))
    text = " ".join(kept).strip()
    return (text if _CITE.search(text) else None), dropped
